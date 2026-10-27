from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import uuid

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from campuslink.app import create_app
from campuslink.photos import MAX_UPLOAD_BYTES
from .conftest import Student, accepted, sql
from .test_photos import image_bytes


def photo(student, content=None, key=None):
    return student.client.post('/api/me/post-photos', content=image_bytes(metadata=True) if content is None else content,
                               headers={'Content-Type': 'image/png', 'X-Upload-Id': key or str(uuid.uuid4())})


def post(student, body='A day on campus', photo_id='', key=None):
    return student.post('/posts', {'body': body, 'photo_id': photo_id, 'client_id': key or str(uuid.uuid4())})


def comment(a, b, body='A private hello', key=None, **extra):
    return a.post('/message-requests', {'target_id': b.id, 'body': body, 'client_id': key or str(uuid.uuid4()), **extra})


def test_photo_post_persists_and_retry_cannot_duplicate(students, app):
    a, b = students['alice'], students['brian']
    upload_key, post_key = str(uuid.uuid4()), str(uuid.uuid4())
    raw = image_bytes(size=(1800, 2400), metadata=True)
    first = photo(a, raw, upload_key)
    assert first.status_code == 200, first.text
    pid = first.json()['photo_id']
    assert photo(a, raw, upload_key).json()['photo_id'] == pid
    assert photo(a, image_bytes('blue'), upload_key).status_code == 409
    url = '/post-photos/' + pid
    assert b.get(url).status_code == 404  # Staged photos remain private.
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: post(a, '<script>plain text</script>', pid, post_key), range(2)))
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    post_id = responses[0].json()['post']['id']
    assert responses[1].json()['post']['id'] == post_id
    assert len(sql(app, 'SELECT * FROM posts')) == 1
    assert post(a, 'Different content', pid, post_key).status_code == 409
    assert post(a, 'Reuse a published photo', pid).status_code == 409
    viewed = b.get(url)
    assert viewed.status_code == 200 and viewed.headers['cache-control'] == 'no-store'
    with Image.open(BytesIO(viewed.content)) as processed:
        assert processed.format == 'JPEG' and max(processed.size) <= 1200
        assert not processed.getexif() and 'GPSLatitude' not in processed.info
    recreated = create_app(app.state.db_path, testing=True)
    fresh = Student(recreated, 'alice')
    assert fresh.get('/feed').json()['items'][0]['id'] == post_id
    assert fresh.get(url).content == viewed.content


@pytest.mark.parametrize('content', [b'not an image', b'<svg xmlns="http://www.w3.org/2000/svg"/>', image_bytes(size=(20,20))])
def test_bad_post_photos_rejected(students, content):
    assert photo(students['alice'], content).status_code == 422


def test_post_permissions_likes_edit_delete_and_cascade(students, app):
    a, b, c = students['alice'], students['brian'], students['chipo']
    pid = photo(a).json()['photo_id']
    row = post(a, photo_id=pid).json()['post']
    post_id = row['id']
    path = f'/posts/{post_id}'
    assert b.client.patch('/api' + path, json={'body':'Not mine'}).status_code == 403
    assert b.client.delete('/api' + path).status_code == 403
    assert post(b, photo_id=pid).status_code == 409
    for _ in range(2):
        r = b.client.put('/api' + path + '/like', json={'liked': True})
        assert r.status_code == 200 and r.json()['post']['like_count'] == 1
    assert [p['id'] for p in c.get(path + '/likes').json()['items']] == [b.id]
    assert b.client.put('/api' + path + '/like', json={'liked': 'yes'}).status_code == 422
    assert a.client.patch('/api' + path, json={'body':'Updated caption'}).json()['post']['body'] == 'Updated caption'
    assert a.client.delete('/api/me/post-photos/' + pid).status_code == 409
    assert a.client.delete('/api' + path).status_code == 200
    assert not sql(app, 'SELECT * FROM post_photos') and not sql(app, 'SELECT * FROM post_likes')
    assert b.get('/post-photos/' + pid).status_code == 404


def test_posts_visibility_blocks_campus_and_pagination(students, app):
    a, b = students['alice'], students['brian']
    photo_id = photo(a).json()['photo_id']
    row = post(a, photo_id=photo_id).json()['post']
    assert b.get('/feed').json()['items'][0]['id'] == row['id']
    a.patch({'discoverable':False})
    assert b.get('/feed').json()['items'] == []
    assert b.get('/post-photos/' + photo_id).status_code == 404
    a.patch({'discoverable':True})
    accepted(a, b)
    a.patch({'discoverable':False})
    assert b.get('/post-photos/' + photo_id).status_code == 200
    b.post('/blocks/' + a.id)
    assert b.get('/feed').json()['items'] == []
    assert b.get('/post-photos/' + photo_id).status_code == 404
    assert a.get('/feed?student=' + b.id).status_code == 404
    sql(app, 'INSERT INTO institutions VALUES ("other","Other Campus")')
    sql(app, 'UPDATE users SET institution_id="other" WHERE id=?', (b.id,))
    assert b.get('/feed').json()['items'] == []
    for n in range(24):
        sql(app, 'INSERT INTO posts(user_id,client_id,body,created_at,updated_at) VALUES (?,?,?,?,?)', (a.id,str(uuid.uuid4()),f'post {n}',n,n))
    first = a.get('/feed').json()
    assert len(first['items']) == 20 and first['has_more']
    second = a.get('/feed?before=' + str(first['next_before'])).json()
    assert len(second['items']) == 5 and not second['has_more']
    assert not {p['id'] for p in first['items']} & {p['id'] for p in second['items']}


def test_public_profile_likes_and_legacy_private_likes_stay_separate(students, app):
    a, b, c = students['alice'], students['brian'], students['chipo']
    assert a.post('/profiles/' + b.id + '/like').status_code == 200
    assert a.post('/profiles/' + b.id + '/like').status_code == 200
    assert [p['id'] for p in c.get('/profiles/' + b.id + '/likes').json()['items']] == [a.id]
    assert b.get('/profiles/' + b.id + '?context=campus').json()['profile']['like_count'] == 1
    assert len(sql(app, 'SELECT * FROM profile_likes')) == 1
    assert not sql(app, 'SELECT * FROM dating_likes')
    a.client.delete('/api/profiles/' + b.id + '/like')
    assert c.get('/profiles/' + b.id + '/likes').json()['items'] == []
    assert a.post('/profiles/' + a.id + '/like').status_code == 422
    sql(app, 'INSERT INTO dating_likes VALUES (?,?)', (c.id, b.id))
    assert b.get('/profiles/' + b.id + '/likes').json()['items'] == []
    a.post('/blocks/' + b.id)
    assert a.post('/profiles/' + b.id + '/like').status_code == 404


def test_public_dating_likes_match_once_and_unlike_does_not_end_chat(students, app):
    a, b, c = students['alice'], students['brian'], students['chipo']
    for student, gender, interested in ((a, 'woman', 'man'), (b, 'man', 'woman')):
        assert student.patch({'dating_enabled':True, 'gender':gender, 'dating_genders':[interested]}).status_code == 200
    assert a.post('/profiles/' + b.id + '/like', {'context':'dating'}).json()['matched'] is False
    assert c.get('/profiles/' + b.id + '/likes').json()['items'][0]['id'] == a.id
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: b.post('/profiles/' + a.id + '/like', {'context':'dating'}), range(2)))
    assert all(r.status_code == 200 and r.json()['matched'] for r in results)
    assert len(sql(app, 'SELECT * FROM relationships')) == 1
    rid = results[0].json()['id']
    a.client.delete('/api/profiles/' + b.id + '/like')
    assert a.get('/chats/' + rid + '/messages').status_code == 200
    assert b.get('/profiles/' + b.id + '/likes').json()['items'] == []


def test_private_dating_comment_acceptance_obeys_eligibility_and_deactivation(students):
    a, b = students['alice'], students['brian']
    assert comment(a, b, kind='dating').status_code == 403
    for student, gender, interested in ((a, 'woman', 'man'), (b, 'man', 'woman')):
        student.patch({'dating_enabled':True, 'gender':gender, 'dating_genders':[interested]})
    reqid = comment(a, b, kind='dating').json()['id']
    a.patch({'dating_enabled':False})
    assert b.post('/message-requests/' + reqid + '/accept').status_code == 403
    a.patch({'dating_enabled':True})
    r = b.post('/message-requests/' + reqid + '/accept')
    assert r.status_code == 200, r.text
    rid = r.json()['conversation_id']
    assert a.get('/chats').json()['items'][0]['kind'] == 'dating'
    a.patch({'dating_enabled':False})
    assert b.get('/chats/' + rid + '/messages').status_code == 403


def test_private_comment_only_visible_to_participants_and_acceptance_is_atomic(students, app):
    a, b, c = students['alice'], students['brian'], students['chipo']
    key = str(uuid.uuid4())
    r = comment(a, b, key=key)
    assert r.status_code == 200, r.text
    reqid = r.json()['id']
    assert comment(a, b, key=key).json()['id'] == reqid
    assert comment(a, b, body='A second unwanted request').status_code == 409
    assert len(sql(app, 'SELECT * FROM message_requests')) == 1
    assert not sql(app, 'SELECT * FROM messages')
    assert c.get('/message-requests').json()['items'] == []
    assert a.get('/message-requests').json()['items'][0]['direction'] == 'sent'
    assert b.get('/message-requests').json()['items'][0]['body'] == 'A private hello'
    assert c.post('/message-requests/' + reqid + '/accept').status_code == 404
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: b.post('/message-requests/' + reqid + '/accept'), range(2)))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    rid = results[0].json()['conversation_id']
    assert results[1].json()['conversation_id'] == rid
    assert len(sql(app, 'SELECT * FROM messages')) == 1
    assert len(sql(app, 'SELECT * FROM relationships')) == 1
    assert a.get('/chats/' + rid + '/messages').json()['items'][0]['body'] == 'A private hello'
    assert c.get('/chats/' + rid + '/messages').status_code == 404
    assert b.get('/message-requests').json()['items'] == []


def test_decline_and_block_do_not_allow_repeated_or_accepted_requests(students):
    a, b, c = students['alice'], students['brian'], students['chipo']
    reqid = comment(a, b).json()['id']
    assert b.post('/message-requests/' + reqid + '/decline').status_code == 200
    assert b.post('/message-requests/' + reqid + '/accept').status_code == 409
    assert comment(a, b).status_code == 409
    assert b.get('/chats').json()['items'] == []
    reqid = comment(c, b).json()['id']
    b.post('/blocks/' + c.id)
    assert b.get('/message-requests').json()['items'] == []
    assert b.post('/message-requests/' + reqid + '/accept').status_code == 404
    assert comment(c, b).status_code == 404


def test_private_post_comment_has_no_public_comment_api(students, app):
    a, b, c = students['alice'], students['brian'], students['chipo']
    row = post(a).json()['post']
    req = comment(b, a, body='Private comment about your photo', post_id=row['id'])
    assert req.status_code == 200
    assert a.get('/message-requests').json()['items'][0]['post_id'] == row['id']
    public = c.get('/feed').json()['items'][0]
    assert 'comment' not in str(public).lower()
    assert c.get(f'/posts/{row["id"]}/comments').status_code == 404
    assert comment(b, c, post_id=row['id']).status_code == 422
    assert a.client.delete(f'/api/posts/{row["id"]}').status_code == 200
    assert a.get('/message-requests').json()['items'][0]['post_id'] is None


def test_receipts_require_recipient_ack_and_remain_monotonic_after_restart(students, app):
    a, b, c = students['alice'], students['brian'], students['chipo']
    rid = accepted(a, b)
    msg = a.post('/chats/' + rid + '/messages', {'body':'Receipt test','client_id':str(uuid.uuid4())}).json()['message']
    mid = msg['id']
    assert a.get('/chats').json()['items'][0]['receipts'] == {'delivered':0,'read':0}
    # Merely fetching the inbox/history is not an acknowledgement.
    b.get('/chats'); b.get('/chats/' + rid + '/messages')
    assert a.get('/chats').json()['items'][0]['receipts'] == {'delivered':0,'read':0}
    assert c.post('/chats/' + rid + '/read', {'message_id':mid}).status_code == 404
    assert b.post('/chats/' + rid + '/delivered', {'message_id':mid+1000}).status_code == 404
    assert b.post('/chats/' + rid + '/delivered', {'message_id':mid}).status_code == 200
    assert a.get('/chats/' + rid + '/messages').json()['receipts'] == {'delivered':mid,'read':0}
    b.post('/chats/' + rid + '/read', {'message_id':mid})
    event_count = len(sql(app, 'SELECT * FROM events'))
    b.post('/chats/' + rid + '/read', {'message_id':mid})
    b.post('/chats/' + rid + '/read', {'message_id':0})
    assert len(sql(app, 'SELECT * FROM events')) == event_count
    recreated = create_app(app.state.db_path, testing=True)
    fresh = Student(recreated, 'alice')
    assert fresh.get('/chats').json()['items'][0]['receipts'] == {'delivered':mid,'read':mid}
    b.post('/blocks/' + a.id)
    assert a.post('/chats/' + rid + '/delivered', {'message_id':mid}).status_code == 403


def test_csrf_and_unauthenticated_social_actions_fail(students, app):
    a, b = students['alice'], students['brian']
    client = TestClient(app)
    assert client.get('/api/feed').status_code == 401
    assert client.post('/api/posts', json={'body':'hello','client_id':str(uuid.uuid4())}).status_code == 401
    a.client.headers.pop('X-CSRF-Token')
    assert post(a).status_code == 403
    assert photo(a).status_code == 403
    assert comment(a, b).status_code == 403


def test_accounts_on_same_wifi_have_independent_api_budgets(students, app):
    a, b = students['alice'], students['brian']
    assert a.get('/feed').status_code == b.get('/feed').status_code == 200
    sql(app, 'UPDATE rate_limits SET count=600 WHERE key=?', ('api:user:' + a.id,))
    assert a.get('/feed').status_code == 429
    assert b.get('/feed').status_code == 200
    anonymous = TestClient(app)
    assert anonymous.get('/api/catalog').status_code == 200
    sql(app, 'UPDATE rate_limits SET count=600 WHERE key="api:anonymous:testclient"')
    assert anonymous.get('/api/catalog').status_code == 429
    assert b.get('/feed').status_code == 200
    sql(app, 'UPDATE rate_limits SET count=6000 WHERE key="ip:testclient"')
    response = b.get('/feed')
    assert response.status_code == 429 and response.headers['Retry-After'] == '60'


def test_version_four_upgrade_preserves_private_data(students, app):
    a, b = students['alice'], students['brian']
    rid = accepted(a, b)
    a.post('/chats/' + rid + '/messages', {'body':'Keep this','client_id':str(uuid.uuid4())})
    sql(app, 'INSERT INTO dating_likes VALUES (?,?)', (a.id, b.id))
    for table in ('message_requests','post_likes','posts','post_photos','profile_likes','delivery_cursors'):
        sql(app, 'DROP TABLE ' + table)
    sql(app, 'PRAGMA user_version=4')
    upgraded = create_app(app.state.db_path, testing=True)
    client = TestClient(upgraded)
    client.cookies.update(a.client.cookies)
    assert client.get('/api/me').status_code == 200
    assert client.get('/api/chats/' + rid + '/messages').json()['items'][0]['body'] == 'Keep this'
    assert not sql(app, 'SELECT * FROM profile_likes')
    assert len(sql(app, 'SELECT * FROM dating_likes')) == 1
    assert sql(app, 'PRAGMA user_version')[0][0] == 6
