from concurrent.futures import ThreadPoolExecutor
import json

import pytest
from fastapi.testclient import TestClient

from campuslink.app import create_app
from campuslink.prompts import PROMPTS
from tests.conftest import Student, accepted, sql
from tests.test_photos import upload


def answer(prompt_id='talk_hours', text='Music, design, and the story behind a good song.'):
    return {'prompt_id': prompt_id, 'answer': text}


def save(student, answers):
    return student.client.put('/api/me/prompts', content=json.dumps({'prompts': answers}), headers={'Content-Type': 'application/json'})


def test_catalog_and_optional_empty_profile(app):
    client = TestClient(app)
    catalog = client.get('/api/catalog').json()
    assert catalog['prompts'] == PROMPTS
    assert catalog['prompt_limits'] == {'count': 3, 'answer': 280}
    a = Student(app, 'alice')
    assert a.get('/me').json()['user']['prompts'] == []
    assert save(a, []).json()['user']['prompts'] == []


def test_edit_order_remove_and_restart_preserve_profile_and_photos(students, app):
    a = students['alice']
    photo = upload(a).json()['user']['main_photo_url']
    bio = a.get('/me').json()['user']['bio']
    values = [answer(), answer('campus_date', '  A walk after class.  '), answer('teach_me', 'Your favourite recipe.')]
    result = save(a, values)
    assert result.status_code == 200
    prompts = result.json()['user']['prompts']
    assert [item['prompt_id'] for item in prompts] == ['talk_hours', 'campus_date', 'teach_me']
    assert prompts[1]['answer'] == 'A walk after class.'
    assert prompts[0]['question'] == PROMPTS[0]['question']
    values = [answer('teach_me', 'A new skill!'), answer('talk_hours', 'Books & music.')]
    assert save(a, values).status_code == 200
    assert save(a, values).status_code == 200  # Repeated complete saves do not duplicate answers.
    restarted = Student(create_app(app.state.db_path, testing=True), 'alice')
    user = restarted.get('/me').json()['user']
    assert [{key: item[key] for key in ('prompt_id', 'answer')} for item in user['prompts']] == values
    assert user['bio'] == bio and user['main_photo_url'] == photo
    assert len(sql(app, 'SELECT * FROM profile_prompts WHERE user_id=?', (a.id,))) == 2
    assert save(a, []).status_code == 200
    assert not a.get('/me').json()['user']['prompts']


@pytest.mark.parametrize('values', [
    None, {}, 'hello', [None], [answer()] * 4,
    [answer(), answer()], [answer('unknown')], [answer(['talk_hours'])],
    [answer(text='')], [answer(text=' \n\t ')], [answer(text='x' * 281)],
    [answer(text=42)], [answer(text='hello\x00there')], [answer(text='\ud800')],
    [{'prompt_id': 'talk_hours'}], [dict(answer(), question='Spoofed question')],
])
def test_invalid_replacements_leave_saved_answers_untouched(app, values):
    a = Student(app, 'alice')
    original = save(a, [answer()]).json()['user']['prompts']
    response = save(a, values)
    assert response.status_code == 422, response.text
    assert a.get('/me').json()['user']['prompts'] == original


def test_plain_text_unicode_and_maximum_length(students):
    a, b = students['alice'], students['brian']
    values = [answer(text='🌻' * 280), answer('small_joy', '<img src=x onerror="alert(1)">\nBooks & friends.')]
    assert save(a, values).status_code == 200
    profile = b.get('/profiles/' + a.id).json()['profile']
    assert profile['prompts'][0]['answer'] == '🌻' * 280
    assert profile['prompts'][1]['answer'] == values[1]['answer']
    assert 'email' not in profile and 'dob' not in profile and 'csrf' not in profile


def test_authentication_csrf_and_owner_scope(students, app):
    a, b = students['alice'], students['brian']
    assert TestClient(app).put('/api/me/prompts', json={'prompts': []}).status_code == 401
    assert a.client.put('/api/me/prompts', json={'prompts': [answer()]}, headers={'X-CSRF-Token': 'wrong'}).status_code == 403
    response = a.client.put('/api/me/prompts', json={'user_id': b.id, 'prompts': [answer()]})
    assert response.status_code == 200
    assert not b.get('/me').json()['user']['prompts']
    assert a.get('/me').json()['user']['prompts']


def test_discovery_full_profiles_and_accepted_hidden_profile_share_rules(students):
    a, b, c = students['alice'], students['brian'], students['chipo']
    prompts = save(a, [answer()]).json()['user']['prompts']
    assert b.get('/discover', params={'mode': 'friend', 'q': 'alice'}).json()['items'][0]['prompts'] == prompts
    a.patch({'discoverable': False})
    assert b.get('/profiles/' + a.id).status_code == 404
    assert not b.get('/discover', params={'q': 'alice'}).json()['items']
    a.patch({'discoverable': True})
    accepted(a, b)
    a.patch({'discoverable': False})
    assert b.get('/profiles/' + a.id).json()['profile']['prompts'] == prompts
    assert b.get('/connections').json()['items'][0]['profile']['prompts'] == prompts
    assert b.get('/chats').json()['items'][0]['profile']['prompts'] == prompts
    assert c.get('/profiles/' + a.id).status_code == 404
    b.post('/blocks/' + a.id)
    assert b.get('/profiles/' + a.id).status_code == 404
    assert a.get('/profiles/' + b.id).status_code == 404
    assert not b.get('/chats').json()['items']
    assert a.get('/me').json()['user']['prompts'] == prompts


def test_dating_only_prompts_require_eligibility_and_campus_scope(students, app):
    a, b = students['alice'], students['brian']
    for student in (a, b):
        assert student.patch({'friend_goal': False, 'study_goal': False, 'dating_enabled': True}).status_code == 200
    prompts = save(a, [answer('campus_date', 'Coffee and a long conversation.')]).json()['user']['prompts']
    assert b.get('/discover', params={'mode': 'dating', 'q': 'alice'}).json()['items'][0]['prompts'] == prompts
    assert b.get('/profiles/' + a.id).json()['profile']['prompts'] == prompts
    b.patch({'dating_genders': ['man']})
    assert b.get('/profiles/' + a.id).status_code == 404
    b.patch({'dating_genders': ['woman']})
    a.patch({'dating_enabled': False})
    assert b.get('/profiles/' + a.id).status_code == 404
    a.patch({'friend_goal': True})
    b.patch({'friend_goal': True})
    sql(app, "INSERT INTO institutions VALUES ('other','Other campus')")
    sql(app, "UPDATE users SET institution_id='other' WHERE id=?", (a.id,))
    assert b.get('/profiles/' + a.id).status_code == 404
    sql(app, "UPDATE users SET institution_id='zut',status='suspended' WHERE id=?", (a.id,))
    assert b.get('/profiles/' + a.id).status_code == 404
    assert save(a, []).status_code == 401


def test_concurrent_saves_are_complete_atomic_sets(students, app):
    a = students['alice']
    first = [answer('talk_hours', 'First set.'), answer('campus_date', 'First date.')]
    second = [answer('teach_me', 'Second set.'), answer('small_joy', 'Second joy.'), answer('green_flag', 'Kindness.')]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result() for future in [pool.submit(save, a, first), pool.submit(save, a, second)]]
    assert all(result.status_code == 200 for result in results)
    rows = sql(app, 'SELECT prompt_id,answer FROM profile_prompts WHERE user_id=? ORDER BY position', (a.id,))
    assert [dict(row) for row in rows] in (first, second)


def test_upgrade_from_version_two_preserves_accounts_photos_and_sessions(students, app):
    a = students['alice']
    photo = upload(a).json()['user']['main_photo_url']
    before = sql(app, 'SELECT id,username FROM users ORDER BY id')
    sql(app, 'DROP TABLE profile_prompts')
    sql(app, 'PRAGMA user_version=2')
    upgraded = create_app(app.state.db_path, testing=True)
    assert sql(app, 'PRAGMA user_version')[0][0] == 5
    assert sql(app, 'SELECT id,username FROM users ORDER BY id') == before
    client = TestClient(upgraded)
    client.cookies.update(a.client.cookies)
    user = client.get('/api/me').json()['user']
    assert user['main_photo_url'] == photo and user['prompts'] == []
    assert client.get(photo).status_code == 200


def test_deactivation_hides_answers_and_deletion_cascades(students, app):
    a, b, c = students['alice'], students['brian'], students['chipo']
    for student in (a, c):
        assert save(student, [answer()]).status_code == 200
    from campuslink.seed import PASSWORD
    assert a.post('/account/deactivate', {'password': PASSWORD}).status_code == 200
    assert b.get('/profiles/' + a.id).status_code == 404
    assert save(a, []).status_code == 401
    assert len(sql(app, 'SELECT * FROM profile_prompts WHERE user_id=?', (a.id,))) == 1
    assert c.post('/account/delete', {'password': PASSWORD}).status_code == 200
    assert not sql(app, 'SELECT * FROM profile_prompts WHERE user_id=?', (c.id,))
