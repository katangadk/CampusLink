import json
from pathlib import Path
import time

from fastapi.testclient import TestClient
import pytest

from campuslink.admin import set_role
from campuslink.app import create_app
from campuslink.operations import Operations, OperationSettings, inspect_database, restore_rehearsal
from campuslink.service import ServiceSettings
from .conftest import accepted, sql


def manager(app, tmp_path, keep=2):
    return Operations(app.state.db_path,OperationSettings(True,tmp_path/'backups',24,keep))


def test_operator_access_requires_console_grant_and_rechecks_revocation(app, students):
    a, moderator = students['alice'], students['moderator']
    assert a.get('/operator/status').status_code == 403
    assert moderator.get('/operator/status').status_code == 403
    a.patch({'operator':True,'role':'moderator'})
    assert a.get('/operator/status').status_code == 403
    set_role(app.state.db_path,'alice','operator')
    assert a.get('/me').json()['user']['operator'] is True
    assert a.get('/operator/status').status_code == 200
    assert a.get('/moderation/reports').status_code == 200
    set_role(app.state.db_path,'alice','operator',revoke=True)
    assert a.get('/operator/status').status_code == 403
    assert a.get('/moderation/reports').status_code == 403
    assert [r['action'] for r in sql(app,'SELECT action FROM operator_audit ORDER BY id')]==['grant_operator','revoke_operator']


def test_staff_grant_requires_existing_active_account(app):
    with pytest.raises(ValueError):set_role(app.state.db_path,'not_an_account','operator')
    sql(app,'UPDATE users SET status="deactivated" WHERE username="alice"')
    with pytest.raises(ValueError):set_role(app.state.db_path,'alice','operator')
    assert not sql(app,'SELECT * FROM operator_roles')


def test_moderator_grant_handles_real_account_without_seed(app, tmp_path):
    fresh=create_app(tmp_path/'fresh.sqlite3',testing=True)
    c=TestClient(fresh)
    registered=c.post('/api/auth/register',json={'email':'real_operator@example.test','username':'real_operator',
        'display_name':'Operator','password':'Operator-individual-password-2026!','agreement':True})
    assert registered.status_code == 200
    set_role(fresh.state.db_path,'real_operator','moderator')
    assert c.get('/api/moderation/reports').status_code == 200
    assert c.get('/api/operator/status').status_code == 403
    set_role(fresh.state.db_path,'real_operator','operator')
    assert c.get('/api/operator/status').status_code == 200


def test_backup_restore_keeps_messages_and_verifies_content_without_overwriting(app, students, tmp_path):
    a,b=students['alice'],students['brian']
    rid=accepted(a,b)
    a.post('/chats/'+rid+'/messages',{'body':'Saved private message for restore.','client_id':'restore-original'})
    ops=manager(app,tmp_path)
    entry=ops.backup()
    path=ops.settings.directory/entry['filename']
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.with_suffix('.json').stat().st_mode & 0o777 == 0o600
    restored=ops.verify_restore()
    assert restored['restore_verified'] and not restored['active_database_overwritten']
    assert restored['content_sha256']==entry['content_sha256']
    assert restored['counts']['messages']==1
    assert a.get('/chats/'+rid+'/messages').json()['items'][0]['body']=='Saved private message for restore.'
    assert ops.status()['runs']['restore']['status']=='ok'
    serialized=json.dumps(entry)
    assert 'Saved private message' not in serialized and 'alice@' not in serialized
    assert entry['offsite_copy_verified'] is False


def test_backup_retention_only_removes_own_old_backups(app, tmp_path):
    ops=manager(app,tmp_path,keep=2)
    ops.settings.directory.mkdir()
    unrelated=ops.settings.directory/'operator-manual.sqlite3'
    unrelated.write_bytes(b'leave this alone')
    first=ops.backup();second=ops.backup();third=ops.backup()
    assert not (ops.settings.directory/first['filename']).exists()
    assert {item['filename'] for item in ops.manifests()}=={second['filename'],third['filename']}
    assert ops.manifests()[0]['filename']==third['filename']
    assert unrelated.read_bytes()==b'leave this alone'


def test_corrupted_backup_is_detected_and_live_data_remains(app, students, tmp_path):
    ops=manager(app,tmp_path)
    entry=ops.backup()
    (ops.settings.directory/entry['filename']).write_bytes(b'corrupted copy')
    with pytest.raises(ValueError,match='checksum'):
        ops.verify_restore()
    assert students['alice'].get('/me').status_code == 200
    assert ops.status()['runs']['restore']['status']=='failed'


def test_low_storage_keeps_last_good_backup(app, tmp_path, monkeypatch):
    from collections import namedtuple
    ops=manager(app,tmp_path)
    entry=ops.backup()
    usage=namedtuple('usage','total used free')
    monkeypatch.setattr('campuslink.operations.shutil.disk_usage',lambda _:usage(1024,1024,0))
    with pytest.raises(ValueError,match='storage'):
        ops.backup()
    assert (ops.settings.directory/entry['filename']).is_file()
    assert ops.status()['runs']['backup']['status']=='failed'


def test_cleanup_removes_only_expired_transient_data(app, students, tmp_path):
    a,b=students['alice'],students['brian'];uid=a.id;now=int(time.time())
    rid=accepted(a,b)
    a.post('/chats/'+rid+'/messages',{'body':'Retain this saved conversation.','client_id':'retained-message'})
    sql(app,'INSERT INTO sessions VALUES (?,?,?,?,?)',('expired-session',uid,'csrf',now-1,now-20))
    sql(app,'INSERT INTO recovery_tokens VALUES (?,?,?)',('expired-recovery',uid,now-1))
    sql(app,'INSERT INTO recovery_tokens VALUES (?,?,?)',('valid-recovery',uid,now+1000))
    sql(app,'INSERT INTO notifications(user_id,body,read,created_at) VALUES (?,?,?,?)',(uid,'old read',1,now-31*86400))
    sql(app,'INSERT INTO notifications(user_id,body,read,created_at) VALUES (?,?,?,?)',(uid,'old unread',0,now-31*86400))
    result=manager(app,tmp_path).cleanup()
    assert result['expired_sessions']==1 and result['expired_recovery_tokens']==1
    assert not sql(app,'SELECT * FROM sessions WHERE token_hash="expired-session"')
    assert sql(app,'SELECT * FROM recovery_tokens WHERE token_hash="valid-recovery"')
    assert not sql(app,'SELECT * FROM notifications WHERE body="old read"')
    assert sql(app,'SELECT * FROM notifications WHERE body="old unread"')
    assert a.get('/me').status_code==200
    assert a.get('/chats/'+rid+'/messages').json()['items'][0]['body']=='Retain this saved conversation.'


def test_inspection_never_creates_missing_source_and_restore_never_accepts_wrong_database(tmp_path):
    with pytest.raises(ValueError):inspect_database(tmp_path/'missing.sqlite3')
    assert not (tmp_path/'missing.sqlite3').exists()
    import sqlite3
    with sqlite3.connect(tmp_path/'other.sqlite3') as con:con.execute('CREATE TABLE x(id INTEGER)')
    with pytest.raises(ValueError):restore_rehearsal(tmp_path/'other.sqlite3')


def test_operator_maintenance_requires_role_and_csrf(app, students):
    a=students['alice']
    assert a.post('/operator/maintenance/cleanup').status_code==403
    set_role(app.state.db_path,'alice','operator')
    assert a.post('/operator/maintenance/cleanup',{}).status_code==200
    assert a.client.post('/api/operator/maintenance/cleanup',json={},headers={'X-CSRF-Token':'bad'}).status_code==403
    assert a.post('/operator/maintenance/not-an-action').status_code==404


def test_feedback_is_private_validated_and_operator_changes_are_audited(app, students):
    a,b=students['alice'],students['brian']
    sent=a.post('/feedback',{'category':'bug','body':'The keyboard covers my send button.'})
    assert sent.status_code==200
    identifier=sent.json()['id']
    assert a.get('/feedback/mine').json()['items'][0]['id']==identifier
    assert b.get('/feedback/mine').json()['items']==[]
    assert b.get('/operator/feedback').status_code==403
    assert b.post('/operator/feedback/'+identifier,{'status':'resolved'}).status_code==403
    assert a.post('/feedback',{'category':'invalid','body':'This should be rejected.'}).status_code==422
    set_role(app.state.db_path,'brian','operator')
    assert b.get('/operator/feedback').json()['items'][0]['body']=='The keyboard covers my send button.'
    assert b.post('/operator/feedback/'+identifier,{'status':'triaged'}).status_code==200
    assert a.get('/feedback/mine').json()['items'][0]['status']=='triaged'
    assert sql(app,'SELECT * FROM operator_audit WHERE action="feedback_status"')


def test_public_service_only_exposes_contact_details(app, monkeypatch, tmp_path):
    monkeypatch.setenv('CAMPUSLINK_OPERATOR_NAME','CampusLink pilot operator')
    monkeypatch.setenv('CAMPUSLINK_SUPPORT_EMAIL','support@example.test')
    monkeypatch.setenv('CAMPUSLINK_SMTP_PASSWORD','Not-for-public-responses!')
    configured=create_app(tmp_path/'contact.sqlite3',testing=True)
    c=TestClient(configured)
    response=c.get('/api/service')
    assert response.json()['support_email']=='support@example.test'
    assert 'Not-for-public-responses!' not in response.text
    assert c.get('/support').status_code==200


def test_request_metrics_use_ids_without_logging_content(app, students, caplog):
    a=students['alice'];response=a.get('/me')
    assert len(response.headers['x-request-id'])==32
    set_role(app.state.db_path,'alice','operator')
    status=a.get('/operator/status').json()
    assert status['metrics']['requests']>0
    assert status['metrics']['latency_ms']['p95']>=0
    assert 'campuslink_session' not in caplog.text
    assert status['readiness']['physical_device_checks_recorded'] is False


@pytest.mark.parametrize('name,value', [('CAMPUSLINK_BACKUP_KEEP','0'),('CAMPUSLINK_BACKUP_INTERVAL_HOURS','no'),
    ('CAMPUSLINK_BACKUPS_ENABLED','maybe'),('CAMPUSLINK_SUPPORT_EMAIL','bad\ncontact'),
    ('CAMPUSLINK_STUDENT_EMAIL_DOMAINS','*.university.test'),('CAMPUSLINK_PRIVACY_REVIEW_DATE','2999-01-01')])
def test_bad_operational_settings_are_rejected(app, monkeypatch, name, value, tmp_path):
    monkeypatch.setenv(name,value)
    with pytest.raises(RuntimeError):create_app(tmp_path/'bad.sqlite3',testing=True)


def test_database_downgrade_is_refused(app):
    sql(app,'PRAGMA user_version=999')
    with pytest.raises(RuntimeError,match='newer CampusLink'):
        create_app(app.state.db_path,testing=True)


def test_backup_export_requires_operator_current_password_csrf_and_matches_verified_file(app, students, tmp_path):
    import hashlib
    a,b=students['alice'],students['moderator']
    password='CampusLink-local-2026!'
    assert a.post('/operator/backup-download',{'password':password}).status_code==403
    assert b.post('/operator/backup-download',{'password':password}).status_code==403
    set_role(app.state.db_path,'alice','operator')
    assert a.post('/operator/backup-download',{'password':password}).status_code==409
    backup=a.post('/operator/maintenance/backup',{}).json()
    assert a.post('/operator/backup-download',{'password':'incorrect-password'}).status_code==403
    assert a.post('/operator/backup-download',{'password':password},headers={'X-CSRF-Token':'bad'}).status_code==403
    response=a.post('/operator/backup-download',{'password':password})
    assert response.status_code==200
    assert response.headers['cache-control']=='no-store'
    assert response.headers['x-backup-sha256']==hashlib.sha256(response.content).hexdigest()==backup['sha256']
    assert 'attachment' in response.headers['content-disposition']
    copied=tmp_path/'downloaded.sqlite3';copied.write_bytes(response.content)
    assert restore_rehearsal(copied)['restore_verified']
    assert sql(app,'SELECT * FROM operator_audit WHERE action="backup_download"')


def test_auto_approval_activates_at_staff_bootstrap_and_cannot_reopen_on_revoke(app, students, monkeypatch):
    from campuslink.eligibility import AccountEligibility
    from campuslink.service import ServiceSettings
    monkeypatch.setenv('CAMPUSLINK_REQUIRE_APPROVAL','auto')
    eligibility=AccountEligibility(app.state.db_path,ServiceSettings.load(),hosted=True)
    assert not eligibility.requires_approval
    set_role(app.state.db_path,'alice','operator')
    assert eligibility.requires_approval
    set_role(app.state.db_path,'alice','operator',revoke=True)
    restarted=AccountEligibility(app.state.db_path,ServiceSettings.load(),hosted=True)
    assert restarted.requires_approval


def test_schema_five_upgrade_preserves_existing_users_conversations_and_pending_memberships(app, students):
    a,b=students['alice'],students['brian'];rid=accepted(a,b)
    a.post('/chats/'+rid+'/messages',{'body':'Saved before the schema six upgrade.','client_id':'schema-six-upgrade'})
    before=[tuple(row) for row in sql(app,'SELECT id,email FROM users ORDER BY id')]
    # Recreate the schema-five boundary by removing only tables added in six.
    import sqlite3
    with sqlite3.connect(app.state.db_path) as con:
        con.execute('DROP TRIGGER IF EXISTS new_account_membership')
        for table in ('provider_events','provider_attempts','service_state','membership_approvals','mail_outbox',
                      'eligibility_checks','account_verification','email_verification_tokens','pilot_feedback',
                      'operation_runs','operator_audit','operator_roles'):
            con.execute('DROP TABLE '+table)
        con.execute('PRAGMA user_version=5')
    upgraded=create_app(app.state.db_path,testing=True)
    assert [tuple(row) for row in sql(upgraded,'SELECT id,email FROM users ORDER BY id')]==before
    assert sql(upgraded,'SELECT body FROM messages')[0][0]=='Saved before the schema six upgrade.'
    assert len(sql(upgraded,'SELECT * FROM membership_approvals WHERE status="pending"'))==len(before)
    assert sql(upgraded,'PRAGMA user_version')[0][0]==6
    assert a.get('/chats/'+rid+'/messages').status_code==200


def test_scheduler_runs_backup_and_restore_and_retries_unchecked_backup(app, tmp_path):
    import asyncio
    ops=manager(app,tmp_path)
    # A backup can exist after a process stopped before checking its restore.
    entry=ops.backup()
    original=ops.verify_restore
    async def exercise():
        stop=asyncio.Event();loop=asyncio.get_running_loop()
        def restored():
            result=original();loop.call_soon_threadsafe(stop.set);return result
        ops.verify_restore=restored
        await asyncio.wait_for(ops.run(stop),5)
    asyncio.run(exercise())
    status=ops.status()['runs']
    assert status['cleanup']['status']=='ok'
    assert status['restore']['summary']['filename']==entry['filename']
    assert status['restore']['summary']['restore_verified']
