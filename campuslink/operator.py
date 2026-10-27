"""Explicitly privileged operation endpoints and private pilot feedback."""
import asyncio
import json
import sqlite3
import uuid

from fastapi import Request
from starlette.responses import FileResponse

from .security import check_password


def install_operator(app, *, db, auth, payload, text, fail, limit, now, operations, metrics, service, recovery,provider,eligibility):
    def operator(con, request):
        user, session = auth(con,request)
        if not con.execute('SELECT 1 FROM operator_roles WHERE user_id=?',(user['id'],)).fetchone():
            fail('Operator access required.',403)
        return user, session

    def audit(con, uid, action, detail=''):
        con.execute('INSERT INTO operator_audit(actor_id,action,detail,created_at) VALUES (?,?,?,?)',
                    (uid,action,detail,now()))

    @app.get('/api/service')
    def service_details():
        return service.public()

    @app.get('/api/operator/status')
    def operator_status(request: Request):
        with db() as con:
            operator(con,request)
            staff = con.execute('SELECT count(*) FROM operator_roles o JOIN users u ON o.user_id=u.id WHERE u.status="active"').fetchone()[0]
            reports = con.execute('SELECT count(*) FROM reports WHERE status="open"').fetchone()[0]
            feedback = con.execute('SELECT count(*) FROM pilot_feedback WHERE status!="resolved"').fetchone()[0]
        return {'operations':operations.status(),'metrics':metrics.snapshot(),'email':recovery.status(),
                'verification':{'provider':provider.name,'configured':provider.configured,'issues':provider.issues,'eligibility_mode':eligibility.mode,'approval_required':eligibility.requires_approval},
                'readiness':{'operator_configured':bool(service.operator_name and service.support_email),
                    'active_operators':staff,'email_configured':bool(getattr(recovery,'configured',False)),
                    'privacy_review_recorded':bool(service.privacy_review_date),
                    'student_domains_configured':bool(service.student_email_domains),
                    'physical_device_checks_recorded':False,'student_pilot_completed':False},
                'open_reports':reports,'open_feedback':feedback}

    @app.post('/api/operator/maintenance/{action}')
    async def run_operation(action: str, request: Request):
        actions = {'backup':operations.backup,'restore-check':operations.verify_restore,'cleanup':operations.cleanup}
        if action not in actions:
            fail('Unknown maintenance action.',404)
        with db() as con:
            user,_ = operator(con,request)
            limit(con,'maintenance:'+user['id'],3,60)
        try:
            result = await asyncio.to_thread(actions[action])
        except ValueError as exc:
            fail(str(exc),409)
        except (OSError,sqlite3.Error):
            fail('Maintenance failed. Check storage and the server configuration.',503)
        with db(True) as con:
            audit(con,user['id'],action,json.dumps({'status':'ok'}))
        return result

    @app.post('/api/operator/backup-download')
    async def download_backup(request: Request):
        data=await payload(request)
        with db() as con:
            user,_=operator(con,request)
            limit(con,'backup-export:'+user['id'],5,900)
            encoded=user['password_hash']
        if not await asyncio.to_thread(check_password,text(data,'password',128,1),encoded):
            fail('Your account password is incorrect.',403)
        try:
            path,entry=await asyncio.to_thread(operations.downloadable_backup)
        except ValueError as exc:
            fail(str(exc),409)
        except (OSError,sqlite3.Error):
            fail('Backup download is unavailable. Check storage and create a new backup.',503)
        with db(True) as con:
            user,_=operator(con,request)
            audit(con,user['id'],'backup_download',json.dumps({'filename':entry['filename'],'sha256':entry['sha256']}))
        return FileResponse(path,media_type='application/octet-stream',filename=entry['filename'],
                            headers={'Cache-Control':'no-store','X-Backup-SHA256':entry['sha256']})

    @app.post('/api/feedback')
    async def submit_feedback(request: Request):
        data = await payload(request)
        category = data.get('category')
        if category not in ('bug','usability','suggestion'):
            fail('Choose a feedback category.',422)
        body = text(data,'body',2000,10)
        with db() as con:
            user,_ = auth(con,request)
            limit(con,'feedback:'+user['id'],10,3600)
        identifier = str(uuid.uuid4())
        with db(True) as con:
            user,_ = auth(con,request)
            con.execute('INSERT INTO pilot_feedback(id,user_id,category,body,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                        (identifier,user['id'],category,body,now(),now()))
        return {'id':identifier,'status':'open'}

    @app.get('/api/feedback/mine')
    def own_feedback(request: Request):
        with db() as con:
            user,_ = auth(con,request)
            return {'items':[dict(row) for row in con.execute(
                'SELECT id,category,body,status,created_at,updated_at FROM pilot_feedback WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(user['id'],))]}

    @app.get('/api/operator/feedback')
    def feedback_list(request: Request):
        with db() as con:
            operator(con,request)
            return {'items':[dict(row) for row in con.execute(
                'SELECT f.*,u.username FROM pilot_feedback f LEFT JOIN users u ON u.id=f.user_id ORDER BY f.created_at DESC LIMIT 100')]}

    @app.post('/api/operator/feedback/{identifier}')
    async def update_feedback(identifier: str, request: Request):
        data = await payload(request)
        status = data.get('status')
        if status not in ('open','triaged','resolved'):
            fail('Choose open, triaged or resolved.',422)
        with db(True) as con:
            user,_ = operator(con,request)
            if not con.execute('SELECT 1 FROM pilot_feedback WHERE id=?',(identifier,)).fetchone():
                fail('Feedback unavailable.',404)
            con.execute('UPDATE pilot_feedback SET status=?,updated_at=? WHERE id=?',(status,now(),identifier))
            audit(con,user['id'],'feedback_status',json.dumps({'feedback_id':identifier,'status':status}))
        return {'ok':True}
