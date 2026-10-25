import json
import uuid

import pytest
from fastapi.testclient import TestClient

from campuslink.app import create_app
from campuslink.starters import CAMPUS_QUESTIONS
from tests.conftest import Student, accepted, sql
from tests.test_flows import message
from tests.test_intentions import match
from tests.test_prompts import answer, save


def starters(student, rid):
    return student.get(f'/chats/{rid}/starters')


def test_both_participants_get_shared_interests_and_the_other_profiles_answers(students):
    a, b = students['alice'], students['brian']
    save(a, [answer(text='ALICE_VISIBLE_ANSWER')])
    save(b, [answer('small_joy', 'BRIAN_VISIBLE_ANSWER')])
    rid = match(a, b)
    for viewer, visible, excluded in [(a, 'BRIAN_VISIBLE_ANSWER', 'ALICE_VISIBLE_ANSWER'),
                                      (b, 'ALICE_VISIBLE_ANSWER', 'BRIAN_VISIBLE_ANSWER')]:
        response = starters(viewer, rid)
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        items = response.json()['items']
        assert len(items) == len({item['id'] for item in items}) == 3
        assert any(item['source'] == 'shared_interest' and 'Programming' in item['context'] for item in items)
        assert visible in json.dumps(items) and excluded not in json.dumps(items)
        assert all(0 < len(item['text']) < 300 for item in items)


def test_no_overlap_or_prompts_returns_campus_questions(students):
    a, b = students['alice'], students['brian']
    a.patch({'interests': ['Music']})
    b.patch({'interests': ['Gaming']})
    rid = match(a, b)
    items = starters(a, rid).json()['items']
    assert [item['text'] for item in items] == CAMPUS_QUESTIONS
    assert {item['source'] for item in items} == {'campus'}


def test_prompt_without_shared_interests_and_long_plain_text_is_bounded(students):
    a, b = students['alice'], students['brian']
    a.patch({'interests': []})
    b.patch({'interests': []})
    literal = '<img src=x onerror="alert(1)"> ' + 'x' * 240
    assert save(b, [answer('teach_me', literal)]).status_code == 200
    rid = match(a, b)
    items = starters(a, rid).json()['items']
    assert items[0]['source'] == 'profile_prompt'
    assert '<img src=x' in items[0]['text']  # Plain text; the UI must escape it.
    assert len(items[0]['text']) < 200
    assert all(item['source'] == 'campus' for item in items[1:])


def test_current_profile_answers_and_interests_are_used_without_private_data(students):
    a, b = students['alice'], students['brian']
    save(b, [answer(text='An old visible answer.')])
    b.patch({'dating_intention': 'figuring_out', 'show_dating_intention': False})
    rid = match(a, b)
    first = starters(a, rid).json()['items']
    assert 'An old visible answer.' in json.dumps(first)
    save(b, [answer('campus_date', 'A new visible answer.')])
    second = starters(a, rid).json()['items']
    assert 'A new visible answer.' in json.dumps(second)
    assert 'An old visible answer.' not in json.dumps(second)
    for private in ('figuring_out', 'brian@campuslink.test', '2003-06-15', 'dating_genders', 'password_hash'):
        assert private not in json.dumps(second)
    save(b, [])
    b.patch({'interests': []})
    final = starters(a, rid).json()['items']
    assert {item['source'] for item in final} == {'campus'}


def test_reading_starters_never_sends_messages_or_changes_notifications_and_cursors(students, app):
    a, b = students['alice'], students['brian']
    rid = match(a, b)
    before = {table: [dict(row) for row in sql(app, f'SELECT * FROM {table}')]
              for table in ('messages', 'notifications', 'read_cursors', 'events')}
    assert starters(a, rid).json() == starters(a, rid).json()
    assert starters(b, rid).status_code == 200
    for table, rows in before.items():
        assert [dict(row) for row in sql(app, f'SELECT * FROM {table}')] == rows


def test_authentication_membership_and_non_dating_connections_are_enforced(students, app):
    a, b, c = students['alice'], students['brian'], students['chipo']
    rid = match(a, b)
    assert TestClient(app).get(f'/api/chats/{rid}/starters').status_code == 401
    assert starters(c, rid).status_code == 404
    assert starters(a, str(uuid.uuid4())).status_code == 404
    for kind in ('friend', 'study'):
        other_rid = accepted(a, b, kind)
        assert starters(a, other_rid).status_code == 404
        assert starters(b, other_rid).status_code == 404


def test_one_sided_like_and_pending_requests_do_not_expose_starters(students):
    a, b = students['alice'], students['brian']
    for student in (a, b):
        student.patch({'dating_enabled': True})
    assert a.post('/dating/' + b.id + '/like').json() == {'matched': False}
    assert not a.get('/chats').json()['items']
    assert starters(a, b.id).status_code == 404
    rid = a.post('/connections', {'target_id': b.id, 'kind': 'friend'}).json()['id']
    assert starters(a, rid).status_code == 403
    assert starters(b, rid).status_code == 403


@pytest.mark.parametrize('revocation', ['unmatch', 'disable', 'preferences', 'block', 'deactivate', 'suspend'])
def test_starters_stop_when_dating_authorization_is_revoked(students, app, revocation):
    a, b = students['alice'], students['brian']
    rid = match(a, b)
    assert starters(a, rid).status_code == 200
    if revocation == 'unmatch':
        a.post('/connections/' + rid + '/remove')
    elif revocation == 'disable':
        a.patch({'dating_enabled': False})
    elif revocation == 'preferences':
        a.patch({'dating_genders': ['woman']})
    elif revocation == 'block':
        a.post('/blocks/' + b.id)
    elif revocation == 'deactivate':
        sql(app, "UPDATE users SET status='deactivated' WHERE id=?", (a.id,))
    else:
        sql(app, "UPDATE users SET status='suspended' WHERE id=?", (a.id,))
    assert starters(a, rid).status_code in (401, 403, 404)
    assert starters(b, rid).status_code in (401, 403, 404)


def test_accepted_match_retains_starters_when_discovery_is_off(students):
    a, b = students['alice'], students['brian']
    rid = match(a, b)
    a.patch({'discoverable': False})
    b.patch({'discoverable': False})
    assert starters(a, rid).status_code == starters(b, rid).status_code == 200


def test_edited_starter_uses_normal_persistent_duplicate_safe_send(students, app):
    a, b = students['alice'], students['brian']
    rid = match(a, b)
    text = starters(a, rid).json()['items'][0]['text'] + ' My own extra question?'
    key = str(uuid.uuid4())
    sent = message(a, rid, text, key)
    retry = message(a, rid, text, key)
    assert sent.status_code == retry.status_code == 200
    assert sent.json()['message']['id'] == retry.json()['message']['id']
    assert len(sql(app, 'SELECT * FROM messages WHERE relationship_id=?', (rid,))) == 1
    restarted = Student(create_app(app.state.db_path, testing=True), 'brian')
    assert restarted.get(f'/chats/{rid}/messages').json()['items'][0]['body'] == text
    assert starters(restarted, rid).status_code == 200
