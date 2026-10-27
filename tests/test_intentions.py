import pytest
from fastapi.testclient import TestClient

from campuslink.app import create_app
from campuslink.intentions import INTENTIONS
from campuslink.seed import PASSWORD
from tests.conftest import Student, accepted, sql
from tests.test_photos import upload
from tests.test_prompts import answer, save


def activate(*students):
    for student in students:
        assert student.patch({'dating_enabled': True}).status_code == 200


def choose(student, intention='relationship', displayed=True):
    return student.patch({'dating_intention': intention, 'show_dating_intention': displayed})


def profile(student, target, context='general'):
    return student.get('/profiles/' + target.id, params={'context': context})


def discover(student, target, **filters):
    return student.get('/discover', params={'mode': 'dating', 'q': target.user['username'], **filters})


def no_intention(projection):
    assert not any(key.startswith('dating_intention') or key == 'show_dating_intention' for key in projection)


def match(a, b):
    activate(a, b)
    assert a.post('/dating/' + b.id + '/like').json()['matched'] is False
    result = b.post('/dating/' + a.id + '/like')
    assert result.json()['matched'] is True
    return result.json()['id']


def test_catalog_unset_and_private_default(app):
    assert TestClient(app).get('/api/catalog').json()['dating_intentions'] == INTENTIONS
    a = Student(app, 'alice')
    user = a.get('/me').json()['user']
    assert user['dating_intention'] == '' and user['show_dating_intention'] is False
    assert a.patch({'dating_intention': 'relationship'}).status_code == 200
    user = a.get('/me').json()['user']
    assert user['dating_intention'] == 'relationship' and user['show_dating_intention'] is False
    assert user['dating_enabled'] == 0  # An intention never opts anyone into Dating.


@pytest.mark.parametrize('choice', INTENTIONS, ids=lambda item: item['id'])
def test_each_label_and_discovery_filter_match_the_saved_choice(students, choice):
    a, b = students['alice'], students['brian']
    activate(a, b)
    assert choose(a, choice['id']).status_code == 200
    result = discover(b, a, intention=choice['id']).json()['items']
    assert len(result) == 1
    assert result[0]['dating_intention'] == choice['id']
    assert result[0]['dating_intention_label'] == choice['label']
    assert profile(b, a, 'dating').json()['profile']['dating_intention_label'] == choice['label']


def test_edit_hide_remove_retry_and_restart(students, app):
    a, b = students['alice'], students['brian']
    activate(a, b)
    choose(a)
    assert choose(a, 'getting_to_know').status_code == 200
    assert choose(a, 'getting_to_know').status_code == 200
    assert len(sql(app, 'SELECT * FROM dating_intentions WHERE user_id=?', (a.id,))) == 1
    assert a.patch({'bio': 'Independent profile edit.'}).status_code == 200
    assert a.get('/me').json()['user']['dating_intention'] == 'getting_to_know'
    assert a.patch({'show_dating_intention': False}).status_code == 200
    hidden = a.get('/me').json()['user']
    assert hidden['dating_intention'] == 'getting_to_know' and hidden['show_dating_intention'] is False
    no_intention(profile(b, a, 'dating').json()['profile'])
    restarted = Student(create_app(app.state.db_path, testing=True), 'alice')
    assert restarted.get('/me').json()['user']['dating_intention'] == 'getting_to_know'
    assert restarted.patch({'show_dating_intention': True}).status_code == 200
    assert profile(b, a, 'dating').json()['profile']['dating_intention'] == 'getting_to_know'
    assert a.patch({'dating_intention': ''}).status_code == 200
    cleared = a.get('/me').json()['user']
    assert cleared['dating_intention'] == '' and cleared['show_dating_intention'] is False
    assert not sql(app, 'SELECT * FROM dating_intentions WHERE user_id=?', (a.id,))
    no_intention(profile(b, a, 'dating').json()['profile'])


def test_unfiltered_discovery_includes_unset_and_hidden_without_filtering_private_values(students):
    a, b = students['alice'], students['brian']
    activate(a, b)
    assert len(discover(b, a).json()['items']) == 1
    assert discover(b, a, intention='relationship').json()['items'] == []
    choose(a, displayed=False)
    no_intention(discover(b, a).json()['items'][0])
    assert discover(b, a, intention='relationship').json()['items'] == []
    choose(a, 'figuring_out', displayed=False)
    assert discover(b, a, intention='figuring_out').json()['items'] == []
    assert len(discover(b, a).json()['items']) == 1
    choose(a, 'figuring_out')
    assert len(discover(b, a, intention='figuring_out').json()['items']) == 1
    assert discover(b, a, intention='relationship').json()['items'] == []
    assert discover(b, a, intention='figuring_out', program='Not a program').json()['items'] == []


def test_general_friend_study_discovery_profiles_connections_and_chats_omit_intentions(students):
    a, b = students['alice'], students['brian']
    activate(a, b)
    choose(a)
    for context in ('general', 'friend', 'study'):
        no_intention(profile(b, a, context).json()['profile'])
    for mode in ('for-you', 'friend', 'study'):
        result = b.get('/discover', params={'mode': mode, 'q': 'alice'}).json()['items']
        assert len(result) == 1
        no_intention(result[0])
    accepted(a, b, 'friend')
    accepted(a, b, 'study')
    match(a, b)
    for endpoint in ('/connections', '/chats'):
        items = b.get(endpoint).json()['items']
        assert {item['kind'] for item in items} == {'friend', 'study', 'dating'}
        for item in items:
            if item['kind'] == 'dating':
                assert item['profile']['dating_intention'] == 'relationship'
            else:
                no_intention(item['profile'])
    no_intention(profile(b, a).json()['profile'])


def test_dating_context_cannot_be_forged_through_friend_access(students):
    a, b = students['alice'], students['brian']
    choose(a)
    accepted(a, b)
    assert profile(b, a).status_code == 200
    assert profile(b, a, 'dating').status_code == 404
    activate(a, b)
    a.patch({'discoverable': False})
    assert profile(b, a).status_code == 200
    assert profile(b, a, 'dating').status_code == 404
    no_intention(profile(b, a).json()['profile'])
    assert profile(b, a, '<script>').status_code == 422


def test_dating_context_matches_visibility_and_consent_revocation(students):
    a, b = students['alice'], students['brian']
    choose(a)
    rid = match(a, b)
    a.patch({'discoverable': False})
    assert profile(b, a, 'dating').json()['profile']['dating_intention'] == 'relationship'
    assert b.post('/connections/' + rid + '/remove').status_code == 200
    assert profile(b, a, 'dating').status_code == 404
    a.patch({'discoverable': True})
    assert profile(b, a, 'dating').status_code == 200
    a.patch({'dating_enabled': False})
    assert profile(b, a, 'dating').status_code == 404
    assert b.get('/connections').json()['items'] == []
    assert b.get('/chats').json()['items'] == []
    assert a.get('/me').json()['user']['dating_intention'] == 'relationship'


def test_filters_and_dating_views_cannot_bypass_eligibility_blocks_or_scope(students, app):
    a, b = students['alice'], students['brian']
    activate(a, b)
    choose(a)
    for change, reset in [({'dating_genders': ['man']}, {'dating_genders': ['woman']}),
                          ({'dating_min': 40}, {'dating_min': 18})]:
        assert b.patch(change).status_code == 200
        assert profile(b, a, 'dating').status_code == 404
        assert discover(b, a, intention='relationship').json()['items'] == []
        b.patch(reset)
    b.post('/blocks/' + a.id)
    assert profile(b, a, 'dating').status_code == 404
    assert profile(a, b, 'dating').status_code == 404
    assert discover(b, a, intention='relationship').json()['items'] == []
    b.client.delete('/api/blocks/' + a.id)
    sql(app, "INSERT INTO institutions VALUES ('other','Other campus')")
    sql(app, "UPDATE users SET institution_id='other' WHERE id=?", (a.id,))
    assert profile(b, a, 'dating').status_code == 404
    assert discover(b, a, intention='relationship').json()['items'] == []
    sql(app, "UPDATE users SET institution_id='zut',adult_test=0 WHERE id=?", (a.id,))
    assert profile(b, a, 'dating').status_code == 404
    assert discover(b, a, intention='relationship').json()['items'] == []


@pytest.mark.parametrize('payload', [
    {'dating_intention': 'unknown'}, {'dating_intention': None}, {'dating_intention': []},
    {'show_dating_intention': 'true'}, {'show_dating_intention': 1},
    {'dating_intention': '', 'show_dating_intention': True},
])
def test_invalid_settings_roll_back_profile_and_intention_changes(app, payload):
    a = Student(app, 'alice')
    choose(a)
    original = a.get('/me').json()['user']
    result = a.patch({'bio': 'Must roll back.', **payload})
    assert result.status_code == 422
    after = a.get('/me').json()['user']
    assert after['bio'] == original['bio']
    assert after['dating_intention'] == 'relationship' and after['show_dating_intention'] is True


def test_auth_csrf_filter_validation_and_owner_scope(students, app):
    a, b = students['alice'], students['brian']
    payload = {'dating_intention': 'relationship', 'show_dating_intention': True}
    assert TestClient(app).patch('/api/me', json=payload).status_code == 401
    assert a.client.patch('/api/me', json=payload, headers={'X-CSRF-Token': 'wrong'}).status_code == 403
    assert a.patch({'user_id': b.id, **payload}).status_code == 200
    assert b.get('/me').json()['user']['dating_intention'] == ''
    activate(a, b)
    assert discover(b, a, intention='unknown').status_code == 422
    for mode in ('for-you', 'friend', 'study'):
        assert b.get('/discover', params={'mode': mode, 'intention': 'relationship'}).status_code == 422


def test_deactivation_and_delete_hide_or_remove_intentions(students, app):
    a, b, c = students['alice'], students['brian'], students['chipo']
    activate(a, b)
    choose(a)
    choose(c)
    assert a.post('/account/deactivate', {'password': PASSWORD}).status_code == 200
    assert profile(b, a, 'dating').status_code == 404
    assert discover(b, a).json()['items'] == []
    assert len(sql(app, 'SELECT * FROM dating_intentions WHERE user_id=?', (a.id,))) == 1
    assert c.post('/account/delete', {'password': PASSWORD}).status_code == 200
    assert not sql(app, 'SELECT * FROM dating_intentions WHERE user_id=?', (c.id,))


def test_version_three_upgrade_preserves_photos_prompts_users_and_sessions(students, app):
    a = students['alice']
    photo = upload(a).json()['user']['main_photo_url']
    prompts = save(a, [answer()]).json()['user']['prompts']
    accounts = sql(app, 'SELECT id,username FROM users ORDER BY id')
    sql(app, 'DROP TABLE dating_intentions')
    sql(app, 'PRAGMA user_version=3')
    upgraded = create_app(app.state.db_path, testing=True)
    client = TestClient(upgraded)
    client.cookies.update(a.client.cookies)
    user = client.get('/api/me').json()['user']
    assert user['prompts'] == prompts and user['main_photo_url'] == photo
    assert client.get(photo).status_code == 200
    assert user['dating_intention'] == '' and user['show_dating_intention'] is False
    assert sql(app, 'SELECT id,username FROM users ORDER BY id') == accounts
    assert sql(app, 'PRAGMA user_version')[0][0] == 6
