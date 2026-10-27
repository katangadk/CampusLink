"""Email ownership confirmation and eligibility status, without document uploads."""
from fastapi import Request
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse

from .security import token_hash


def install_verification(app,*,db,auth,payload,text,fail,limit,now,emit,mailbox,eligibility):
    @app.get('/api/verification')
    def verification_status(request: Request):
        with db() as con:
            user,_=auth(con,request)
            return eligibility.details(con,user)

    @app.post('/api/verification/email')
    async def request_email_confirmation(request: Request):
        with db() as con:
            user,_=auth(con,request)
            limit(con,'email-confirmation:'+user['id'],3,3600)
            if eligibility.details(con,user)['email_confirmed']:
                return {'message':'Your email is already confirmed.'}
        if not mailbox.configured:
            fail('Email confirmation is unavailable until delivery is configured.',503)
        with db(True) as con:
            user,_=auth(con,request)
            mailbox.enqueue(con,user,'verify_email')
        return JSONResponse({'message':'A confirmation link has been queued for your account email.'},
                            background=BackgroundTask(mailbox.process))

    @app.post('/api/auth/verify-email')
    async def confirm_email(request: Request):
        data=await payload(request)
        token=text(data,'token',100,20)
        with db() as con:
            limit(con,'confirm-email-ip:'+request.client.host,15,900)
        with db(True) as con:
            record=con.execute('SELECT t.*,u.email FROM email_verification_tokens t JOIN users u ON t.user_id=u.id '
                'WHERE t.token_hash=? AND t.expires_at>? AND u.status="active"',(token_hash(token),now())).fetchone()
            if not record or record['email_hash']!=token_hash(record['email'].lower()):
                fail('This confirmation link is invalid or expired. Request a new one.',400)
            con.execute('INSERT INTO account_verification VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET '
                'email_hash=excluded.email_hash,email_verified_at=excluded.email_verified_at',
                (record['user_id'],record['email_hash'],now()))
            con.execute('DELETE FROM email_verification_tokens WHERE user_id=?',(record['user_id'],))
            mailbox.consumed(con,record['user_id'],'verify_email')
            emit(con,record['user_id'])
        return {'ok':True,'email_confirmed':True}
