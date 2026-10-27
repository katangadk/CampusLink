"""Durable email jobs without storing plaintext reset/verification tokens."""
import argparse
import base64
from contextlib import closing
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import threading
import time
import uuid

from .operations import connect
from .security import token_hash


class MailOutbox:
    def __init__(self,database,transport,*,base_url,secret=None):
        self.database,self.transport=database,transport
        self.base=base_url.rstrip('/')
        raw=secret if secret is not None else os.getenv('CAMPUSLINK_MAIL_TOKEN_SECRET','')
        self._secret=raw.encode()
        self.key_id=hashlib.sha256(self._secret).hexdigest()[:16]
        self.issues=list(getattr(transport,'issues',[]))
        if len(raw)<32 or raw!=raw.strip() or any(ord(c)<32 for c in raw):
            self.issues.append('Set CAMPUSLINK_MAIL_TOKEN_SECRET to a random secret of at least 32 characters.')
        self.configured=bool(getattr(transport,'configured',False) and hasattr(transport,'send') and self.base and not self.issues)
        self.lock=threading.Lock()

    def token(self,job):
        value=json.dumps([job[k] for k in ('id','user_id','purpose','email_hash','created_at','expires_at')],separators=(',',':')).encode()
        return base64.urlsafe_b64encode(hmac.digest(self._secret,b'campuslink-mail-v1\0'+value,'sha256')).decode().rstrip('=')

    def enqueue(self,con,user,purpose):
        if not self.configured or purpose not in ('recovery','verify_email'):
            raise ValueError('Email delivery is not configured.')
        now=int(time.time())
        job={'id':str(uuid.uuid4()),'user_id':user['id'],'purpose':purpose,
             'email_hash':token_hash(user['email'].lower()),'created_at':now,'expires_at':now+1800}
        token_hash_value=token_hash(self.token(job))
        con.execute('UPDATE mail_outbox SET status="cancelled",lease_until=0 WHERE user_id=? AND purpose=? AND status IN ("queued","sending")',
                    (user['id'],purpose))
        table='recovery_tokens' if purpose=='recovery' else 'email_verification_tokens'
        con.execute('DELETE FROM '+table+' WHERE user_id=?',(user['id'],))
        if purpose=='recovery':
            con.execute('INSERT INTO recovery_tokens VALUES (?,?,?)',(token_hash_value,user['id'],job['expires_at']))
        else:
            con.execute('INSERT INTO email_verification_tokens VALUES (?,?,?,?)',
                        (token_hash_value,user['id'],job['email_hash'],job['expires_at']))
        con.execute('INSERT INTO mail_outbox(id,user_id,purpose,email_hash,key_id,created_at,expires_at,next_attempt) VALUES (?,?,?,?,?,?,?,?)',
            (job['id'],user['id'],purpose,job['email_hash'],self.key_id,now,job['expires_at'],now))
        return job['id']

    def claim(self):
        now=int(time.time())
        with closing(connect(self.database)) as con:
            con.execute('BEGIN IMMEDIATE')
            job=con.execute('SELECT * FROM mail_outbox WHERE status IN ("queued","sending") AND next_attempt<=? AND lease_until<=? ORDER BY created_at,id LIMIT 1',
                            (now,now)).fetchone()
            if job:
                con.execute('UPDATE mail_outbox SET status="sending",attempts=attempts+1,lease_until=? WHERE id=?',(now+180,job['id']))
            con.commit()
            return dict(job) if job else None

    def update(self,identifier,status,*,attempts=0,error=''):
        now=int(time.time())
        with closing(connect(self.database)) as con:
            con.execute('UPDATE mail_outbox SET status=?,lease_until=0,sent_at=CASE WHEN ?="sent" THEN ? ELSE sent_at END, '
                'next_attempt=?,last_error=? WHERE id=? AND status="sending"',
                (status,status,now,now+min(300,30*2**min(attempts,4)),error,identifier))
            con.commit()

    def process(self,limit=2):
        if not self.configured or not self.lock.acquire(blocking=False):return
        try:
            for _ in range(limit):
                job=self.claim()
                if not job:break
                now=int(time.time());token=self.token(job)
                table='recovery_tokens' if job['purpose']=='recovery' else 'email_verification_tokens'
                with closing(connect(self.database,readonly=True)) as con:
                    user=con.execute('SELECT * FROM users WHERE id=? AND status="active"',(job['user_id'],)).fetchone()
                    current=con.execute('SELECT 1 FROM '+table+' WHERE token_hash=? AND user_id=? AND expires_at>?',
                                        (token_hash(token),job['user_id'],now)).fetchone()
                if (not user or not current or job['expires_at']<=now or job['key_id']!=self.key_id
                        or token_hash(user['email'].lower())!=job['email_hash']):
                    self.update(job['id'],'cancelled');continue
                if job['purpose']=='recovery':
                    subject='Reset your CampusLink password';path='/reset-password'
                    intro='A password reset was requested for your CampusLink account.'
                else:
                    subject='Confirm your CampusLink email';path='/verify-email'
                    intro='Confirm this email address for your CampusLink account. This does not verify your student status or age.'
                body=intro+'\n\nThis link expires in 30 minutes and can be used once. If you did not request it, ignore this email.\n\n'+self.base+path+'#'+token
                try:
                    self.transport.send(user['email'],subject,body)
                except Exception:
                    attempts=job['attempts']+1
                    self.update(job['id'],'failed' if attempts>=5 else 'queued',attempts=attempts,error='Provider did not accept the message.')
                    logging.getLogger('campuslink.mail').warning('Email provider did not accept a queued message; retry recorded.')
                else:
                    self.update(job['id'],'sent')
        finally:self.lock.release()

    def consumed(self,con,uid,purpose):
        con.execute('UPDATE mail_outbox SET status="used",lease_until=0 WHERE user_id=? AND purpose=? AND status IN ("sent","sending","queued")',(uid,purpose))

    def status(self):
        with closing(connect(self.database,readonly=True)) as con:
            counts={row['status']:row['count'] for row in con.execute('SELECT status,count(*) AS count FROM mail_outbox WHERE created_at>? GROUP BY status',(int(time.time())-86400,))}
        return {'configured':self.configured,'issues':self.issues,'last_24_hours':counts,
                'sent_means':'Accepted by the provider; mailbox receipt still requires confirmation.'}


def main():
    parser=argparse.ArgumentParser(description='Check email configuration without revealing credentials.')
    parser.add_argument('--test-to',help='Explicitly send a test message to this operator-controlled address')
    args=parser.parse_args()
    from .recovery import SMTPRecovery
    from .deployment import Deployment
    deployment=Deployment.load(Path(__file__).resolve().parent.parent)
    delivery=SMTPRecovery(base_url=deployment.origin or None)
    result={'smtp_configured':delivery.configured,'issues':delivery.issues,
            'mail_token_secret_configured':len(os.getenv('CAMPUSLINK_MAIL_TOKEN_SECRET',''))>=32}
    if args.test_to:
        if not delivery.configured:parser.exit(1,'Configure the SMTP sender before sending a test.\n')
        delivery.send(args.test_to,'CampusLink delivery test','This operator-requested test checks CampusLink email delivery. No password or reset token is included.')
        result['test_message']='Provider accepted the message. Confirm it arrived in the intended mailbox.'
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
