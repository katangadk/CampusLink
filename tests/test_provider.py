import copy
import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient
import pytest

from campuslink.admin import set_role
from campuslink.app import create_app
from campuslink.provider import SheerID
from .conftest import sql
from .test_mail import FakeDelivery,KEY,PASSWORD,token_from

STUDENT='a'*24
ADULT='b'*24
WEBHOOK='Synthetic-SheerID-webhook-secret-only-for-tests!'

class FakeSheerID(SheerID):
    def __init__(self):super().__init__();self.responses={};self.created=0;self.themes={}
    def api(self,path,body=None):
        if path.startswith('program/'):
            age='b'*24 in path
            return copy.deepcopy(self.themes.get('adult' if age else 'student',{'isTestMode':False,'config':{'segment':'age' if age else 'student','countries':['ZM'],'minAge':18}}))
        if path=='verification':
            self.created+=1
            return {'verificationId':f'{self.created:024x}'}
        identifier=path.split('/')[1]
        return copy.deepcopy(self.responses[identifier])

@pytest.fixture
def provider_app(monkeypatch,tmp_path):
    for key,value in {
        'CAMPUSLINK_REQUIRE_APPROVAL':'true','CAMPUSLINK_ELIGIBILITY_MODE':'external',
        'CAMPUSLINK_BASE_URL':'https://verify.campuslink.test','CAMPUSLINK_MAIL_TOKEN_SECRET':KEY,
        'CAMPUSLINK_VERIFICATION_PROVIDER':'sheerid','CAMPUSLINK_VERIFICATION_LIVE':'true',
        'CAMPUSLINK_SHEERID_CLIENT_ID':'synthetic-oauth-client','CAMPUSLINK_SHEERID_CLIENT_SECRET':'synthetic-client-secret',
        'CAMPUSLINK_SHEERID_WEBHOOK_SECRET':WEBHOOK,'CAMPUSLINK_SHEERID_STUDENT_PROGRAM_ID':STUDENT,
        'CAMPUSLINK_SHEERID_AGE_PROGRAM_ID':ADULT,'CAMPUSLINK_SHEERID_ORGANIZATION_ID':'9001',
    }.items():monkeypatch.setenv(key,value)
    delivery=FakeDelivery();provider=FakeSheerID()
    app=create_app(tmp_path/'provider.sqlite3',testing=True,recovery_delivery=delivery,verification_provider=provider)
    def member(name):
        c=TestClient(app,base_url='https://verify.campuslink.test')
        r=c.post('/api/auth/register',json={'username':name,'display_name':name,'email':name+'@example.test','password':PASSWORD,'agreement':True})
        assert r.status_code==200
        c.headers['X-CSRF-Token']=r.json()['csrf']
        c.patch('/api/me',json={'program':'Computer Science','onboarding_step':6})
        return c,r.json()['user']['id']
    owner,owner_id=member('owner');student,uid=member('student')
    set_role(app.state.db_path,'owner','operator')
    owner.post('/api/operator/members/'+uid,json={'action':'approve'})
    c=student
    assert c.post('/api/verification/email',json={}).status_code==200
    assert c.post('/api/auth/verify-email',json={'token':token_from(delivery.messages[-1])}).status_code==200
    return app,owner,c,uid,provider,member,delivery

def begin(bundle,kind='student'):
    app,owner,c,uid,provider,*_=bundle
    response=c.post('/api/verification/start/'+kind,json={'consent':True})
    assert response.status_code==200,response.text
    row=dict(sql(app,'SELECT * FROM provider_attempts WHERE user_id=? AND kind=? ORDER BY rowid DESC',(uid,kind))[0])
    identifier=row['provider_id']
    provider.responses[identifier]={
        'programId':row['program_id'],'lastResponse':{'verificationId':identifier,'currentStep':'success','segment':'student' if kind=='student' else 'age'},
        'personInfo':{'email':'student@example.test','firstName':'Given','lastName':'Student','birthDate':'2001-06-15'},
        'approvingVerificationTypes':['authoritative'],
        'confirmedSegments':[{'segment':'student','active':True,'organization':{'id':9001},'endDate':int((time.time()+60*86400)*1000)}],
    }
    return row

def approve_student(bundle):
    row=begin(bundle)
    assert bundle[2].post('/api/verification/refresh/student',json={}).json()['status']=='approved'
    return row

def test_external_checks_are_separate_from_owner_approval_and_self_declaration(provider_app):
    app,owner,c,uid,provider,*_=provider_app
    assert c.get('/api/discover').status_code==403
    assert c.post('/api/dating/test-eligibility',json={'dob':'2001-06-15','adult_test_agreement':True}).status_code==403
    approve_student(provider_app)
    assert c.get('/api/discover').status_code==200
    user=c.get('/api/me').json()['user']
    assert user['verified'] and not user['adult_eligible'] and user['local_test'] is False
    begin(provider_app,'adult')
    assert c.post('/api/verification/refresh/adult',json={}).json()['status']=='approved'
    user=c.get('/api/me').json()['user']
    assert user['adult_eligible'] and not user['dating_enabled'] and user['dob']=='2001-06-15'

def test_start_is_authenticated_csrf_protected_consented_and_reuses_pending_reference(provider_app):
    app,owner,c,uid,provider,*_=provider_app
    assert TestClient(app).post('/api/verification/start/student',json={'consent':True}).status_code==401
    assert c.post('/api/verification/start/student',json={'consent':False}).status_code==422
    assert c.post('/api/verification/start/student',json={'consent':True},headers={'X-CSRF-Token':'bad'}).status_code==403
    first=c.post('/api/verification/start/student',json={'consent':True})
    second=c.post('/api/verification/start/student',json={'consent':True})
    assert first.json()==second.json() and provider.created==1
    assert first.json()['url'].startswith('https://services.sheerid.com/verify/')
    assert 'synthetic-client-secret' not in first.text

@pytest.mark.parametrize('change',['program','account','campus','inactive','honor','email_only','test','missing_identity','null_identity','malformed_source'])
def test_canonical_mismatches_and_weak_sources_never_grant_student_status(provider_app,change):
    app,owner,c,uid,provider,*_=provider_app
    row=begin(provider_app);result=provider.responses[row['provider_id']]
    if change=='program':result['programId']='c'*24
    if change=='account':result['personInfo']['email']='another@example.test'
    if change=='campus':result['confirmedSegments'][0]['organization']['id']=9999
    if change=='inactive':result['confirmedSegments'][0]['active']=False
    if change=='honor':result['approvingVerificationTypes']=['honorSystem']
    if change=='email_only':result['approvingVerificationTypes']=['emailLoop','domainValidation']
    if change=='test':result['isTestMode']=True
    if change=='missing_identity':result['personInfo']['lastName']=''
    if change=='null_identity':result['personInfo']['lastName']=None
    if change=='malformed_source':result['approvingVerificationTypes']=[{'source':'authoritative'}]
    assert c.post('/api/verification/refresh/student',json={}).json()['status']=='rejected'
    assert c.get('/api/discover').status_code==403

@pytest.mark.parametrize('change',['underage','different_person','honor'])
def test_age_check_needs_adult_evidence_and_same_verified_person(provider_app,change):
    app,owner,c,uid,provider,*_=provider_app
    approve_student(provider_app);row=begin(provider_app,'adult');result=provider.responses[row['provider_id']]
    if change=='underage':result['personInfo']['birthDate']='2012-06-15'
    if change=='different_person':result['personInfo']['lastName']='Somebody else'
    if change=='honor':result['approvingVerificationTypes']=['honorSystem']
    assert c.post('/api/verification/refresh/adult',json={}).json()['status']=='rejected'
    assert not c.get('/api/me').json()['user']['adult_eligible']

def signed_event(identifier,**changes):
    event={'verificationId':identifier,'notifierEventType':'SUCCESS','timestamp':int(time.time()*1000),'nonce':'n'*32,**changes}
    body=json.dumps(event,separators=(',',':')).encode()
    return body,hmac.new(WEBHOOK.encode(),body,hashlib.sha256).hexdigest()

def test_signed_webhook_rechecks_canonical_result_and_is_idempotent(provider_app):
    app,owner,c,uid,provider,*_=provider_app
    row=begin(provider_app);result=provider.responses[row['provider_id']];result['lastResponse']['currentStep']='pending'
    body,signature=signed_event(row['provider_id'])
    guest=TestClient(app)
    assert guest.post('/api/webhooks/sheerid',content=body,headers={'Content-Type':'application/json','X-SheerID-Signature':signature}).status_code==200
    assert not c.get('/api/verification').json()['student_verified']
    result['lastResponse']['currentStep']='success'
    body,signature=signed_event(row['provider_id'],nonce='fresh_nonce_for_success_2026')
    headers={'Content-Type':'application/json','X-SheerID-Signature':signature}
    assert guest.post('/api/webhooks/sheerid',content=body,headers=headers).status_code==200
    expiry=sql(app,'SELECT expires_at FROM eligibility_checks WHERE user_id=? AND kind="student"',(uid,))[0][0]
    assert guest.post('/api/webhooks/sheerid',content=body,headers=headers).json()['duplicate']
    assert sql(app,'SELECT expires_at FROM eligibility_checks WHERE user_id=? AND kind="student"',(uid,))[0][0]==expiry
    assert c.get('/api/verification').json()['student_verified']

@pytest.mark.parametrize('attack',['missing','wrong','old','modified','unknown'])
def test_bad_or_stale_webhooks_do_not_approve(provider_app,attack):
    app,owner,c,uid,provider,*_=provider_app
    row=begin(provider_app)
    body,signature=signed_event('f'*24 if attack=='unknown' else row['provider_id'],**({'timestamp':1} if attack=='old' else {}))
    if attack=='missing':signature=''
    if attack=='wrong':signature='0'*64
    if attack=='modified':body+=b' '
    response=TestClient(app).post('/api/webhooks/sheerid',content=body,headers={'Content-Type':'application/json','X-SheerID-Signature':signature})
    assert response.status_code==(404 if attack=='unknown' else 401)
    assert not c.get('/api/verification').json()['student_verified']

def test_old_verification_cannot_renew_expired_eligibility(provider_app):
    app,owner,c,uid,provider,*_=provider_app
    row=approve_student(provider_app)
    sql(app,'UPDATE provider_attempts SET created_at=? WHERE id=?',(int(time.time())-91*86400,row['id']))
    sql(app,'UPDATE eligibility_checks SET expires_at=1 WHERE user_id=?',(uid,))
    assert c.post('/api/verification/refresh/student',json={}).json()['status']=='rejected'
    assert c.get('/api/discover').status_code==403

@pytest.mark.parametrize('change',['test','country','minimum_age'])
def test_provider_configuration_must_be_live_in_zambia_and_age_appropriate(provider_app,change):
    app,owner,c,uid,provider,*_=provider_app
    kind='student'
    if change=='minimum_age':approve_student(provider_app);kind='adult'
    theme={'isTestMode':change=='test','config':{'segment':'student' if kind=='student' else 'age','countries':['US'] if change=='country' else ['ZM'],'minAge':17 if change=='minimum_age' else 18}}
    provider.themes[kind]=theme
    assert c.post('/api/verification/start/'+kind,json={'consent':True}).status_code==503
    assert provider.created==(1 if kind=='adult' else 0)

def test_oauth_uses_documented_endpoint_and_never_follows_arbitrary_hosts(provider_app,monkeypatch):
    provider=provider_app[4];calls=[]
    def request(url,**kwargs):calls.append((url,kwargs));return {'access_token':'synthetic-bearer','expires_in':3600}
    monkeypatch.setattr(provider,'_request',request)
    assert provider.access_token()=='synthetic-bearer' and provider.access_token()=='synthetic-bearer'
    assert len(calls)==1 and calls[0][0]=='https://auth.sheerid.com/oauth/token'
    assert calls[0][1]['body']['grant_type']=='client_credentials'
    actual=SheerID()
    with pytest.raises(ValueError):actual._request('https://attacker.test/path',bearer='private')


def test_simultaneous_starts_create_only_one_remote_verification(provider_app):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    app,owner,c,uid,provider,*_=provider_app
    original=provider.create;entered=threading.Event();release=threading.Event()
    def blocking_create(kind):
        entered.set();assert release.wait(5);return original(kind)
    provider.create=blocking_create
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(c.post,'/api/verification/start/student',json={'consent':True})
        assert entered.wait(5)
        second=pool.submit(c.post,'/api/verification/start/student',json={'consent':True}).result(timeout=5)
        assert second.status_code==409
        release.set();assert first.result(timeout=5).status_code==200
    assert provider.created==1
