"""Campus posts, public reactions and recipient-controlled private comments."""
import asyncio
import hashlib
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import Response

from .photos import PhotoError, process_photo


def install_social(app, *, db, auth, payload, text, number, fail, now, limit, emit,
                   notify, public, get_user, blocked, campus_access, pair,
                   authorized_relation, dating_compatible, like_dating):
    def request_peers(con, user, row):
        if user['id'] not in (row['sender'], row['target']):
            fail('Request unavailable.', 404)
        sender, target = get_user(con, row['sender']), get_user(con, row['target'])
        if sender['institution_id'] != target['institution_id'] or blocked(con, sender['id'], target['id']):
            fail('Request unavailable.', 404)
        return sender, target

    def post_access(con, user, pid):
        row = con.execute('SELECT * FROM posts WHERE id=?', (pid,)).fetchone()
        if not row:
            fail('Post unavailable.', 404)
        campus_access(con, user, get_user(con, row['user_id']))
        return row

    def visible_reactions(con, user, rows):
        items = []
        for row in rows:
            try:
                person = get_user(con, row[0])
                campus_access(con, user, person)
            except HTTPException:
                continue
            items.append(public(con, person))
        return items

    def post_json(con, user, row):
        likes = visible_reactions(con, user, con.execute(
            'SELECT user_id FROM post_likes WHERE post_id=? ORDER BY created_at,user_id', (row['id'],)))
        return {'id': row['id'], 'body': row['body'], 'created_at': row['created_at'],
                'updated_at': row['updated_at'], 'author': public(con, get_user(con, row['user_id'])),
                'photo_url': f'/api/post-photos/{row["photo_id"]}' if row['photo_id'] else None,
                'like_count': len(likes), 'liked': any(p['id'] == user['id'] for p in likes),
                'mine': row['user_id'] == user['id']}

    @app.get('/api/feed')
    def feed(request: Request, before: int = 0, student: str = ''):
        if before < 0:
            fail('Invalid post cursor.', 422)
        with db() as con:
            user, _ = auth(con, request)
            if student:
                campus_access(con, user, get_user(con, student))
            # Keyset pagination counts only posts this viewer may actually see.
            rows = con.execute('SELECT p.* FROM posts p JOIN users u ON u.id=p.user_id '
                               'WHERE p.id<? AND u.institution_id=? AND u.status="active" '
                               'AND (?="" OR p.user_id=?) ORDER BY p.id DESC',
                               (before or 9223372036854775807, user['institution_id'], student, student))
            items = []
            for row in rows:
                try:
                    campus_access(con, user, get_user(con, row['user_id']))
                except HTTPException:
                    continue
                items.append(post_json(con, user, row))
                if len(items) == 21:
                    break
            return {'items': items[:20], 'has_more': len(items) > 20,
                    'next_before': items[19]['id'] if len(items) > 20 else None}

    @app.post('/api/me/post-photos')
    async def upload_post_photo(request: Request):
        key = request.headers.get('x-upload-id', '')
        if not 8 <= len(key) <= 64:
            fail('A valid upload ID is required.', 422)
        content = await request.body()
        digest = hashlib.sha256(content).hexdigest()
        try:
            image = await asyncio.to_thread(process_photo, content)
        except PhotoError as exc:
            fail(str(exc), 422)
        with db(True) as con:
            user, _ = auth(con, request)
            campus_access(con, user, user)
            existing = con.execute('SELECT id,upload_hash FROM post_photos WHERE user_id=? AND upload_key=?',
                                   (user['id'], key)).fetchone()
            if existing:
                if existing['upload_hash'] != digest:
                    fail('This upload ID belongs to another photo.', 409)
                return {'photo_id': existing['id']}
            con.execute('DELETE FROM post_photos WHERE created_at<? AND id NOT IN '
                        '(SELECT photo_id FROM posts WHERE photo_id IS NOT NULL)', (now() - 86400,))
            staged = con.execute('SELECT count(*) FROM post_photos WHERE user_id=? AND id NOT IN '
                                 '(SELECT photo_id FROM posts WHERE photo_id IS NOT NULL)', (user['id'],)).fetchone()[0]
            if staged >= 4:
                fail('Publish or remove your pending photos first.', 409)
            pid = str(uuid.uuid4())
            con.execute('INSERT INTO post_photos VALUES (?,?,?,?,?,?,?,?)',
                        (pid, user['id'], image.data, image.width, image.height, key, digest, now()))
            return {'photo_id': pid}

    @app.delete('/api/me/post-photos/{pid}')
    def remove_post_photo(pid: str, request: Request):
        with db(True) as con:
            user, _ = auth(con, request)
            if con.execute('SELECT 1 FROM posts WHERE photo_id=?', (pid,)).fetchone():
                fail('Remove the published post to remove its photo.', 409)
            con.execute('DELETE FROM post_photos WHERE id=? AND user_id=?', (pid, user['id']))
            return {'ok': True}

    @app.get('/api/post-photos/{pid}')
    def post_photo(pid: str, request: Request):
        with db() as con:
            user, _ = auth(con, request)
            image = con.execute('SELECT * FROM post_photos WHERE id=?', (pid,)).fetchone()
            if not image:
                fail('Photo unavailable.', 404)
            row = con.execute('SELECT id FROM posts WHERE photo_id=?', (pid,)).fetchone()
            if row:
                post_access(con, user, row['id'])
            elif image['user_id'] != user['id']:
                fail('Photo unavailable.', 404)
            return Response(bytes(image['image']), media_type='image/jpeg', headers={'Cache-Control': 'no-store'})

    @app.post('/api/posts')
    async def create_post(request: Request):
        data = await payload(request)
        body, cid = text(data, 'body', 2000), text(data, 'client_id', 64, 8)
        photo = text(data, 'photo_id', 64) or None
        if not body and not photo:
            fail('Write something or add a photo.', 422)
        with db(True) as con:
            user, _ = auth(con, request)
            campus_access(con, user, user)
            existing = con.execute('SELECT * FROM posts WHERE user_id=? AND client_id=?', (user['id'], cid)).fetchone()
            if existing:
                if existing['body'] != body or existing['photo_id'] != photo:
                    fail('This post ID belongs to different content.', 409)
                return {'post': post_json(con, user, existing)}
            limit(con, 'post:' + user['id'], 20, 3600)
            if photo and (not con.execute('SELECT 1 FROM post_photos WHERE id=? AND user_id=?', (photo, user['id'])).fetchone()
                          or con.execute('SELECT 1 FROM posts WHERE photo_id=?', (photo,)).fetchone()):
                fail('Photo unavailable or already published.', 409)
            cur = con.execute('INSERT INTO posts(user_id,client_id,body,photo_id,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                              (user['id'], cid, body, photo, now(), now()))
            emit(con, user['id'])
            return {'post': post_json(con, user, con.execute('SELECT * FROM posts WHERE id=?', (cur.lastrowid,)).fetchone())}

    @app.patch('/api/posts/{pid}')
    async def edit_post(pid: int, request: Request):
        data = await payload(request)
        body = text(data, 'body', 2000)
        with db(True) as con:
            user, _ = auth(con, request)
            row = post_access(con, user, pid)
            if row['user_id'] != user['id']:
                fail('Only the author can edit this post.', 403)
            if not body and not row['photo_id']:
                fail('Write something or add a photo.', 422)
            con.execute('UPDATE posts SET body=?,updated_at=? WHERE id=?', (body, now(), pid))
            emit(con, user['id'])
            return {'post': post_json(con, user, con.execute('SELECT * FROM posts WHERE id=?', (pid,)).fetchone())}

    @app.delete('/api/posts/{pid}')
    def delete_post(pid: int, request: Request):
        with db(True) as con:
            user, _ = auth(con, request)
            row = post_access(con, user, pid)
            if row['user_id'] != user['id']:
                fail('Only the author can delete this post.', 403)
            con.execute('DELETE FROM posts WHERE id=?', (pid,))
            if row['photo_id']:
                con.execute('DELETE FROM post_photos WHERE id=?', (row['photo_id'],))
            emit(con, user['id'])
            return {'ok': True}

    @app.get('/api/posts/{pid}/likes')
    def post_likes(pid: int, request: Request):
        with db() as con:
            user, _ = auth(con, request)
            post_access(con, user, pid)
            return {'items': visible_reactions(con, user, con.execute(
                'SELECT user_id FROM post_likes WHERE post_id=? ORDER BY created_at,user_id', (pid,)))}

    @app.put('/api/posts/{pid}/like')
    async def post_like(pid: int, request: Request):
        data = await payload(request)
        if type(data.get('liked')) is not bool:
            fail('Choose whether to like this post.', 422)
        with db(True) as con:
            user, _ = auth(con, request)
            row = post_access(con, user, pid)
            limit(con, 'post-like:' + user['id'], 90)
            if data['liked']:
                con.execute('INSERT OR IGNORE INTO post_likes VALUES (?,?,?)', (pid, user['id'], now()))
            else:
                con.execute('DELETE FROM post_likes WHERE post_id=? AND user_id=?', (pid, user['id']))
            emit(con, user['id'], row['user_id'])
            return {'post': post_json(con, user, row)}

    @app.get('/api/profiles/{uid}/likes')
    def profile_likes(uid: str, request: Request):
        with db() as con:
            user, _ = auth(con, request)
            campus_access(con, user, get_user(con, uid))
            items = visible_reactions(con, user, con.execute(
                'SELECT sender FROM profile_likes WHERE target=? ORDER BY created_at,sender', (uid,)))
            return {'items': items, 'liked': any(p['id'] == user['id'] for p in items)}

    @app.post('/api/profiles/{uid}/like')
    async def profile_like(uid: str, request: Request):
        data = await payload(request)
        context = data.get('context', 'campus')
        if context not in ('campus', 'dating'):
            fail('Invalid like context.', 422)
        with db(True) as con:
            user, _ = auth(con, request)
            target = get_user(con, uid)
            campus_access(con, user, target)
            if uid == user['id']:
                fail('You cannot like your own profile.', 422)
            limit(con, 'public-like:' + user['id'], 90)
            result = like_dating(con, user, target) if context == 'dating' else {'matched': False}
            con.execute('INSERT OR IGNORE INTO profile_likes VALUES (?,?,?)', (user['id'], uid, now()))
            emit(con, user['id'], uid)
            return {**result, 'liked': True}

    @app.delete('/api/profiles/{uid}/like')
    def unlike_profile(uid: str, request: Request):
        with db(True) as con:
            user, _ = auth(con, request)
            campus_access(con, user, get_user(con, uid))
            existed = con.execute('DELETE FROM profile_likes WHERE sender=? AND target=?', (user['id'], uid)).rowcount
            match = con.execute('SELECT 1 FROM relationships WHERE low_id=? AND high_id=? AND kind="dating" AND status="accepted"', pair(user['id'], uid)).fetchone()
            if existed and not match:
                con.execute('DELETE FROM dating_likes WHERE sender=? AND target=?', (user['id'], uid))
            emit(con, user['id'], uid)
            return {'liked': False}

    @app.get('/api/message-requests')
    def message_requests(request: Request):
        with db() as con:
            user, _ = auth(con, request)
            rows = con.execute('SELECT * FROM message_requests WHERE sender=? OR target=? ORDER BY created_at DESC,id DESC',
                               (user['id'], user['id']))
            items = []
            for row in rows:
                try:
                    sender, target = request_peers(con, user, row)
                except HTTPException:
                    continue
                # Accepted requests live in the regular inbox. Declines stay private to the recipient.
                if row['status'] != 'pending':
                    continue
                other = target if row['sender'] == user['id'] else sender
                items.append({'id': row['id'], 'body': row['body'], 'kind': row['kind'],
                              'direction': 'sent' if row['sender'] == user['id'] else 'received',
                              'profile': public(con, other), 'created_at': row['created_at'], 'post_id': row['post_id']})
            return {'items': items}

    @app.post('/api/message-requests')
    async def send_request(request: Request):
        data = await payload(request)
        body, cid, uid = text(data, 'body', 1000, 1), text(data, 'client_id', 64, 8), text(data, 'target_id', 64, 1)
        kind = data.get('kind', 'friend')
        if kind not in ('friend', 'study', 'dating'):
            fail('Invalid request kind.', 422)
        pid = number(data, 'post_id', 1, 9223372036854775807) if data.get('post_id') is not None else None
        with db(True) as con:
            user, _ = auth(con, request)
            target = get_user(con, uid)
            campus_access(con, user, target)
            if uid == user['id']:
                fail('You cannot message yourself.', 422)
            if kind == 'dating' and not dating_compatible(user, target):
                fail('This Dating profile is unavailable.', 403)
            if pid and post_access(con, user, pid)['user_id'] != uid:
                fail('This post does not belong to that student.', 422)
            for rel in con.execute('SELECT id FROM relationships WHERE low_id=? AND high_id=? AND status="accepted"', pair(user['id'], uid)):
                try:
                    authorized_relation(con, user, rel['id'])
                    return {'conversation_id': rel['id']}
                except HTTPException:
                    continue
            existing = con.execute('SELECT * FROM message_requests WHERE sender=? AND target=?', (user['id'], uid)).fetchone()
            if existing:
                if existing['client_id'] == cid and existing['body'] == body and existing['post_id'] == pid and existing['kind'] == kind:
                    return {'id': existing['id'], 'status': 'sent'}
                fail('You have already sent a request to this student. They decide whether to reply.', 409)
            limit(con, 'private-comment:' + user['id'], 20, 3600)
            rid = str(uuid.uuid4())
            con.execute('INSERT INTO message_requests(id,sender,target,body,kind,post_id,client_id,created_at) VALUES (?,?,?,?,?,?,?,?)',
                        (rid, user['id'], uid, body, kind, pid, cid, now()))
            notify(con, uid, f'{user["display_name"]} sent you a private comment.')
            emit(con, user['id'])
            return {'id': rid, 'status': 'sent'}

    @app.post('/api/message-requests/{reqid}/{action}')
    def decide_request(reqid: str, action: str, request: Request):
        if action not in ('accept', 'decline'):
            fail('Invalid request action.', 422)
        with db(True) as con:
            user, _ = auth(con, request)
            row = con.execute('SELECT * FROM message_requests WHERE id=? AND target=?', (reqid, user['id'])).fetchone()
            if not row:
                fail('Request unavailable.', 404)
            sender, target = request_peers(con, user, row)
            if row['status'] != 'pending':
                if action == 'accept' and row['status'] == 'accepted' and row['relationship_id']:
                    authorized_relation(con, user, row['relationship_id'])
                    return {'conversation_id': row['relationship_id']}
                if action == 'accept':
                    fail('This request is no longer available.', 409)
                return {'ok': True}
            if action == 'decline':
                con.execute('UPDATE message_requests SET status="declined" WHERE id=?', (reqid,))
                emit(con, sender['id'], target['id'])
                return {'ok': True}
            if row['kind'] == 'dating' and not dating_compatible(sender, target):
                fail('This Dating request is no longer available.', 403)
            low, high = pair(sender['id'], target['id'])
            rel = con.execute('SELECT * FROM relationships WHERE low_id=? AND high_id=? AND kind=?', (low, high, row['kind'])).fetchone()
            rid = rel['id'] if rel else str(uuid.uuid4())
            if rel:
                con.execute('UPDATE relationships SET status="accepted",updated_at=? WHERE id=?', (now(), rid))
            else:
                con.execute('INSERT INTO relationships VALUES (?,?,?,?,?,?,?,?)',
                            (rid, low, high, row['kind'], sender['id'], 'accepted', now(), now()))
            # The initial private comment enters history once, only after acceptance.
            con.execute('INSERT OR IGNORE INTO messages(relationship_id,sender_id,client_id,body,created_at) VALUES (?,?,?,?,?)',
                        (rid, sender['id'], 'request-' + reqid, row['body'], row['created_at']))
            con.execute('UPDATE message_requests SET status="accepted",relationship_id=? WHERE id=?', (rid, reqid))
            notify(con, sender['id'], f'{target["display_name"]} accepted your message request.', rid)
            emit(con, target['id'])
            return {'conversation_id': rid}
