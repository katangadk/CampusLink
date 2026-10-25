from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest
from fastapi.testclient import TestClient

from campuslink.app import create_app
from campuslink.seed import PASSWORD, seed
from campuslink.security import token_hash
from .conftest import Student, accepted, sql


def message(a,rid,body='Hello from campus',cid=None):
    return a.post(f'/chats/{rid}/messages',{'body':body,'client_id':cid or str(uuid.uuid4())})


def test_secure_registration_login_and_normalized_username(app):
    client=TestClient(app)
    data={'email':'new@example.test','username':'New_Student','display_name':'New student','password':PASSWORD,'agreement':True}
    result=client.post('/api/auth/register',json=data)
    assert result.status_code==200
    assert result.json()['user']['username']=='new_student'
    assert 'HttpOnly' in result.headers['set-cookie'] and 'SameSite=lax' in result.headers['set-cookie']
    user=result.json()['user']
    assert user['verified'] is False and user['adult_eligible'] is False and user['local_test'] is True
    row=sql(app,'SELECT password_hash FROM users WHERE id=?',(user['id'],))[0]
    assert PASSWORD not in row['password_hash'] and row['password_hash'].startswith('scrypt$')
    session=sql(app,'SELECT * FROM sessions WHERE user_id=?',(user['id'],))[0]
    assert client.cookies.get('campuslink_session')!=session['token_hash']
    assert client.post('/api/auth/register',json={**data,'email':'other@example.test'}).status_code==409
    assert client.post('/api/auth/register',json={**data,'username':'second'}).status_code==409
    assert client.post('/api/auth/register',json={**data,'password':'short'}).status_code==422


def test_authentication_csrf_origin_and_logout(students):
    a=students['alice']
    assert TestClient(a.client.app).get('/api/chats').status_code==401
    assert a.client.patch('/api/me',json={'bio':'changed'},headers={'X-CSRF-Token':'bad'}).status_code==403
    assert a.client.patch('/api/me',json={'bio':'changed'},headers={'Origin':'https://attacker.test'}).status_code==403
    assert a.post('/auth/logout').status_code==200
    assert a.get('/me').status_code==401


def test_onboarding_persists_and_requires_program(app):
    c=TestClient(app)
    result=c.post('/api/auth/register',json={'email':'onboard@example.test','username':'onboard','display_name':'A student','password':PASSWORD,'agreement':True}).json()
    c.headers['X-CSRF-Token']=result['csrf']
    assert c.patch('/api/me',json={'onboarding_step':6}).status_code==422
    assert c.patch('/api/me',json={'bio':'Learning things','onboarding_step':1}).status_code==200
    assert c.get('/api/me').json()['user']['bio']=='Learning things'
    assert c.patch('/api/me',json={'program':'Computer Science','interests':['Programming','Music'],'onboarding_step':6}).status_code==200
    assert c.get('/api/me').json()['user']['interests']==['Music','Programming']


def test_discovery_search_filters_scoring_and_public_projection(students):
    a,b=students['alice'],students['brian']
    result=a.get('/discover?mode=study&q=brian').json()['items']
    assert len(result)==1 and result[0]['id']==b.id
    assert 'Programming' in result[0]['shared_interests']
    for field in ['email','dob','password_hash','gender','dating_genders','adult_test','role']:
        assert field not in result[0]
    assert any('same program' in reason for reason in result[0]['reasons'])
    assert a.get('/discover?interest=Reading&year=3').json()['items'][0]['username']=='chipo'
    assert a.get('/discover?q=%27%20OR%201=1--').json()['items']==[]
    assert a.get('/discover?page=-1').status_code==422
    assert a.get('/discover?mode=dating').status_code==403


def test_hidden_inactive_and_nonstudent_profiles_excluded(students,app):
    a,b=students['alice'],students['brian']
    assert b.patch({'discoverable':False}).status_code==200
    assert a.get('/discover?q=brian').json()['items']==[]
    assert a.get('/profiles/'+b.id).status_code==404
    assert a.post('/connections',{'target_id':b.id,'kind':'friend'}).status_code==403
    b.patch({'discoverable':True})
    sql(app,'UPDATE users SET local_test=0 WHERE id=?',(b.id,))
    assert a.get('/discover?q=brian').json()['items']==[]
    sql(app,'UPDATE users SET local_test=1,status="suspended" WHERE id=?',(b.id,))
    assert a.get('/discover?q=brian').json()['items']==[]


@pytest.mark.parametrize('kind',['friend','study'])
def test_discover_request_accept_chat_and_remove(students,kind):
    a,b,c=students['alice'],students['brian'],students['chipo']
    result=a.post('/connections',{'target_id':b.id,'kind':kind})
    rid=result.json()['id']
    assert result.json()['status']=='pending'
    assert a.post('/connections',{'target_id':b.id,'kind':kind}).json()['id']==rid
    assert b.get('/connections').json()['items'][0]['direction']=='received'
    assert b.get('/notifications').json()['items'][0]['relationship_id']==rid
    assert message(a,rid).status_code==403
    assert a.get(f'/chats/{rid}/messages').status_code==403
    assert a.post(f'/connections/{rid}/accept').status_code==409
    assert b.post(f'/connections/{rid}/accept').status_code==200
    assert a.get('/chats').json()['items'][0]['kind']==kind
    sent=message(a,rid,'Hi Brian, want to study together?')
    assert sent.status_code==200
    mid=sent.json()['message']['id']
    assert b.get(f'/chats/{rid}/messages').json()['items'][0]['body']=='Hi Brian, want to study together?'
    assert b.get('/chats').json()['items'][0]['unread']==1
    assert b.post(f'/chats/{rid}/read',{'message_id':mid}).status_code==200
    assert b.get('/chats').json()['items'][0]['unread']==0
    assert c.get(f'/chats/{rid}/messages').status_code==404
    assert message(c,rid).status_code==404
    assert c.post(f'/chats/{rid}/read',{'message_id':mid}).status_code==404
    assert a.post(f'/connections/{rid}/remove').status_code==200
    assert message(b,rid).status_code==403
    assert b.get(f'/chats/{rid}/messages').status_code==403
    assert a.get('/chats').json()['items']==[]


def test_crossing_requests_create_one_connection(students,app):
    a,b=students['alice'],students['brian']
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(x.post,'/connections',{'target_id':y.id,'kind':'friend'}) for x,y in [(a,b),(b,a)]]
        responses=[f.result() for f in futures]
    assert all(r.status_code==200 for r in responses)
    assert len({r.json()['id'] for r in responses})==1
    rows=sql(app,'SELECT * FROM relationships')
    assert len(rows)==1 and rows[0]['status']=='accepted'


def test_decline_cancel_and_cooldown(students):
    a,b=students['alice'],students['brian']
    rid=a.post('/connections',{'target_id':b.id,'kind':'friend'}).json()['id']
    assert b.post(f'/connections/{rid}/decline').status_code==200
    assert a.post('/connections',{'target_id':b.id,'kind':'friend'}).status_code==409
    assert a.get('/discover?mode=friend&q=brian').json()['items']==[]
    rid=a.post('/connections',{'target_id':b.id,'kind':'study'}).json()['id']
    assert b.post(f'/connections/{rid}/cancel').status_code==409
    assert a.post(f'/connections/{rid}/cancel').status_code==200
    assert b.post(f'/connections/{rid}/accept').status_code==409


def test_accepted_hidden_profile_exception(students):
    a,b=students['alice'],students['brian']
    rid=accepted(a,b)
    b.patch({'discoverable':False})
    assert a.get('/profiles/'+b.id).status_code==200
    assert message(a,rid).status_code==200


def test_block_is_bidirectional_and_unblock_does_not_restore(students):
    a,b=students['alice'],students['brian']
    rid=accepted(a,b)
    assert message(a,rid).status_code==200
    assert b.post('/blocks/'+a.id).status_code==200
    for x,y in [(a,b),(b,a)]:
        assert x.get('/discover?q='+y.user['username']).json()['items']==[]
        assert x.get('/profiles/'+y.id).status_code==404
        assert message(x,rid).status_code==403
        assert x.get(f'/chats/{rid}/messages').status_code==403
        assert x.post('/connections',{'target_id':y.id,'kind':'friend'}).status_code==403
    assert b.client.delete('/api/blocks/'+a.id).status_code==200
    assert a.get('/connections').json()['items']==[]
    assert message(a,rid).status_code==403


def test_idempotent_concurrent_message_retry(students,app):
    a,b=students['alice'],students['brian']
    rid=accepted(a,b)
    cid=str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=[f.result() for f in [pool.submit(message,a,rid,'One message',cid),pool.submit(message,a,rid,'One message',cid)]]
    assert all(r.status_code==200 for r in results)
    assert results[0].json()==results[1].json()
    assert len(sql(app,'SELECT * FROM messages'))==1
    assert message(a,rid,'Different message',cid).status_code==409
    assert message(a,rid,' ').status_code==422
    assert message(a,rid,'x'*4001).status_code==422


def test_message_history_pagination_and_catchup(students,app):
    a,b=students['alice'],students['brian']
    rid=accepted(a,b)
    for i in range(63):
        assert message(a,rid,f'Message {i}').status_code==200
    newest=b.get(f'/chats/{rid}/messages').json()
    assert len(newest['items'])==50 and newest['has_more'] is True
    assert newest['items'][0]['body']=='Message 13'
    older=b.get(f'/chats/{rid}/messages?before='+str(newest['items'][0]['id'])).json()
    assert len(older['items'])==13 and older['has_more'] is False
    first=older['items'][0]['id']
    catchup=b.get(f'/chats/{rid}/messages?after={first}').json()
    assert len(catchup['items'])==50 and catchup['has_more'] is True
    ids=[m['id'] for m in older['items']+newest['items']]
    assert len(ids)==len(set(ids))==63


def activate(a,**extra):
    return a.patch({'dating_enabled':True,**extra})


def test_private_dating_likes_and_mutual_match_do_not_create_friendship(students,app):
    a,b=students['alice'],students['brian']
    assert activate(a).status_code==200 and activate(b).status_code==200
    assert a.get('/discover?mode=dating&q=brian').json()['items'][0]['id']==b.id
    notification_count=len(b.get('/notifications').json()['items'])
    assert a.post('/dating/'+b.id+'/like').json()=={'matched':False}
    assert len(b.get('/notifications').json()['items'])==notification_count
    assert sql(app,'SELECT * FROM events WHERE user_id=?',(b.id,))[-1]['id'] # activation event only
    assert b.get('/connections').json()['items']==[]
    r=b.post('/dating/'+a.id+'/like').json()
    assert r['matched'] is True
    rows=sql(app,'SELECT * FROM relationships')
    assert len(rows)==1 and rows[0]['kind']=='dating'
    assert message(a,r['id']).status_code==200
    assert b.post('/dating/'+a.id+'/like').json()['id']==r['id']
    assert len(sql(app,'SELECT * FROM relationships'))==1
    assert a.patch({'dating_enabled':False}).status_code==200
    assert message(b,r['id']).status_code==403
    assert b.get('/chats').json()['items']==[]
    activate(a)
    assert a.get('/chats').json()['items']==[]


def test_dating_requires_reciprocal_preferences_and_verified_adult_fixture(students,app):
    a,b,c=students['alice'],students['brian'],students['chipo']
    activate(a)
    activate(b,dating_genders=['man'])
    assert a.get('/discover?mode=dating&q=brian').json()['items']==[]
    assert a.post('/dating/'+b.id+'/like').status_code==403
    sql(app,'UPDATE users SET adult_test=0 WHERE id=?',(c.id,))
    assert c.patch({'dob':'2000-01-01','adult_test':True,'dating_enabled':True}).status_code==403
    sql(app,'UPDATE users SET dob="2015-01-01" WHERE id=?',(c.id,))
    assert activate(c).status_code==403


def test_unmatching_clears_private_likes(students,app):
    a,b=students['alice'],students['brian']
    activate(a);activate(b)
    a.post('/dating/'+b.id+'/like')
    rid=b.post('/dating/'+a.id+'/like').json()['id']
    assert b.post(f'/connections/{rid}/remove').status_code==200
    assert sql(app,'SELECT * FROM dating_likes')==[]
    assert message(a,rid).status_code==403


def test_reports_private_role_gated_and_moderation_audited(students,app):
    a,b,c,m=[students[k] for k in ('alice','brian','chipo','moderator')]
    rid=accepted(a,b)
    mid=message(b,rid,'A reportable message').json()['message']['id']
    result=a.post('/reports',{'target_id':b.id,'message_id':mid,'reason':'harassment','detail':'Test report'})
    assert result.status_code==200
    report_id=result.json()['id']
    assert b.get('/reports/mine').json()['items']==[]
    assert c.post('/reports',{'target_id':b.id,'message_id':mid,'reason':'spam'}).status_code==404
    assert a.get('/moderation/reports').status_code==403
    assert a.post('/moderation/reports/'+report_id,{'action':'suspend'}).status_code==403
    assert m.get('/moderation/reports').json()['items'][0]['message_body']=='A reportable message'
    assert m.post('/moderation/reports/'+report_id,{'action':'suspend'}).status_code==200
    assert len(sql(app,'SELECT * FROM moderation_audit'))==1
    assert b.get('/me').status_code==401
    assert a.get('/chats').json()['items']==[]
    assert message(a,rid).status_code==404
    assert a.get('/reports/mine').json()['items'][0]['status']=='resolved'


def test_other_sessions_revoked_and_password_changes_persist(students,app):
    a=students['alice']
    second=Student(app,'alice')
    assert len(a.get('/security/sessions').json()['items'])==2
    assert a.post('/security/revoke-others').status_code==200
    assert second.get('/me').status_code==401
    assert a.post('/security/password',{'current_password':'bad','new_password':'A-different-password!'}).status_code==403
    assert a.post('/security/password',{'current_password':PASSWORD,'new_password':'A-different-password!'}).status_code==200
    c=TestClient(app)
    assert c.post('/api/auth/login',json={'email':'alice@campuslink.test','password':PASSWORD}).status_code==401
    assert c.post('/api/auth/login',json={'email':'alice@campuslink.test','password':'A-different-password!'}).status_code==200


def test_delete_cascades_messages_and_anonymizes_reports(students,app):
    a,b=students['alice'],students['brian']
    rid=accepted(a,b)
    mid=message(a,rid).json()['message']['id']
    b.post('/reports',{'target_id':a.id,'message_id':mid,'reason':'spam'})
    assert a.post('/account/delete',{'password':'wrong'}).status_code==403
    assert a.post('/account/delete',{'password':PASSWORD}).status_code==200
    assert a.get('/me').status_code==401
    assert sql(app,'SELECT * FROM messages')==[]
    assert sql(app,'SELECT * FROM relationships')==[]
    row=sql(app,'SELECT * FROM reports')[0]
    assert row['target'] is None and row['message_id'] is None


def test_deactivation_closes_sessions_discovery_and_chat(students):
    a,b=students['alice'],students['brian']
    rid=accepted(a,b)
    assert b.post('/account/deactivate',{'password':PASSWORD}).status_code==200
    assert b.get('/me').status_code==401
    assert a.get('/discover?q=brian').json()['items']==[]
    assert message(a,rid).status_code==404


def test_rate_limits_persist_even_when_actions_rejected(students,app):
    a,b=students['alice'],students['brian']
    assert a.post('/connections',{'target_id':b.id,'kind':'friend'}).status_code==200
    sql(app,'UPDATE rate_limits SET count=30 WHERE key=?',('request:'+a.id,))
    assert a.post('/connections',{'target_id':b.id,'kind':'friend'}).status_code==429
    assert a.post('/connections',{'target_id':b.id,'kind':'friend'}).status_code==429
    sql(app,'UPDATE rate_limits SET count=600 WHERE key=?',('api:user:'+a.id,))
    response=a.get('/discover')
    assert response.status_code==429 and response.headers['Retry-After']=='60'


def test_input_types_body_limits_and_security_headers(students):
    a=students['alice']
    assert a.patch({'interests':['Made up']}).status_code==422
    assert a.patch({'discoverable':'false'}).status_code==422
    assert a.patch({'year':True}).status_code==422
    assert a.patch({'dating_min':30,'dating_max':18}).status_code==422
    assert a.patch({'bio':'x'*40000}).status_code==413
    r=a.get('/me')
    assert "frame-ancestors 'none'" in r.headers['Content-Security-Policy']
    assert r.headers['Cache-Control']=='no-store'
    assert TestClient(a.client.app).get('/api/events').status_code==401


def test_records_survive_server_recreation(students,app):
    a,b=students['alice'],students['brian']
    rid=accepted(a,b)
    message(a,rid,'Persist across a restart')
    recreated=create_app(app.state.db_path,testing=True)
    new_b=Student(recreated,'brian')
    assert new_b.get(f'/chats/{rid}/messages').json()['items'][0]['body']=='Persist across a restart'


def test_secure_recovery_generic_response_expiry_single_use_and_session_revocation(app):
    deliveries=[]
    recovered_app=create_app(app.state.db_path,testing=True,recovery_delivery=lambda email,token:deliveries.append((email,token)))
    a=Student(recovered_app,'alice')
    client=TestClient(recovered_app)
    known=client.post('/api/auth/recover',json={'email':'alice@campuslink.test'})
    unknown=client.post('/api/auth/recover',json={'email':'nobody@campuslink.test'})
    assert known.status_code==unknown.status_code==200 and known.json()==unknown.json()
    assert len(deliveries)==1
    token=deliveries[0][1]
    assert sql(app,'SELECT token_hash FROM recovery_tokens')[0]['token_hash']==token_hash(token)
    new='Recovered-password-2026!'
    assert client.post('/api/auth/reset-password',json={'token':'x'*43,'new_password':new}).status_code==400
    assert client.post('/api/auth/reset-password',json={'token':token,'new_password':new}).status_code==200
    assert a.get('/me').status_code==401
    assert client.post('/api/auth/reset-password',json={'token':token,'new_password':new}).status_code==400
    assert client.post('/api/auth/login',json={'email':'alice@campuslink.test','password':new}).status_code==200
    client.post('/api/auth/recover',json={'email':'alice@campuslink.test'})
    sql(app,'UPDATE recovery_tokens SET expires_at=1')
    assert client.post('/api/auth/reset-password',json={'token':deliveries[-1][1],'new_password':new}).status_code==400


def test_recovery_transport_not_configured_is_honest_and_does_not_enumerate(app):
    client=TestClient(app)
    assert client.get('/api/catalog').json()['recovery_available'] is False
    a=client.post('/api/auth/recover',json={'email':'alice@campuslink.test'})
    b=client.post('/api/auth/recover',json={'email':'nobody@campuslink.test'})
    assert a.status_code==b.status_code==503 and a.json()==b.json()


def test_dating_fixtures_are_available_after_explicit_opt_in_only(students):
    a=students['alice']
    assert a.get('/me').json()['user']['dating_enabled']==0
    assert a.get('/discover?mode=dating').status_code==403
    assert activate(a).status_code==200
    profiles=a.get('/discover?mode=dating').json()['items']
    assert {'demo_daniel','demo_musa'}.issubset({p['username'] for p in profiles})
    assert 'brian' not in {p['username'] for p in profiles}
    for profile in profiles:
        assert profile['age']>=18 and profile['verified'] is False
        assert not {'dob','email','dating_genders','gender','adult_test'} & profile.keys()
    assert all('age' not in p for p in a.get('/discover?mode=friend').json()['items'])


def test_reseeding_dating_demo_preserves_existing_choices(students,app):
    a=students['alice']
    demo=Student(app,'demo_daniel')
    assert demo.patch({'dating_enabled':False,'dating_genders':['man']}).status_code==200
    seed(app.state.db_path,dating_only=True)
    profile=demo.get('/me').json()['user']
    assert profile['dating_enabled']==0 and profile['dating_genders']==['man']
    assert a.get('/me').json()['user']['dating_enabled']==0


def test_account_switching_revokes_only_the_previous_browser_session(students,app):
    a=students['alice']
    other=Student(app,'alice')
    previous=TestClient(app)
    previous.cookies.set('campuslink_session',a.client.cookies.get('campuslink_session'))
    switched=a.post('/auth/login',{'email':'brian@campuslink.test','password':PASSWORD})
    assert switched.status_code==200
    assert a.get('/me').json()['user']['username']=='brian'
    assert previous.get('/api/me').status_code==401
    assert other.get('/me').status_code==200


def test_created_account_can_declare_local_adult_test_access_without_auto_activation(app):
    c=TestClient(app)
    registered=c.post('/api/auth/register',json={'email':'local_dating@example.test','username':'local_dating','display_name':'Local Dating','password':PASSWORD,'agreement':True}).json()
    c.headers['X-CSRF-Token']=registered['csrf']
    assert c.post('/api/dating/test-eligibility',json={'dob':'2001-06-15'}).status_code==422
    assert c.post('/api/dating/test-eligibility',json={'dob':'2015-06-15','adult_test_agreement':True}).status_code==403
    assert c.get('/api/me').json()['user']['adult_eligible'] is False
    assert c.post('/api/dating/test-eligibility',json={'dob':'bad-date!!','adult_test_agreement':True}).status_code==403
    result=c.post('/api/dating/test-eligibility',json={'dob':'2001-06-15','adult_test_agreement':True})
    assert result.status_code==200
    assert result.json()['eligibility']=='self_declared_local_test'
    user=result.json()['user']
    assert user['adult_eligible'] is True and user['verified'] is False and user['dating_enabled']==0
    assert c.get('/api/discover?mode=dating').status_code==403
    enabled=c.patch('/api/me',json={'dating_enabled':True,'gender':'man','dating_genders':['woman']})
    assert enabled.status_code==200 and enabled.json()['user']['dating_enabled']==1


def test_local_adult_declaration_requires_auth_csrf_and_local_account(students,app):
    data={'dob':'2001-06-15','adult_test_agreement':True}
    a=students['alice']
    assert TestClient(app).post('/api/dating/test-eligibility',json=data).status_code==401
    assert a.client.post('/api/dating/test-eligibility',json=data,headers={'X-CSRF-Token':'wrong'}).status_code==403
    sql(app,'UPDATE users SET local_test=0 WHERE id=?',(a.id,))
    assert a.post('/dating/test-eligibility',data).status_code==403
