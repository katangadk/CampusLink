from concurrent.futures import ThreadPoolExecutor
import json
import ssl
import threading

from fastapi.testclient import TestClient
import pytest

from campuslink.app import create_app
from campuslink.mail import MailOutbox
from campuslink.recovery import SMTPRecovery
from campuslink.security import token_hash
from .conftest import sql

KEY='Synthetic-mail-HMAC-key-for-isolated-tests-2026!'
PASSWORD='Mail-account-test-password-2026!'

class FakeDelivery:
    configured=True
    issues=[]
    def __init__(self,failures=0):self.messages=[];self.failures=failures
    def send(self,email,subject,body):
        if self.failures:
            self.failures-=1
            raise RuntimeError('Do not log this provider diagnostic: '+email+' '+KEY)
        self.messages.append((email,subject,body))

@pytest.fixture
def mailbox_app(monkeypatch,tmp_path):
    monkeypatch.setenv('CAMPUSLINK_MODE','local')
    monkeypatch.setenv('CAMPUSLINK_BASE_URL','https://mail.campuslink.test')
    monkeypatch.setenv('CAMPUSLINK_MAIL_TOKEN_SECRET',KEY)
    delivery=FakeDelivery()
    app=create_app(tmp_path/'mail.sqlite3',testing=True,recovery_delivery=delivery)
    c=TestClient(app,base_url='https://mail.campuslink.test')
    r=c.post('/api/auth/register',json={'email':'mail_owner@example.test','username':'mail_owner','display_name':'Mail owner','password':PASSWORD,'agreement':True})
    assert r.status_code==200
    c.headers['X-CSRF-Token']=r.json()['csrf']
    return app,c,delivery

def token_from(message):return message[2].rsplit('#',1)[1]

def test_queued_recovery_has_no_plaintext_token_and_is_one_time(mailbox_app):
    app,c,delivery=mailbox_app
    assert c.post('/api/auth/recover',json={'email':'mail_owner@example.test'}).status_code==200
    token=token_from(delivery.messages[0])
    assert sql(app,'SELECT token_hash FROM recovery_tokens')[0][0]==token_hash(token)
    queued=dict(sql(app,'SELECT * FROM mail_outbox')[0])
    assert token not in json.dumps(queued) and KEY not in json.dumps(queued) and queued['status']=='sent'
    assert c.post('/api/auth/reset-password',json={'token':token,'new_password':'Changed-account-password-2026!'}).status_code==200
    assert c.get('/api/me').status_code==401 and sql(app,'SELECT status FROM mail_outbox')[0][0]=='used'
    assert c.post('/api/auth/reset-password',json={'token':token,'new_password':PASSWORD}).status_code==400
    assert c.post('/api/auth/login',json={'email':'mail_owner@example.test','password':'Changed-account-password-2026!'}).status_code==200

def test_unknown_email_has_same_response_without_queueing(mailbox_app):
    app,c,delivery=mailbox_app
    known=c.post('/api/auth/recover',json={'email':'mail_owner@example.test'})
    unknown=c.post('/api/auth/recover',json={'email':'not_registered@example.test'})
    assert known.json()==unknown.json() and known.status_code==unknown.status_code==200
    assert len(delivery.messages)==1 and len(sql(app,'SELECT * FROM mail_outbox'))==1

def test_delivery_retries_after_restart_without_logging_secrets(mailbox_app,caplog):
    app,c,delivery=mailbox_app;delivery.failures=1
    c.post('/api/auth/recover',json={'email':'mail_owner@example.test'})
    queued=sql(app,'SELECT * FROM mail_outbox')[0]
    assert queued['status']=='queued' and queued['attempts']==1
    assert KEY not in caplog.text and 'mail_owner@example.test' not in caplog.text
    sql(app,'UPDATE mail_outbox SET next_attempt=0')
    fresh=FakeDelivery();restarted=create_app(app.state.db_path,testing=True,recovery_delivery=fresh)
    restarted.state.mailbox.process()
    assert len(fresh.messages)==1 and sql(app,'SELECT status FROM mail_outbox')[0][0]=='sent'
    assert sql(app,'SELECT token_hash FROM recovery_tokens')[0][0]==token_hash(token_from(fresh.messages[0]))

def test_key_rotation_cancels_pending_jobs(mailbox_app,monkeypatch):
    app,c,delivery=mailbox_app;delivery.failures=1
    c.post('/api/auth/recover',json={'email':'mail_owner@example.test'})
    sql(app,'UPDATE mail_outbox SET next_attempt=0')
    monkeypatch.setenv('CAMPUSLINK_MAIL_TOKEN_SECRET','Rotated-synthetic-mail-key-for-tests-only-2026!')
    fresh=FakeDelivery();restarted=create_app(app.state.db_path,testing=True,recovery_delivery=fresh)
    restarted.state.mailbox.process()
    assert not fresh.messages and sql(app,'SELECT status FROM mail_outbox')[0][0]=='cancelled'

def test_new_reset_request_invalidates_old_link(mailbox_app):
    app,c,delivery=mailbox_app
    c.post('/api/auth/recover',json={'email':'mail_owner@example.test'});old=token_from(delivery.messages[-1])
    c.post('/api/auth/recover',json={'email':'mail_owner@example.test'});new=token_from(delivery.messages[-1])
    assert old!=new
    assert c.post('/api/auth/reset-password',json={'token':old,'new_password':PASSWORD}).status_code==400
    assert c.post('/api/auth/reset-password',json={'token':new,'new_password':PASSWORD}).status_code==200

@pytest.mark.parametrize('change',['expired','inactive'])
def test_expired_or_inactive_jobs_are_not_delivered(mailbox_app,change):
    app,c,delivery=mailbox_app;delivery.failures=1
    c.post('/api/auth/recover',json={'email':'mail_owner@example.test'})
    sql(app,'UPDATE mail_outbox SET next_attempt=0'+(',expires_at=1' if change=='expired' else ''))
    if change=='inactive':sql(app,'UPDATE users SET status="deactivated"')
    app.state.mailbox.process()
    assert not delivery.messages and sql(app,'SELECT status FROM mail_outbox')[0][0]=='cancelled'

def test_retry_budget_stops_permanent_failure(mailbox_app):
    app,c,delivery=mailbox_app;delivery.failures=10
    c.post('/api/auth/recover',json={'email':'mail_owner@example.test'})
    for _ in range(4):
        sql(app,'UPDATE mail_outbox SET next_attempt=0');app.state.mailbox.process()
    row=sql(app,'SELECT status,attempts FROM mail_outbox')[0]
    assert row['status']=='failed' and row['attempts']==5

def test_two_workers_do_not_claim_same_job(mailbox_app):
    app,c,delivery=mailbox_app;delivery.failures=1
    c.post('/api/auth/recover',json={'email':'mail_owner@example.test'});sql(app,'UPDATE mail_outbox SET next_attempt=0')
    entered,release=threading.Event(),threading.Event()
    class BlockingDelivery(FakeDelivery):
        def send(self,*args):entered.set();release.wait(3);super().send(*args)
    transport=BlockingDelivery()
    one=MailOutbox(app.state.db_path,transport,base_url='https://mail.campuslink.test',secret=KEY)
    two=MailOutbox(app.state.db_path,transport,base_url='https://mail.campuslink.test',secret=KEY)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(one.process);assert entered.wait(3)
        pool.submit(two.process).result(timeout=3);release.set();first.result(timeout=3)
    assert len(transport.messages)==1

def test_confirming_email_is_not_student_or_age_approval(mailbox_app):
    app,c,delivery=mailbox_app
    assert c.post('/api/verification/email',json={}).status_code==200
    token=token_from(delivery.messages[0]);guest=TestClient(app)
    assert guest.post('/api/auth/verify-email',json={'token':token}).status_code==200
    status=c.get('/api/verification').json()
    assert status['email_confirmed'] and not status['student_verified'] and not status['adult_verified']
    assert guest.post('/api/auth/verify-email',json={'token':token}).status_code==400
    assert c.post('/api/verification/email',json={},headers={'X-CSRF-Token':'wrong'}).status_code==403

def test_email_change_invalidates_confirmation_link(mailbox_app):
    app,c,delivery=mailbox_app
    c.post('/api/verification/email',json={});token=token_from(delivery.messages[0])
    sql(app,'UPDATE users SET email="changed@example.test"')
    assert c.post('/api/auth/verify-email',json={'token':token}).status_code==400

@pytest.mark.parametrize('security,port',[('starttls','587'),('ssl','465')])
def test_smtp_verifies_tls_and_authentication(monkeypatch,security,port):
    for key,value in {'HOST':'smtp.example.test','FROM':'sender@example.test','USER':'sender@example.test','PASSWORD':'Synthetic-SMTP-password!','PORT':port,'TLS':security}.items():
        monkeypatch.setenv('CAMPUSLINK_SMTP_'+key,value)
    calls=[]
    class SMTP:
        def __init__(self,*args,**kwargs):
            if security=='ssl':assert kwargs['context'].verify_mode==ssl.CERT_REQUIRED
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def starttls(self,context):assert context.check_hostname;calls.append('tls')
        def login(self,user,password):assert password=='Synthetic-SMTP-password!';calls.append('login')
        def send_message(self,message):assert 'Reset your' in message['Subject'];calls.append('send');return {}
    monkeypatch.setattr('campuslink.recovery.smtplib.SMTP',SMTP);monkeypatch.setattr('campuslink.recovery.smtplib.SMTP_SSL',SMTP)
    delivery=SMTPRecovery(base_url='https://campuslink.test');assert delivery.configured
    delivery('recipient@example.test','Synthetic-token-2026!')
    assert 'login' in calls and calls[-1]=='send' and ('tls' in calls)==(security=='starttls')

def test_smtp_partial_credentials_are_not_ready(monkeypatch):
    monkeypatch.setenv('CAMPUSLINK_SMTP_HOST','smtp.example.test');monkeypatch.setenv('CAMPUSLINK_SMTP_FROM','sender@example.test')
    monkeypatch.setenv('CAMPUSLINK_SMTP_USER','sender@example.test');monkeypatch.delenv('CAMPUSLINK_SMTP_PASSWORD',raising=False)
    assert not SMTPRecovery(base_url='https://campuslink.test').configured
    monkeypatch.setenv('CAMPUSLINK_SMTP_TLS','none');assert not SMTPRecovery(base_url='https://campuslink.test').configured
