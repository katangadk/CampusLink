"""Backend-bound provider sessions; browser redirects never grant eligibility."""
import asyncio
import hashlib
import json
import uuid

from fastapi import Request

from .membership import revoke_dating
from .security import token_hash


def install_provider(app,*,db,auth,payload,fail,limit,now,emit,eligibility,provider):
    async def synchronize(attempt):
        try:
            details=await asyncio.to_thread(provider.details,attempt['kind'],attempt['provider_id'])
            result=provider.evaluate(attempt,details)
        except ValueError:
            fail('The verification service could not be checked. Try again later.',503)
        with db(True) as con:
            current=con.execute('SELECT * FROM provider_attempts WHERE id=?',(attempt['id'],)).fetchone()
            user=con.execute('SELECT * FROM users WHERE id=? AND status="active"',(attempt['user_id'],)).fetchone()
            if not current or not user or token_hash(user['email'].lower())!=attempt['email_hash']:
                fail('Verification account changed. Start a new check.',409)
            latest=con.execute('SELECT id FROM provider_attempts WHERE user_id=? AND kind=? AND provider_id IS NOT NULL ORDER BY created_at DESC,rowid DESC LIMIT 1',
                               (user['id'],attempt['kind'])).fetchone()
            if latest['id']!=attempt['id']:return {'status':'superseded'}
            status=result['status']
            expires=attempt['created_at']+(90 if attempt['kind']=='student' else 365)*86400
            if result.get('provider_expires_at'):expires=min(expires,result['provider_expires_at'])
            if status=='approved' and expires<=now():
                status='rejected';result['reason']='verification_expired'
            if status=='approved' and attempt['kind']=='adult':
                student=con.execute('SELECT * FROM provider_attempts WHERE user_id=? AND kind="student" AND status="approved" ORDER BY updated_at DESC,rowid DESC LIMIT 1',(user['id'],)).fetchone()
                if not student or student['identity_hash']!=result['identity_hash'] or not eligibility.details(con,user)['student_verified']:
                    status='rejected';result['reason']='identity_binding_failed'
            existing=con.execute('SELECT status,expires_at FROM eligibility_checks WHERE user_id=? AND kind=?',(user['id'],attempt['kind'])).fetchone()
            changed=status!=current['status'] or (existing and existing['status']=='approved' and (not existing['expires_at'] or existing['expires_at']<=now()))
            if changed and (status=='rejected' or (status=='approved' and existing and existing['status']=='approved' and (not existing['expires_at'] or existing['expires_at']<=now()))):
                revoke_dating(con,user['id'],now,emit)
            if status=='approved' and attempt['kind']=='student':
                prior=con.execute('SELECT identity_hash FROM provider_attempts WHERE user_id=? AND kind="student" AND status="approved" AND id!=? ORDER BY updated_at DESC,rowid DESC LIMIT 1',(user['id'],attempt['id'])).fetchone()
                if prior and prior['identity_hash']!=result['identity_hash']:
                    con.execute('UPDATE eligibility_checks SET status="rejected",expires_at=NULL,updated_at=? WHERE user_id=? AND kind="adult"',(now(),user['id']))
                    revoke_dating(con,user['id'],now,emit)
            expires=expires if status=='approved' else None
            if status in ('approved','rejected'):
                # Repeat callbacks cannot keep extending an old approval forever.
                if status=='approved' and existing and existing['status']=='approved' and not changed:
                    expires=existing['expires_at']
                con.execute('INSERT INTO eligibility_checks(user_id,kind,status,method,reference_hash,expires_at,updated_at) VALUES (?,?,?,?,?,?,?) '
                    'ON CONFLICT(user_id,kind) DO UPDATE SET status=excluded.status,method=excluded.method,reference_hash=excluded.reference_hash,expires_at=excluded.expires_at,updated_at=excluded.updated_at',
                    (user['id'],attempt['kind'],status,'provider',token_hash(attempt['provider_id']),expires,now()))
                if status=='approved' and attempt['kind']=='adult':con.execute('UPDATE users SET dob=? WHERE id=?',(result['dob'],user['id']))
            con.execute('UPDATE provider_attempts SET status=?,identity_hash=?,updated_at=? WHERE id=?',
                (status,result.get('identity_hash',''),now(),attempt['id']))
            if changed:
                con.execute('INSERT INTO operator_audit(actor_id,target_id,action,detail,created_at) VALUES (NULL,?,?,?,?)',
                    (user['id'],'provider_'+attempt['kind']+'_'+status,json.dumps({'reason':result['reason']}),now()))
            emit(con,user['id'])
        return {'status':status}

    @app.post('/api/verification/start/{kind}')
    async def start_verification(kind: str,request: Request):
        if kind not in ('student','adult'):fail('Unknown verification check.',404)
        data=await payload(request)
        if data.get('consent') is not True:fail('Confirm you agree to continue with the verification partner.',422)
        if not provider.configured:fail('External verification is not configured yet. Contact the operator.',503)
        with db() as con:
            user,_=auth(con,request)
            status=eligibility.details(con,user)
            if not eligibility.approved(con,user):fail('Wait for campus membership approval before starting this check.',403)
            if not status['email_confirmed']:fail('Confirm your account email first.',403)
            if kind=='adult' and not status['student_verified']:fail('Complete the student-status check first.',403)
            existing=con.execute('SELECT * FROM provider_attempts WHERE user_id=? AND kind=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(user['id'],kind)).fetchone()
            if existing and existing['status']=='pending' and existing['provider_id'] and existing['program_id']==provider.programs[kind] and existing['created_at']>now()-86400:
                return {'url':provider.hosted_url(kind,existing['provider_id'])}
            if existing and existing['status']=='creating' and existing['created_at']>now()-60:
                fail('A verification is already starting. Wait a moment and check again.',409)
            limit(con,'provider-start:'+user['id'],3,86400)
        identifier=str(uuid.uuid4())
        with db(True) as con:
            user,_=auth(con,request)
            # Serialize starts before contacting a potentially billable API.
            # The earlier read alone cannot exclude concurrent browser tabs.
            latest=con.execute('SELECT * FROM provider_attempts WHERE user_id=? AND kind=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(user['id'],kind)).fetchone()
            if latest and latest['status']=='creating' and latest['created_at']>now()-60:
                fail('A verification is already starting. Wait a moment and check again.',409)
            if latest and latest['status']=='pending' and latest['provider_id'] and latest['program_id']==provider.programs[kind] and latest['created_at']>now()-86400:
                return {'url':provider.hosted_url(kind,latest['provider_id'])}
            con.execute('INSERT INTO provider_attempts(id,user_id,kind,program_id,status,email_hash,consent_version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                (identifier,user['id'],kind,provider.programs[kind],'creating',token_hash(user['email'].lower()),'2026-10-27',now(),now()))
        try:
            remote=await asyncio.to_thread(provider.create,kind)
        except ValueError:
            with db(True) as con:con.execute('UPDATE provider_attempts SET status="failed",updated_at=? WHERE id=?',(now(),identifier))
            fail('The verification service could not start. Try again later.',503)
        with db(True) as con:
            con.execute('UPDATE provider_attempts SET provider_id=?,status="pending",live_started=1,updated_at=? WHERE id=?',(remote,now(),identifier))
        return {'url':provider.hosted_url(kind,remote)}

    @app.post('/api/verification/refresh/{kind}')
    async def refresh_verification(kind: str,request: Request):
        if kind not in ('student','adult'):fail('Unknown verification check.',404)
        if not provider.configured:fail('External verification is not configured yet.',503)
        with db() as con:
            user,_=auth(con,request)
            limit(con,'provider-refresh:'+user['id'],6,60)
            record=con.execute('SELECT * FROM provider_attempts WHERE user_id=? AND kind=? AND provider_id IS NOT NULL ORDER BY created_at DESC,rowid DESC LIMIT 1',(user['id'],kind)).fetchone()
            if not record:fail('Start this verification check first.',404)
        return await synchronize(dict(record))

    @app.post('/api/webhooks/sheerid')
    async def provider_webhook(request: Request):
        body=await request.body()
        event=provider.signed_event(body,request.headers.get('x-sheerid-signature',''))
        if event is None:fail('Webhook authentication failed.',401)
        digest=hashlib.sha256(body).hexdigest()
        with db() as con:
            if con.execute('SELECT 1 FROM provider_events WHERE body_sha256=?',(digest,)).fetchone():return {'ok':True,'duplicate':True}
            record=con.execute('SELECT * FROM provider_attempts WHERE provider_id=?',(event['verificationId'],)).fetchone()
        if not record:fail('Unknown verification reference.',404)
        await synchronize(dict(record))
        with db(True) as con:con.execute('INSERT OR IGNORE INTO provider_events VALUES (?,?)',(digest,now()))
        return {'ok':True}
