from fastapi.testclient import TestClient
import pytest

from campuslink.admin import set_role
from campuslink.app import create_app
from .conftest import sql

PASSWORD='Membership-individual-password-2026!'

@pytest.fixture
def approval_app(monkeypatch,tmp_path):
    monkeypatch.setenv('CAMPUSLINK_REQUIRE_APPROVAL','true')
    app=create_app(tmp_path/'approval.sqlite3',testing=True)
    def member(name):
        c=TestClient(app)
        result=c.post('/api/auth/register',json={'username':name,'display_name':name,'email':name+'@example.test','password':PASSWORD,'agreement':True})
        assert result.status_code==200
        c.headers['X-CSRF-Token']=result.json()['csrf']
        assert c.patch('/api/me',json={'program':'Computer Science','onboarding_step':6}).status_code==200
        return c,result.json()['user']['id']
    owner,owner_id=member('owner');student,student_id=member('student')
    set_role(app.state.db_path,'owner','operator')
    return app,owner,owner_id,student,student_id,member

def test_new_accounts_are_pending_but_site_and_own_profile_are_accessible(approval_app):
    app,owner,owner_id,c,uid,_=approval_app
    assert TestClient(app).get('/').status_code==200
    assert c.get('/api/me').json()['user']['verification']['membership']['status']=='pending'
    for route in ('/api/discover','/api/feed','/api/chats','/api/connections','/api/events'):
        assert c.get(route).status_code==403
    assert c.get('/api/feedback/mine').status_code==200
    assert c.get('/api/operator/members').status_code==403
    assert owner.get('/api/operator/members').status_code==200

def test_owner_can_approve_email_without_granting_age_verification(approval_app):
    app,owner,owner_id,c,uid,_=approval_app
    rows=owner.get('/api/operator/members').json()['items']
    assert next(row for row in rows if row['id']==uid)['email']=='student@example.test'
    assert owner.post('/api/operator/members/'+uid,json={'action':'approve'}).status_code==200
    assert c.get('/api/discover').status_code==200
    status=c.get('/api/verification').json()
    assert status['membership']['status']=='approved'
    assert not status['email_confirmed'] and not status['student_verified'] and not status['adult_verified']
    assert c.get('/api/me').json()['user']['adult_eligible'] is False
    owner.post('/api/operator/members/'+uid,json={'action':'approve'})
    assert len(sql(app,'SELECT * FROM operator_audit WHERE action="membership_approve"'))==1

def test_members_cannot_approve_themselves_or_forge_roles(approval_app):
    app,owner,owner_id,c,uid,_=approval_app
    assert c.post('/api/operator/members/'+uid,json={'action':'approve'}).status_code==403
    c.patch('/api/me',json={'operator':True,'role':'moderator','approval_status':'approved'})
    assert c.get('/api/discover').status_code==403
    assert c.post('/api/operator/members/'+uid,json={'action':'approve'}).status_code==403
    assert owner.post('/api/operator/members/'+uid,json={'action':'approve'},headers={'X-CSRF-Token':'bad'}).status_code==403

def test_declining_revokes_chat_and_reapproval_does_not_restore_it(approval_app):
    app,owner,owner_id,a,a_id,member=approval_app
    b,b_id=member('second_student')
    for uid in (a_id,b_id):assert owner.post('/api/operator/members/'+uid,json={'action':'approve'}).status_code==200
    relation=a.post('/api/connections',json={'target_id':b_id,'kind':'friend'}).json()['id']
    assert b.post('/api/connections/'+relation+'/accept',json={}).status_code==200
    assert a.post('/api/chats/'+relation+'/messages',json={'body':'Retain this saved message.','client_id':'before-decline'}).status_code==200
    assert owner.post('/api/operator/members/'+a_id,json={'action':'decline','reason':'unable_to_confirm'}).status_code==200
    assert a.get('/api/chats/'+relation+'/messages').status_code==403
    assert b.get('/api/chats/'+relation+'/messages').status_code==403
    assert a.get('/api/me').status_code==200
    assert sql(app,'SELECT body FROM messages')[0][0]=='Retain this saved message.'
    assert owner.post('/api/operator/members/'+a_id,json={'action':'approve'}).status_code==200
    assert a.get('/api/chats/'+relation+'/messages').status_code==403
    assert a.get('/api/me').json()['user']['dating_enabled']==0

def test_operator_manages_queue_before_own_membership_is_approved(approval_app):
    app,owner,owner_id,c,uid,_=approval_app
    assert owner.get('/api/me').json()['user']['verification']['membership']['status']=='pending'
    assert owner.get('/api/operator/status').status_code==200
    assert owner.get('/api/operator/members').status_code==200
    assert owner.post('/api/operator/members/'+owner_id,json={'action':'approve'}).status_code==200
    assert owner.get('/api/discover').status_code==200

def test_decline_requires_reason_and_suspended_accounts_are_not_reactivated(approval_app):
    app,owner,owner_id,c,uid,_=approval_app
    assert owner.post('/api/operator/members/'+uid,json={'action':'decline'}).status_code==422
    sql(app,'UPDATE users SET status="suspended" WHERE id=?',(uid,))
    assert owner.post('/api/operator/members/'+uid,json={'action':'approve'}).status_code==409


def test_pending_members_can_delete_their_own_account(approval_app):
    app,owner,owner_id,c,uid,_=approval_app
    assert c.get('/api/discover').status_code==403
    assert c.post('/api/account/delete',json={'password':PASSWORD}).status_code==200
    assert not sql(app,'SELECT id FROM users WHERE id=?',(uid,))
