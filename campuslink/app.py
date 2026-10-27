from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from .security import LocalEligibility, USERNAME, age, check_password, password_hash, token_hash
from .recovery import SMTPRecovery
from .photos import MAX_PHOTOS, MAX_UPLOAD_BYTES, PhotoError, process_photo
from .prompts import PROMPTS, QUESTIONS, MAX_PROMPTS, MAX_ANSWER, validate_answers
from .intentions import INTENTIONS, INTENTION_LABELS
from .starters import conversation_starters
from .social import install_social
from .deployment import Deployment, StagingAccess

ROOT = Path(__file__).resolve().parent.parent
INTERESTS = ['Technology', 'Cybersecurity', 'Programming', 'Gaming', 'Music', 'Sports',
             'Reading', 'Entrepreneurship', 'Art', 'Movies', 'Travel', 'Photography', 'Science', 'Design']
DAY = 86400
WEIGHTS = {'interest': 3, 'program': 4, 'goal': 2, 'subject': 5, 'skill': 3, 'study_goal': 3}


def create_app(db_path: str | Path | None = None, *, testing=False, recovery_delivery=None):
    deployment = Deployment.load(ROOT,db_path)
    app = FastAPI(title='CampusLink', docs_url='/api/docs' if testing else None, redoc_url=None)
    app.state.db_path = str(deployment.database)
    app.state.mode = deployment.mode
    app.state.testing = testing
    eligibility = LocalEligibility()
    recovery_delivery = recovery_delivery or SMTPRecovery(base_url=deployment.origin or None)
    recovery_available = bool(getattr(recovery_delivery,'configured',testing))
    Path(app.state.db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def db(write=False):
        con = sqlite3.connect(app.state.db_path, timeout=15, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        con.execute('PRAGMA busy_timeout=15000')
        try:
            if write:
                con.execute('BEGIN IMMEDIATE')
            yield con
            if write:
                con.commit()
        except BaseException:
            if write:
                con.rollback()
            raise
        finally:
            con.close()

    with db() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript((ROOT / 'campuslink' / 'schema.sql').read_text())
        deployment.reject_fixture_database(con)
        con.executemany('INSERT OR IGNORE INTO interests(name) VALUES (?)', [(i,) for i in INTERESTS])

    def fail(message, status=400):
        raise HTTPException(status, message)

    def now():
        return int(time.time())

    def text(data, key, maximum=200, minimum=0):
        val = data.get(key, '')
        if not isinstance(val, str) or not minimum <= len(val.strip()) <= maximum:
            fail(f'{key.replace("_", " ").capitalize()} must be {minimum}–{maximum} characters.', 422)
        return val.strip()

    def boolean(data, key):
        if type(data[key]) is not bool:
            fail(f'{key} must be true or false.', 422)
        return int(data[key])

    def number(data, key, low, high, default=None):
        value = data.get(key, default)
        try:
            if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
                raise ValueError()
            value = int(value)
            if not low <= value <= high:
                raise ValueError()
            return value
        except (ValueError, TypeError):
            fail(f'{key} must be between {low} and {high}.', 422)

    async def payload(request):
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (ValueError, json.JSONDecodeError):
            fail('A JSON object is required.', 422)

    def limit(con, key, maximum=60, seconds=60):
        window = now() // seconds
        con.execute('INSERT INTO rate_limits VALUES (?, ?, 1) ON CONFLICT(key) DO UPDATE SET '
                    'count=CASE WHEN window=excluded.window THEN count+1 ELSE 1 END, window=excluded.window', (key, window))
        if con.execute('SELECT count FROM rate_limits WHERE key=?', (key,)).fetchone()[0] > maximum:
            fail('Too many attempts. Please try again later.', 429)

    def auth(con, request, *, csrf=True):
        token = token_hash(request.cookies.get('campuslink_session', ''))
        session = con.execute('SELECT * FROM sessions WHERE token_hash=? AND expires_at>?', (token, now())).fetchone()
        if not session:
            fail('Please sign in again.', 401)
        user = con.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
        if not user or user['status'] != 'active':
            fail('This account is unavailable.', 401)
        if csrf and request.method not in ('GET', 'HEAD'):
            supplied = request.headers.get('x-csrf-token', '')
            if not secrets.compare_digest(supplied, session['csrf']):
                fail('Your session changed. Refresh and try again.', 403)
        return user, session

    def emit(con, *ids):
        con.executemany('INSERT INTO events(user_id,created_at) VALUES (?,?)', [(i, now()) for i in set(ids)])

    def notify(con, uid, body, rid=None):
        user = con.execute('SELECT notifications_enabled FROM users WHERE id=?', (uid,)).fetchone()
        if user and user[0]:
            con.execute('INSERT INTO notifications(user_id,body,relationship_id,created_at) VALUES (?,?,?,?)', (uid, body, rid, now()))
        emit(con, uid)

    def blocked(con, a, b):
        return con.execute('SELECT 1 FROM blocks WHERE (blocker=? AND blocked=?) OR (blocker=? AND blocked=?)', (a,b,b,a)).fetchone() is not None

    def interests(con, uid):
        return [r[0] for r in con.execute('SELECT i.name FROM interests i JOIN user_interests ui ON ui.interest_id=i.id WHERE ui.user_id=? ORDER BY i.name', (uid,))]

    def public(con, user, *, dating=False, viewer=None):
        photos = [{'id':r['id'],'url':f'/api/photos/{r["id"]}?v={r["version"]}',
                   'width':r['width'],'height':r['height'],'position':r['position']}
                  for r in con.execute('SELECT id,width,height,position,version FROM profile_photos WHERE user_id=? ORDER BY position,id',(user['id'],))]
        prompts = [{'prompt_id':r['prompt_id'], 'question':QUESTIONS[r['prompt_id']], 'answer':r['answer']}
                   for r in con.execute('SELECT prompt_id,answer FROM profile_prompts WHERE user_id=? ORDER BY position',(user['id'],))]
        result = {**{k: user[k] for k in ('id','username','display_name','bio','institution_id','program','year','subjects','skills','study_goals')},
                'interests': interests(con, user['id']), 'local_test': bool(user['local_test']), 'verified': False,
                'photos':photos,'main_photo_url':photos[0]['url'] if photos else None,'prompts':prompts}
        viewer_id = viewer['id'] if viewer is not None else user['id']
        result['like_count'] = con.execute('SELECT count(*) FROM profile_likes l JOIN users u ON u.id=l.sender WHERE l.target=? AND u.status="active" AND NOT EXISTS (SELECT 1 FROM blocks b WHERE (b.blocker=? AND b.blocked=l.sender) OR (b.blocked=? AND b.blocker=l.sender))', (user['id'],viewer_id,viewer_id)).fetchone()[0]
        result['liked'] = bool(con.execute('SELECT 1 FROM profile_likes WHERE sender=? AND target=?',(viewer_id,user['id'])).fetchone())
        if dating:
            result['dating_liked'] = bool(con.execute('SELECT 1 FROM dating_likes WHERE sender=? AND target=?',(viewer_id,user['id'])).fetchone())
            intention = con.execute('SELECT intention FROM dating_intentions WHERE user_id=? AND displayed=1',(user['id'],)).fetchone()
            if intention:
                result.update(dating_intention=intention[0],dating_intention_label=INTENTION_LABELS[intention[0]])
        return result

    def self_profile(con, user, session=None):
        intention = con.execute('SELECT intention,displayed FROM dating_intentions WHERE user_id=?',(user['id'],)).fetchone()
        return {**public(con, user), **{k: user[k] for k in ('email','dob','discoverable','friend_goal','study_goal','dating_enabled','gender',
                'dating_min','dating_max','onboarding_step','notifications_enabled','role')},
                'dating_genders': json.loads(user['dating_genders']), 'adult_eligible': eligibility.adult(user),
                'csrf': session['csrf'] if session else None,
                'dating_intention':intention['intention'] if intention else '',
                'show_dating_intention':bool(intention and intention['displayed'])}

    def get_user(con, uid):
        user = con.execute('SELECT * FROM users WHERE id=? AND status="active"', (uid,)).fetchone()
        if not user:
            fail('Student unavailable.', 404)
        return user

    def pair(a, b):
        return tuple(sorted((a,b)))

    def relation(con, a, b, kind):
        return con.execute('SELECT * FROM relationships WHERE low_id=? AND high_id=? AND kind=?', (*pair(a,b),kind)).fetchone()

    def dating_compatible(a,b):
        return (a['dating_enabled'] and b['dating_enabled'] and eligibility.adult(a) and eligibility.adult(b)
                and a['gender'] in json.loads(b['dating_genders']) and b['gender'] in json.loads(a['dating_genders'])
                and a['dating_min'] <= age(b['dob']) <= a['dating_max'] and b['dating_min'] <= age(a['dob']) <= b['dating_max'])

    def can_discover(con, a, b, kind):
        if a['id'] == b['id'] or a['institution_id']!=b['institution_id'] or b['onboarding_step']!=6 or not b['discoverable'] or not eligibility.student(a) or not eligibility.student(b) or blocked(con,a['id'],b['id']):
            return False
        if kind == 'dating':
            return dating_compatible(a,b)
        return bool(a[f'{kind}_goal'] and b[f'{kind}_goal'])

    def authorized_relation(con, user, rid):
        row = con.execute('SELECT * FROM relationships WHERE id=? AND (low_id=? OR high_id=?)', (rid,user['id'],user['id'])).fetchone()
        if not row:
            fail('Conversation unavailable.',404)
        other = row['high_id'] if row['low_id'] == user['id'] else row['low_id']
        target = get_user(con, other)
        if row['status'] != 'accepted' or blocked(con,user['id'],other):
            fail('This connection no longer permits messaging.',403)
        if row['kind'] == 'dating' and not dating_compatible(user,target):
            fail('This dating conversation is inactive.',403)
        return row, target

    def require_profile_access(con, user, target):
        if user['id']==target['id']:
            return
        if blocked(con,user['id'],target['id']):
            fail('Profile unavailable.',404)
        for row in con.execute('SELECT id FROM relationships WHERE low_id=? AND high_id=? AND status="accepted"',pair(user['id'],target['id'])):
            try:
                authorized_relation(con,user,row['id'])
                return
            except HTTPException:
                continue
        if not any(can_discover(con,user,target,k) for k in ('friend','study','dating')):
            fail('Profile unavailable.',404)

    def campus_access(con, user, target):
        if user['onboarding_step'] != 6 or target['onboarding_step'] != 6 or not eligibility.student(user) or not eligibility.student(target) or user['institution_id'] != target['institution_id'] or blocked(con,user['id'],target['id']):
            fail('Student unavailable.',404)
        if user['id'] == target['id'] or target['discoverable']:
            return
        require_profile_access(con,user,target)

    def require_dating_profile_access(con, user, target):
        if user['id']==target['id'] and user['dating_enabled'] and eligibility.adult(user):
            return
        if can_discover(con,user,target,'dating'):
            return
        match = relation(con,user['id'],target['id'],'dating')
        if match and match['status']=='accepted':
            try:
                authorized_relation(con,user,match['id'])
                return
            except HTTPException:
                pass
        fail('Dating profile unavailable.',404)

    def profile_changed(con, uid):
        peers={uid}
        for row in con.execute('SELECT low_id,high_id FROM relationships WHERE status="accepted" AND (low_id=? OR high_id=?)',(uid,uid)):
            peers.update(row)
        emit(con,*peers)

    def start_session(con, user, request):
        # Successful account switching ends this browser's prior session only.
        con.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(request.cookies.get('campuslink_session','')),))
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        con.execute('INSERT INTO sessions VALUES (?,?,?,?,?)', (token_hash(token),user['id'],csrf,now()+7*DAY,now()))
        result = JSONResponse({'user':self_profile(con,user), 'csrf':csrf})
        result.set_cookie('campuslink_session', token, httponly=True, samesite='lax', secure=deployment.mode=='staging' or request.url.scheme=='https', max_age=7*DAY, path='/')
        return result

    @app.middleware('http')
    async def guards(request, call_next):
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin = request.headers.get('origin')
            if origin and origin != str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'Cross-origin request denied.'},403)
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail':'Cross-site request denied.'},403)
            photo_upload = request.method in ('POST','PUT') and bool(re.fullmatch(r'/api/me/(?:photos(?:/[^/]+)?|post-photos)',request.url.path))
            max_body = MAX_UPLOAD_BYTES if photo_upload else 32768
            if photo_upload:
                try:
                    with db() as con:
                        user,_=auth(con,request)
                        limit(con,'photo-upload:'+user['id'],20)
                except HTTPException as exc:
                    return JSONResponse({'detail':exc.detail},exc.status_code)
            try:
                if int(request.headers.get('content-length','0')) > max_body:
                    return JSONResponse({'detail':'Request is too large.'},413)
            except ValueError:
                return JSONResponse({'detail':'Invalid content length.'},400)
            # Bound chunked requests too; replay the bounded body downstream
            # through Starlette's cached Request body, without multipart buffers.
            chunks=[]
            received=0
            async for chunk in request.stream():
                received+=len(chunk)
                if received>max_body:
                    return JSONResponse({'detail':'Request is too large.'},413)
                chunks.append(chunk)
            request._body=b''.join(chunks)
        if request.url.path.startswith('/api/') and request.url.path != '/api/events':
            try:
                with db() as con:
                    ip = request.client.host if request.client else 'unknown'
                    # Students on the same campus Wi-Fi share an IP. A busy
                    # account must not consume another student's request budget.
                    limit(con, 'ip:'+ip, 6000)
                    session_user = con.execute('SELECT u.id FROM sessions s JOIN users u ON u.id=s.user_id '
                        'WHERE s.token_hash=? AND s.expires_at>? AND u.status="active"',
                        (token_hash(request.cookies.get('campuslink_session','')),now())).fetchone()
                    bucket = 'user:'+session_user[0] if session_user else 'anonymous:'+ip
                    limit(con, 'api:'+bucket, 600)
            except HTTPException as exc:
                return JSONResponse({'detail':exc.detail},exc.status_code,headers={'Retry-After':'60'})
        response = await call_next(request)
        response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-src 'none'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
            'Cache-Control':'no-store' if request.url.path.startswith('/api/') else 'no-cache'})
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse({'detail':exc.detail},exc.status_code, headers={'Retry-After':'60'} if exc.status_code==429 else {})

    @app.get('/api/health')
    def health():
        with db() as con:
            con.execute('SELECT 1').fetchone()
        return {'status':'ok','mode':deployment.mode,'public_launch_ready':False}

    @app.get('/api/catalog')
    def catalog():
        return {'interests':INTERESTS,'institutions':[{'id':'zut','name':'Zambia University College of Technology'}], 'mode':deployment.mode,'demo_accounts_available':deployment.mode=='local','recovery_available':recovery_available,
                'prompts':PROMPTS,'prompt_limits':{'count':MAX_PROMPTS,'answer':MAX_ANSWER},'dating_intentions':INTENTIONS}

    @app.post('/api/auth/register')
    async def register(request: Request):
        data = await payload(request)
        with db() as con:
            limit(con,'register:'+request.client.host,10,3600)
        email = text(data,'email',254,5).lower()
        username = text(data,'username',24,3).lower()
        password = text(data,'password',128,12)
        display = text(data,'display_name',60,1)
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not USERNAME.fullmatch(username):
            fail('Use a valid email and a username with 3–24 lowercase letters, numbers or underscores.',422)
        if data.get('agreement') is not True:
            fail('Please agree to the draft terms and privacy notice.',422)
        uid = str(uuid.uuid4())
        hashed = password_hash(password)
        with db(True) as con:
            if con.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():
                fail('That username is already taken.',409)
            if con.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone():
                fail('An account already uses this email. Try signing in.',409)
            con.execute('INSERT INTO users(id,email,username,display_name,password_hash,local_test,created_at) VALUES (?,?,?,?,?,1,?)', (uid,email,username,display,hashed,now()))
            return start_session(con,get_user(con,uid),request)

    dummy_hash = password_hash('dummy-constant-for-timing')

    @app.post('/api/auth/login')
    async def login(request: Request):
        data = await payload(request)
        email = text(data,'email',254,1).lower()
        password = text(data,'password',128,1)
        with db() as con:
            limit(con,'login-ip:'+request.client.host,30,900)
            limit(con,'login-user:'+token_hash(email),10,900)
            user = con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            valid = check_password(password,user['password_hash'] if user else dummy_hash)
        if not valid or not user or user['status']!='active':
            fail('Email or password is incorrect, or the account is unavailable.',401)
        with db(True) as con:
            return start_session(con,user,request)

    @app.get('/api/me')
    def me(request: Request):
        with db() as con:
            user, session = auth(con,request)
            return {'user':self_profile(con,user,session)}

    @app.put('/api/me/prompts')
    async def save_prompts(request: Request):
        data = await payload(request)
        with db(True) as con:
            user, session = auth(con,request)
            try:
                answers = validate_answers(data.get('prompts'))
            except ValueError as exc:
                fail(str(exc),422)
            # Replacing the ordered set in one transaction makes retries safe and
            # prevents partial edits or concurrent saves exceeding the cap.
            con.execute('DELETE FROM profile_prompts WHERE user_id=?',(user['id'],))
            con.executemany('INSERT INTO profile_prompts(user_id,prompt_id,answer,position) VALUES (?,?,?,?)',
                            [(user['id'],prompt_id,answer,index) for index,(prompt_id,answer) in enumerate(answers)])
            profile_changed(con,user['id'])
            return {'user':self_profile(con,user,session)}

    def inspect_upload(con, user, photo_id, key, digest):
        if photo_id:
            row=con.execute('SELECT id,operation_key,operation_hash FROM profile_photos WHERE id=? AND user_id=?',(photo_id,user['id'])).fetchone()
            if not row:
                fail('Photo unavailable.',404)
            if row['operation_key']==key:
                if row['operation_hash']!=digest:
                    fail('This upload key was already used for a different image.',409)
                return row
        else:
            row=con.execute('SELECT id,upload_hash FROM profile_photos WHERE user_id=? AND upload_key=?',(user['id'],key)).fetchone()
            if row:
                if row['upload_hash']!=digest:
                    fail('This upload key was already used for a different image.',409)
                return row
            if con.execute('SELECT count(*) FROM profile_photos WHERE user_id=?',(user['id'],)).fetchone()[0]>=MAX_PHOTOS:
                fail('Your gallery is full. Replace or remove a photo first.',409)
        return None

    async def store_photo(request, photo_id=None):
        content=await request.body()
        key=text({'upload_id':request.headers.get('x-upload-id','')},'upload_id',64,8)
        digest=hashlib.sha256(content).hexdigest()
        with db() as con:
            user,session=auth(con,request)
            existing=inspect_upload(con,user,photo_id,key,digest)
            if existing:
                return {'user':self_profile(con,user,session),'photo_id':existing['id']}
        try:
            image=await asyncio.to_thread(process_photo,content)
        except PhotoError as exc:
            fail(str(exc),422)
        with db(True) as con:
            user,session=auth(con,request)
            existing=inspect_upload(con,user,photo_id,key,digest)
            if existing:
                return {'user':self_profile(con,user,session),'photo_id':existing['id']}
            if photo_id:
                con.execute('UPDATE profile_photos SET image=?,width=?,height=?,version=version+1,operation_key=?,operation_hash=? WHERE id=? AND user_id=?',
                            (image.data,image.width,image.height,key,digest,photo_id,user['id']))
            else:
                photo_id=str(uuid.uuid4())
                position=con.execute('SELECT count(*) FROM profile_photos WHERE user_id=?',(user['id'],)).fetchone()[0]
                con.execute('INSERT INTO profile_photos(id,user_id,image,width,height,position,upload_key,upload_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                            (photo_id,user['id'],image.data,image.width,image.height,position,key,digest,now()))
            profile_changed(con,user['id'])
            return {'user':self_profile(con,user,session),'photo_id':photo_id}

    @app.post('/api/me/photos')
    async def upload_photo(request: Request):
        return await store_photo(request)

    @app.put('/api/me/photos/{photo_id}')
    async def replace_photo(photo_id: str, request: Request):
        return await store_photo(request,photo_id)

    @app.patch('/api/me/photos/order')
    async def order_photos(request: Request):
        data=await payload(request)
        order=data.get('photo_ids')
        if not isinstance(order,list) or len(order)>MAX_PHOTOS or any(not isinstance(i,str) or len(i)>36 for i in order) or len(order)!=len(set(order)):
            fail('Choose each of your photos exactly once.',422)
        with db(True) as con:
            user,session=auth(con,request)
            own={r[0] for r in con.execute('SELECT id FROM profile_photos WHERE user_id=?',(user['id'],))}
            if set(order)!=own:
                fail('Choose each of your photos exactly once.',422)
            con.executemany('UPDATE profile_photos SET position=? WHERE id=? AND user_id=?',[(i,pid,user['id']) for i,pid in enumerate(order)])
            profile_changed(con,user['id'])
            return {'user':self_profile(con,user,session)}

    @app.post('/api/me/photos/{photo_id}/main')
    def main_photo(photo_id: str, request: Request):
        with db(True) as con:
            user,session=auth(con,request)
            ids=[r[0] for r in con.execute('SELECT id FROM profile_photos WHERE user_id=? ORDER BY position,id',(user['id'],))]
            if photo_id not in ids:
                fail('Photo unavailable.',404)
            ids.remove(photo_id)
            ids.insert(0,photo_id)
            con.executemany('UPDATE profile_photos SET position=? WHERE id=? AND user_id=?',[(i,pid,user['id']) for i,pid in enumerate(ids)])
            profile_changed(con,user['id'])
            return {'user':self_profile(con,user,session)}

    @app.delete('/api/me/photos/{photo_id}')
    def delete_photo(photo_id: str, request: Request):
        with db(True) as con:
            user,session=auth(con,request)
            if not con.execute('SELECT 1 FROM profile_photos WHERE id=? AND user_id=?',(photo_id,user['id'])).fetchone():
                fail('Photo unavailable.',404)
            con.execute('DELETE FROM profile_photos WHERE id=? AND user_id=?',(photo_id,user['id']))
            ids=[r[0] for r in con.execute('SELECT id FROM profile_photos WHERE user_id=? ORDER BY position,id',(user['id'],))]
            con.executemany('UPDATE profile_photos SET position=? WHERE id=? AND user_id=?',[(i,pid,user['id']) for i,pid in enumerate(ids)])
            profile_changed(con,user['id'])
            return {'user':self_profile(con,user,session)}

    @app.get('/api/photos/{photo_id}')
    def photo(photo_id: str, request: Request):
        with db() as con:
            user,_=auth(con,request)
            owner=con.execute('SELECT user_id FROM profile_photos WHERE id=?',(photo_id,)).fetchone()
            if not owner:
                fail('Photo unavailable.',404)
            target=get_user(con,owner['user_id'])
            require_profile_access(con,user,target)
            row=con.execute('SELECT image FROM profile_photos WHERE id=?',(photo_id,)).fetchone()
            if not row:
                fail('Photo unavailable.',404)
            return Response(bytes(row['image']),media_type='image/jpeg',headers={'Cache-Control':'no-store','Content-Disposition':'inline; filename="photo.jpg"'})

    @app.post('/api/dating/test-eligibility')
    async def local_adult_test_access(request: Request):
        """Explicit self-declared adult test access; never verifies age/identity.

        This is available locally and inside the restricted staging gate only.
        Public modes remain disabled; this declaration never verifies a student.
        This declaration does not activate Dating; that requires separate opt-in.
        """
        data=await payload(request)
        with db() as con:
            user,_=auth(con,request)
            limit(con,'adult-test:'+user['id'],10,3600)
        if data.get('adult_test_agreement') is not True:
            fail('Confirm this is self-declared 18+ access for local testing.',422)
        dob=text(data,'dob',10,10)
        try:
            adult_age=age(dob)
            if not 18<=adult_age<=100:
                raise ValueError()
        except ValueError:
            fail('Dating test access is restricted to people aged 18 or older. Enter a valid birth date.',403)
        with db(True) as con:
            user,session=auth(con,request)
            if not user['local_test']:
                fail('This setup is available only to local test accounts.',403)
            con.execute('UPDATE users SET dob=?,adult_test=1 WHERE id=?',(dob,user['id']))
            emit(con,user['id'])
            return {'user':self_profile(con,get_user(con,user['id']),session),'eligibility':'self_declared_local_test','verified':False}

    @app.post('/api/auth/recover')
    async def recover(request: Request):
        data=await payload(request)
        email=text(data,'email',254,5).lower()
        with db() as con:
            limit(con,'recovery-ip:'+request.client.host,10,3600)
            limit(con,'recovery-email:'+token_hash(email),3,3600)
        if not recovery_available:
            fail('Password recovery is unavailable until an email provider is configured.',503)
        token=secrets.token_urlsafe(32)
        with db(True) as con:
            user=con.execute('SELECT id,email FROM users WHERE email=? AND status="active"',(email,)).fetchone()
            if user:
                con.execute('DELETE FROM recovery_tokens WHERE user_id=? OR expires_at<?',(user['id'],now()))
                con.execute('INSERT INTO recovery_tokens VALUES (?,?,?)',(token_hash(token),user['id'],now()+1800))
        def deliver(email,token):
            try:
                # Transport errors never reveal account existence in the response.
                recovery_delivery(email,token)
            except Exception:
                logging.getLogger('campuslink').error('Recovery delivery failed; check email provider configuration.')
        return JSONResponse({'message':'If an active account uses this email, a reset link will arrive shortly.'},
                            background=BackgroundTask(deliver,user['email'],token) if user else None)

    @app.post('/api/auth/reset-password')
    async def reset_password(request: Request):
        data=await payload(request)
        token,new=text(data,'token',100,20),text(data,'new_password',128,12)
        with db() as con:
            limit(con,'reset-ip:'+request.client.host,15,3600)
        hashed=password_hash(new)
        with db(True) as con:
            recovery=con.execute('SELECT r.* FROM recovery_tokens r JOIN users u ON u.id=r.user_id WHERE r.token_hash=? AND r.expires_at>? AND u.status="active"',(token_hash(token),now())).fetchone()
            if not recovery:
                fail('This reset link is invalid or expired. Request a new one.',400)
            con.execute('UPDATE users SET password_hash=? WHERE id=?',(hashed,recovery['user_id']))
            con.execute('DELETE FROM sessions WHERE user_id=?',(recovery['user_id'],))
            con.execute('DELETE FROM recovery_tokens WHERE user_id=?',(recovery['user_id'],))
            notify(con,recovery['user_id'],'Your password was reset. All sessions were signed out.')
        return {'ok':True}

    @app.post('/api/auth/logout')
    def logout(request: Request):
        with db(True) as con:
            user, session = auth(con,request)
            con.execute('DELETE FROM sessions WHERE token_hash=?',(session['token_hash'],))
            emit(con,user['id'])
        response = JSONResponse({'ok':True})
        response.delete_cookie('campuslink_session',path='/')
        return response

    @app.patch('/api/me')
    async def update_profile(request: Request):
        data = await payload(request)
        with db(True) as con:
            user, session = auth(con,request)
            updates = {}
            for key, maximum, minimum in [('display_name',60,1),('bio',500,0),('program',100,0),('subjects',300,0),('skills',300,0),('study_goals',300,0)]:
                if key in data:
                    updates[key] = text(data,key,maximum,minimum)
            for key in ('discoverable','friend_goal','study_goal','notifications_enabled','dating_enabled'):
                if key in data:
                    updates[key] = boolean(data,key)
            if 'username' in data:
                name = text(data,'username',24,3).lower()
                if not USERNAME.fullmatch(name):
                    fail('Invalid username.',422)
                if con.execute('SELECT 1 FROM users WHERE username=? AND id!=?',(name,user['id'])).fetchone():
                    fail('That username is already taken.',409)
                updates['username'] = name
            if 'year' in data:
                updates['year'] = number(data,'year',1,7)
            if 'onboarding_step' in data:
                updates['onboarding_step'] = number(data,'onboarding_step',0,6)
            if 'dob' in data:
                value = text(data,'dob',10)
                try:
                    if age(value) < 13 or age(value) > 100:
                        raise ValueError()
                except ValueError:
                    fail('Enter a valid birth date (age 13–100).',422)
                updates['dob'] = value
            if 'gender' in data:
                if data['gender'] not in ('woman','man','nonbinary',''):
                    fail('Invalid gender option.',422)
                updates['gender'] = data['gender']
            if 'dating_genders' in data:
                values = data['dating_genders']
                if not isinstance(values,list) or len(values)>3 or any(i not in ('woman','man','nonbinary') for i in values):
                    fail('Invalid dating preferences.',422)
                updates['dating_genders'] = json.dumps(sorted(set(values)))
            for key in ('dating_min','dating_max'):
                if key in data:
                    updates[key] = number(data,key,18,100)
            candidate = {**dict(user),**updates}
            if candidate['onboarding_step']==6 and not candidate['program'].strip():
                fail('Add your academic program before finishing onboarding.',422)
            if candidate['dating_min'] > candidate['dating_max']:
                fail('The maximum dating age must be at least the minimum.',422)
            if candidate['dating_enabled'] and (not eligibility.adult(candidate) or not candidate['gender'] or not json.loads(candidate['dating_genders'])):
                fail('Dating requires established adult eligibility and explicit preferences. Self-reported birth dates do not establish eligibility.',403)
            if 'dating_intention' in data or 'show_dating_intention' in data:
                previous = con.execute('SELECT intention,displayed FROM dating_intentions WHERE user_id=?',(user['id'],)).fetchone()
                intention = data.get('dating_intention',previous['intention'] if previous else '')
                if not isinstance(intention,str) or intention not in ('',*INTENTION_LABELS):
                    fail('Choose a dating intention from the available list, or leave it unset.',422)
                displayed = previous['displayed'] if previous and intention else 0
                if 'show_dating_intention' in data:
                    displayed = boolean(data,'show_dating_intention')
                if displayed and not intention:
                    fail('Choose an intention before displaying it in Dating.',422)
                if intention:
                    con.execute('INSERT INTO dating_intentions VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET intention=excluded.intention,displayed=excluded.displayed',
                                (user['id'],intention,displayed))
                else:
                    con.execute('DELETE FROM dating_intentions WHERE user_id=?',(user['id'],))
                profile_changed(con,user['id'])
            if 'interests' in data:
                values = data['interests']
                if not isinstance(values,list) or len(values)>14 or any(i not in INTERESTS for i in values):
                    fail('Choose interests from the available list.',422)
                con.execute('DELETE FROM user_interests WHERE user_id=?',(user['id'],))
                con.executemany('INSERT OR IGNORE INTO user_interests SELECT ?,id FROM interests WHERE name=?', [(user['id'],i) for i in values])
            if updates:
                con.execute('UPDATE users SET '+','.join(f'{k}=?' for k in updates)+' WHERE id=?',(*updates.values(),user['id']))
            # Deactivation of dating ends old matches permanently; re-enabling does not restore consent.
            if user['dating_enabled'] and not candidate['dating_enabled']:
                matches = con.execute('SELECT * FROM relationships WHERE kind="dating" AND status="accepted" AND (low_id=? OR high_id=?)',(user['id'],user['id'])).fetchall()
                for match in matches:
                    con.execute('UPDATE relationships SET status="removed",updated_at=? WHERE id=?',(now(),match['id']))
                    emit(con,match['low_id'],match['high_id'])
                con.execute('DELETE FROM dating_likes WHERE sender=? OR target=?',(user['id'],user['id']))
            emit(con,user['id'])
            return {'user':self_profile(con,get_user(con,user['id']),session)}

    @app.get('/api/discover')
    def discover(request: Request, mode: str='for-you', q: str='', program: str='', interest: str='', year: int=0, page: int=1, intention: str=''):
        if mode not in ('for-you','friend','study','dating') or not 1<=page<=100 or len(q)>100 or len(program)>100 or len(interest)>50 or not 0<=year<=7:
            fail('Invalid search filters.',422)
        if intention and (intention not in INTENTION_LABELS or mode!='dating'):
            fail('Intention filters are available only in Dating. Choose a listed intention.',422)
        with db() as con:
            user,_ = auth(con,request)
            limit(con,'search:'+user['id'],90)
            if mode=='dating' and not (user['dating_enabled'] and eligibility.adult(user)):
                fail('Activate eligible dating before using this view.',403)
            # Scope institution first. All eligibility/privacy rules precede scoring and pagination.
            candidates = con.execute('SELECT * FROM users WHERE status="active" AND onboarding_step=6 AND institution_id=? AND id!=?',(user['institution_id'],user['id'])).fetchall()
            own_interests = set(interests(con,user['id']))
            output = []
            for target in candidates:
                kinds = ['friend','study'] if mode=='for-you' else [mode]
                available = []
                for kind in kinds:
                    rel = relation(con,user['id'],target['id'],kind)
                    dismissed = con.execute('SELECT 1 FROM dismissals WHERE user_id=? AND target=? AND kind=? AND until_at>?',(user['id'],target['id'],kind,now())).fetchone()
                    liked = kind=='dating' and con.execute('SELECT 1 FROM dating_likes WHERE sender=? AND target=?',(user['id'],target['id'])).fetchone()
                    if can_discover(con,user,target,kind) and not dismissed and not liked and (not rel or rel['status'] in ('declined','cancelled','removed')):
                        available.append(kind)
                if not available:
                    continue
                profile = public(con,target,dating=mode=='dating',viewer=user)
                if intention and profile.get('dating_intention')!=intention:
                    continue
                if mode=='dating':
                    profile['age'] = age(target['dob'])
                haystack = ' '.join([target['display_name'],target['username'],target['program'],*profile['interests']]).casefold()
                if q.casefold() not in haystack or program.casefold() not in target['program'].casefold() or (interest and interest not in profile['interests']) or (year and year!=target['year']):
                    continue
                shared = sorted(own_interests.intersection(profile['interests']))
                same_program = bool(user['program']) and user['program'].casefold()==target['program'].casefold()
                score = len(shared)*WEIGHTS['interest'] + same_program*WEIGHTS['program'] + len(available)*WEIGHTS['goal']
                reasons = ['You both enjoy '+', '.join(shared[:3])+'.'] if shared else []
                if same_program:
                    reasons.append('You study the same program.')
                if 'study' in available:
                    for field,weight in [('subjects','subject'),('skills','skill'),('study_goals','study_goal')]:
                        common = set(x.strip().casefold() for x in user[field].split(',') if x.strip()) & set(x.strip().casefold() for x in target[field].split(',') if x.strip())
                        score += len(common)*WEIGHTS[weight]
                        if common:
                            reasons.append('Shared '+field.replace('_',' ')+': '+', '.join(sorted(common))+'.')
                output.append({**profile,'available_kinds':available,'shared_interests':shared,'reasons':reasons or ['Open to connecting with students on your campus.'],'score':score})
            output.sort(key=lambda p:(-p['score'],p['display_name'].casefold(),p['id']))
            start = (page-1)*12
            return {'items':output[start:start+12],'has_more':len(output)>start+12,'page':page}

    @app.get('/api/profiles/{uid}')
    def profile(uid: str, request: Request, context: str='general'):
        if context not in ('general','friend','study','dating','campus'):
            fail('Invalid profile context.',422)
        with db() as con:
            user,_ = auth(con,request)
            target = get_user(con,uid)
            if context=='dating':
                require_dating_profile_access(con,user,target)
            elif context=='campus':
                campus_access(con,user,target)
            else:
                require_profile_access(con,user,target)
            return {'profile':public(con,target,dating=context=='dating',viewer=user)}

    @app.post('/api/discover/{uid}/dismiss')
    async def dismiss(uid: str, request: Request):
        data = await payload(request)
        kind = data.get('kind')
        if kind not in ('friend','study','dating'):
            fail('Invalid discovery category.',422)
        with db(True) as con:
            user,_ = auth(con,request)
            if not can_discover(con,user,get_user(con,uid),kind):
                fail('Student unavailable.',404)
            con.execute('INSERT INTO dismissals VALUES (?,?,?,?) ON CONFLICT(user_id,target,kind) DO UPDATE SET until_at=excluded.until_at',(user['id'],uid,kind,now()+30*DAY))
            if kind=='dating':
                con.execute('DELETE FROM dating_likes WHERE sender=? AND target=?',(user['id'],uid))
            return {'ok':True}

    @app.post('/api/connections')
    async def connect(request: Request):
        data = await payload(request)
        kind, uid = data.get('kind'), text(data,'target_id',36,1)
        if kind not in ('friend','study'):
            fail('Choose a friendship or study request.',422)
        with db() as con:
            user,_ = auth(con,request)
            limit(con,'request:'+user['id'],30,3600)
        with db(True) as con:
            user,_ = auth(con,request)
            target = get_user(con,uid)
            if not can_discover(con,user,target,kind):
                fail('This student cannot receive that request.',403)
            rel = relation(con,user['id'],uid,kind)
            if rel and rel['status'] in ('accepted','pending'):
                if rel['status']=='pending' and rel['sender_id']!=user['id']:
                    con.execute('UPDATE relationships SET status="accepted",updated_at=? WHERE id=?',(now(),rel['id']))
                    notify(con,uid,f'{user["display_name"]} accepted your {kind} request.',rel['id'])
                    notify(con,user['id'],f'Your {kind} connection with {target["display_name"]} is ready.',rel['id'])
                    return {'id':rel['id'],'status':'accepted'}
                return {'id':rel['id'],'status':rel['status']}
            if rel and rel['status']=='declined' and now()-rel['updated_at']<30*DAY:
                fail('This request is in a 30-day cooldown.',409)
            rid = rel['id'] if rel else str(uuid.uuid4())
            if rel:
                con.execute('UPDATE relationships SET status="pending",sender_id=?,updated_at=? WHERE id=?',(user['id'],now(),rid))
            else:
                con.execute('INSERT INTO relationships VALUES (?,?,?,?,?,?,?,?)',(rid,*pair(user['id'],uid),kind,user['id'],'pending',now(),now()))
            notify(con,uid,f'{user["display_name"]} sent you a {kind} request.',rid)
            emit(con,user['id'])
            return {'id':rid,'status':'pending'}

    @app.get('/api/connections')
    def connections(request: Request):
        with db() as con:
            user,_ = auth(con,request)
            output = []
            rows = con.execute('SELECT * FROM relationships WHERE (low_id=? OR high_id=?) AND status IN ("pending","accepted") ORDER BY updated_at DESC,id',(user['id'],user['id'])).fetchall()
            for row in rows:
                uid = row['high_id'] if row['low_id']==user['id'] else row['low_id']
                target = con.execute('SELECT * FROM users WHERE id=? AND status="active"',(uid,)).fetchone()
                if not target or blocked(con,user['id'],uid) or (row['kind']=='dating' and not dating_compatible(user,target)):
                    continue
                output.append({**dict(row),'direction':'sent' if row['sender_id']==user['id'] else 'received','profile':public(con,target,dating=row['kind']=='dating')})
            return {'items':output}

    @app.post('/api/connections/{rid}/{action}')
    def change_connection(rid: str, action: str, request: Request):
        with db(True) as con:
            user,_ = auth(con,request)
            row = con.execute('SELECT * FROM relationships WHERE id=? AND (low_id=? OR high_id=?)',(rid,user['id'],user['id'])).fetchone()
            if not row:
                fail('Request unavailable.',404)
            other = row['high_id'] if row['low_id']==user['id'] else row['low_id']
            if blocked(con,user['id'],other):
                fail('Request unavailable.',404)
            target = get_user(con,other)
            if action in ('accept','decline') and row['status']=='pending' and row['sender_id']!=user['id']:
                state = 'accepted' if action=='accept' else 'declined'
                if action=='accept' and not (eligibility.student(user) and eligibility.student(target) and user[row['kind']+'_goal'] and target[row['kind']+'_goal']):
                    fail('This request is no longer eligible.',403)
            elif action=='cancel' and row['status']=='pending' and row['sender_id']==user['id']:
                state = 'cancelled'
            elif action=='remove' and row['status']=='accepted':
                state = 'removed'
            else:
                fail('This action is not available for this request.',409)
            con.execute('UPDATE relationships SET status=?,updated_at=? WHERE id=?',(state,now(),rid))
            if action=='decline':
                con.execute('INSERT INTO dismissals VALUES (?,?,?,?) ON CONFLICT(user_id,target,kind) DO UPDATE SET until_at=excluded.until_at',(other,user['id'],row['kind'],now()+30*DAY))
            if row['kind']=='dating':
                con.execute('DELETE FROM dating_likes WHERE (sender=? AND target=?) OR (sender=? AND target=?)',(user['id'],other,other,user['id']))
            if action=='accept':
                notify(con,other,f'{user["display_name"]} accepted your {row["kind"]} request.',rid)
            emit(con,user['id'],other)
            return {'status':state}

    def like_dating(con, user, target):
        uid = target['id']
        if not can_discover(con,user,target,'dating'):
            fail('Dating profile unavailable.',403)
        dismissed = con.execute('SELECT 1 FROM dismissals WHERE user_id=? AND target=? AND kind="dating" AND until_at>?',(user['id'],uid,now())).fetchone()
        if dismissed:
            fail('This profile is in a cooldown.',409)
        con.execute('INSERT OR IGNORE INTO dating_likes VALUES (?,?)',(user['id'],uid))
        if not con.execute('SELECT 1 FROM dating_likes WHERE sender=? AND target=?',(uid,user['id'])).fetchone():
            return {'matched':False}  # Deliberately no event or notification to target.
        rel = relation(con,user['id'],uid,'dating')
        rid = rel['id'] if rel else str(uuid.uuid4())
        if not rel:
            con.execute('INSERT INTO relationships VALUES (?,?,?,?,?,?,?,?)',(rid,*pair(user['id'],uid),'dating',user['id'],'accepted',now(),now()))
        elif rel['status']!='accepted':
            con.execute('UPDATE relationships SET status="accepted",updated_at=? WHERE id=?',(now(),rid))
        else:
            return {'matched':True,'id':rid}
        notify(con,user['id'],f'You and {target["display_name"]} have a mutual dating match.',rid)
        notify(con,uid,f'You and {user["display_name"]} have a mutual dating match.',rid)
        return {'matched':True,'id':rid}


    @app.post('/api/dating/{uid}/like')
    def like(uid: str, request: Request):
        # Legacy private Dating API; existing private likes are never published.
        with db(True) as con:
            user,_ = auth(con,request)
            limit(con,'dating:'+user['id'],40,3600)
            return like_dating(con,user,get_user(con,uid))

    def receipts(con, user, rid, peer):
        def cursor(table):
            row = con.execute(f'SELECT message_id FROM {table} WHERE user_id=? AND relationship_id=?',(peer,rid)).fetchone()
            return row[0] if row else 0
        read = cursor('read_cursors')
        return {'delivered':max(cursor('delivery_cursors'),read),'read':read}

    @app.get('/api/chats')
    def chats(request: Request):
        with db() as con:
            user,_ = auth(con,request)
            result = []
            rows = con.execute('SELECT id FROM relationships WHERE status="accepted" AND (low_id=? OR high_id=?)',(user['id'],user['id'])).fetchall()
            for row in rows:
                try:
                    rel,target = authorized_relation(con,user,row['id'])
                except HTTPException:
                    continue
                last = con.execute('SELECT * FROM messages WHERE relationship_id=? ORDER BY id DESC LIMIT 1',(row['id'],)).fetchone()
                cursor = con.execute('SELECT message_id FROM read_cursors WHERE user_id=? AND relationship_id=?',(user['id'],row['id'])).fetchone()
                unread = con.execute('SELECT count(*) FROM messages WHERE relationship_id=? AND sender_id!=? AND id>?',(row['id'],user['id'],cursor[0] if cursor else 0)).fetchone()[0]
                result.append({'id':row['id'],'kind':rel['kind'],'profile':public(con,target,dating=rel['kind']=='dating',viewer=user),'last_message':dict(last) if last else None,'unread':unread,'receipts':receipts(con,user,row['id'],target['id'])})
            result.sort(key=lambda c:(-(c['last_message']['id'] if c['last_message'] else 0),c['id']))
            return {'items':result}

    @app.get('/api/chats/{rid}/starters')
    def starters(rid: str, request: Request):
        with db() as con:
            user,_ = auth(con,request)
            rel,target = authorized_relation(con,user,rid)
            if rel['kind']!='dating':
                fail('Conversation starters are available inside active dating matches.',404)
            shared = set(interests(con,user['id'])).intersection(interests(con,target['id']))
            return {'items':conversation_starters(shared,public(con,target)['prompts'])}

    @app.get('/api/chats/{rid}/messages')
    def messages(rid: str, request: Request, before: int=0, after: int=0):
        if before<0 or after<0 or (before and after):
            fail('Invalid message cursor.',422)
        with db() as con:
            user,_ = auth(con,request)
            _,peer = authorized_relation(con,user,rid)
            if after:
                rows = con.execute('SELECT * FROM messages WHERE relationship_id=? AND id>? ORDER BY id LIMIT 51',(rid,after)).fetchall()
                items = rows[:50]
            else:
                rows = con.execute('SELECT * FROM messages WHERE relationship_id=? AND id<? ORDER BY id DESC LIMIT 51',(rid,before or 9223372036854775807)).fetchall()
                items = list(reversed(rows[:50]))
            return {'items':[dict(r) for r in items],'has_more':len(rows)>50,'receipts':receipts(con,user,rid,peer['id'])}

    @app.post('/api/chats/{rid}/messages')
    async def send_message(rid: str, request: Request):
        data = await payload(request)
        body, cid = text(data,'body',4000,1), text(data,'client_id',64,8)
        with db() as con:
            user,_ = auth(con,request)
            limit(con,'message:'+user['id'],90)
        with db(True) as con:
            user,_ = auth(con,request)
            rel,target = authorized_relation(con,user,rid)
            existing = con.execute('SELECT * FROM messages WHERE relationship_id=? AND sender_id=? AND client_id=?',(rid,user['id'],cid)).fetchone()
            if existing:
                if existing['body']!=body:
                    fail('This message key was already used for different text.',409)
                return {'message':dict(existing)}
            cur = con.execute('INSERT INTO messages(relationship_id,sender_id,client_id,body,created_at) VALUES (?,?,?,?,?)',(rid,user['id'],cid,body,now()))
            message = con.execute('SELECT * FROM messages WHERE id=?',(cur.lastrowid,)).fetchone()
            notify(con,target['id'],f'New {rel["kind"]} message from {user["display_name"]}.',rid)
            emit(con,user['id'])
            return {'message':dict(message)}

    def advance_cursor(con, table, uid, rid, mid):
        row = con.execute(f'SELECT message_id FROM {table} WHERE user_id=? AND relationship_id=?',(uid,rid)).fetchone()
        if mid <= (row[0] if row else 0):
            return False
        con.execute(f'INSERT INTO {table} VALUES (?,?,?) ON CONFLICT(user_id,relationship_id) DO UPDATE SET message_id=MAX(message_id,excluded.message_id)',(uid,rid,mid))
        return True

    @app.post('/api/chats/{rid}/delivered')
    @app.post('/api/chats/{rid}/read')
    async def acknowledge_messages(rid: str, request: Request):
        data = await payload(request)
        mid = number(data,'message_id',0,9223372036854775807,0)
        with db(True) as con:
            user,_ = auth(con,request)
            _,peer = authorized_relation(con,user,rid)
            if mid and not con.execute('SELECT 1 FROM messages WHERE id=? AND relationship_id=?',(mid,rid)).fetchone():
                fail('Message unavailable.',404)
            changed = advance_cursor(con,'delivery_cursors',user['id'],rid,mid)
            if request.url.path.endswith('/read'):
                changed = advance_cursor(con,'read_cursors',user['id'],rid,mid) or changed
            if changed:
                emit(con,user['id'],peer['id'])
            return {'ok':True}

    @app.get('/api/events')
    async def events(request: Request):
        with db() as con:
            user, session = auth(con,request)
            limit(con,'stream:'+user['id'],30)
            uid, session_hash = user['id'],session['token_hash']
            cursor = con.execute('SELECT COALESCE(MAX(id),0) FROM events WHERE user_id=?',(uid,)).fetchone()[0]
        async def stream():
            nonlocal cursor
            yield 'event: ready\ndata: {}\n\n'
            heartbeat = time.monotonic()
            while not await request.is_disconnected():
                with db() as con:
                    valid = con.execute('SELECT 1 FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.status="active"',(session_hash,now())).fetchone()
                    if not valid:
                        yield 'event: expired\ndata: {}\n\n'
                        return
                    latest = con.execute('SELECT COALESCE(MAX(id),0) FROM events WHERE user_id=?',(uid,)).fetchone()[0]
                if latest>cursor:
                    cursor = latest
                    # No messages, other-user IDs or private likes cross this channel.
                    yield f'id: {cursor}\nevent: refresh\ndata: {{}}\n\n'
                if time.monotonic()-heartbeat>15:
                    yield ': heartbeat\n\n'
                    heartbeat = time.monotonic()
                await asyncio.sleep(.35)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

    @app.get('/api/notifications')
    def notifications(request: Request):
        with db() as con:
            user,_ = auth(con,request)
            return {'items':[dict(r) for r in con.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100',(user['id'],))]}

    @app.post('/api/notifications/read')
    def read_notifications(request: Request):
        with db(True) as con:
            user,_ = auth(con,request)
            con.execute('UPDATE notifications SET read=1 WHERE user_id=?',(user['id'],))
            return {'ok':True}

    @app.get('/api/blocks')
    def blocks(request: Request):
        with db() as con:
            user,_ = auth(con,request)
            return {'items':[{'id':r['id'],'display_name':r['display_name'],'username':r['username']} for r in con.execute('SELECT u.* FROM users u JOIN blocks b ON b.blocked=u.id WHERE b.blocker=?',(user['id'],))]}

    @app.post('/api/blocks/{uid}')
    def block(uid: str, request: Request):
        with db(True) as con:
            user,_ = auth(con,request)
            get_user(con,uid)
            if uid==user['id']:
                fail('You cannot block yourself.',422)
            con.execute('INSERT OR IGNORE INTO blocks VALUES (?,?)',(user['id'],uid))
            con.execute('UPDATE relationships SET status="removed",updated_at=? WHERE low_id=? AND high_id=?',(now(),*pair(user['id'],uid)))
            con.execute('DELETE FROM dating_likes WHERE (sender=? AND target=?) OR (sender=? AND target=?)',(user['id'],uid,uid,user['id']))
            emit(con,user['id'],uid)
            return {'ok':True}

    @app.delete('/api/blocks/{uid}')
    def unblock(uid: str, request: Request):
        with db(True) as con:
            user,_ = auth(con,request)
            con.execute('DELETE FROM blocks WHERE blocker=? AND blocked=?',(user['id'],uid))
            emit(con,user['id'],uid)
            return {'ok':True}

    @app.post('/api/reports')
    async def report(request: Request):
        data = await payload(request)
        uid, reason, detail = text(data,'target_id',36,1), text(data,'reason',50,1), text(data,'detail',2000)
        if reason not in ('harassment','impersonation','spam','inappropriate','other'):
            fail('Choose a report reason.',422)
        with db() as con:
            user,_ = auth(con,request)
            limit(con,'report:'+user['id'],10,3600)
        with db(True) as con:
            user,_ = auth(con,request)
            get_user(con,uid)
            if uid==user['id']:
                fail('You cannot report yourself.',422)
            mid = data.get('message_id')
            if mid is not None:
                mid = number(data,'message_id',1,9223372036854775807)
                msg = con.execute('SELECT m.* FROM messages m JOIN relationships r ON r.id=m.relationship_id WHERE m.id=? AND m.sender_id=? AND (r.low_id=? OR r.high_id=?)',(mid,uid,user['id'],user['id'])).fetchone()
                if not msg:
                    fail('Message unavailable.',404)
            rid = str(uuid.uuid4())
            con.execute('INSERT INTO reports(id,reporter,target,message_id,reason,detail,created_at) VALUES (?,?,?,?,?,?,?)',(rid,user['id'],uid,mid,reason,detail,now()))
            return {'id':rid,'status':'open'}

    @app.get('/api/reports/mine')
    def my_reports(request: Request):
        with db() as con:
            user,_ = auth(con,request)
            return {'items':[dict(r) for r in con.execute('SELECT id,reason,status,created_at FROM reports WHERE reporter=? ORDER BY created_at DESC LIMIT 100',(user['id'],))]}

    def moderator(con,request):
        user,_ = auth(con,request)
        if user['role']!='moderator':
            fail('Moderator access required.',403)
        return user

    @app.get('/api/moderation/reports')
    def moderation_reports(request: Request):
        with db() as con:
            moderator(con,request)
            return {'items':[dict(r) for r in con.execute('SELECT r.*,u.display_name AS target_name,m.body AS message_body FROM reports r LEFT JOIN users u ON r.target=u.id LEFT JOIN messages m ON r.message_id=m.id ORDER BY r.created_at DESC LIMIT 100')]}

    @app.post('/api/moderation/reports/{rid}')
    async def resolve_report(rid: str, request: Request):
        data = await payload(request)
        action = data.get('action')
        if action not in ('resolve','dismiss','suspend'):
            fail('Invalid moderation action.',422)
        with db(True) as con:
            user = moderator(con,request)
            row = con.execute('SELECT * FROM reports WHERE id=?',(rid,)).fetchone()
            if not row:
                fail('Report unavailable.',404)
            if row['status']!='open':
                fail('This report is already closed.',409)
            if action=='suspend' and row['target']:
                if row['target']==user['id']:
                    fail('Another moderator must review this report.',403)
                con.execute('UPDATE users SET status="suspended" WHERE id=?',(row['target'],))
                con.execute('DELETE FROM sessions WHERE user_id=?',(row['target'],))
                peers = con.execute('SELECT low_id,high_id FROM relationships WHERE low_id=? OR high_id=?',(row['target'],row['target'])).fetchall()
                for peer in peers:
                    emit(con,*peer)
            con.execute('UPDATE reports SET status=? WHERE id=?',('dismissed' if action=='dismiss' else 'resolved',rid))
            con.execute('INSERT INTO moderation_audit(moderator,report_id,action,created_at) VALUES (?,?,?,?)',(user['id'],rid,action,now()))
            return {'ok':True}

    @app.get('/api/security/sessions')
    def sessions(request: Request):
        with db() as con:
            user,current = auth(con,request)
            return {'items':[{'current':r['token_hash']==current['token_hash'],'created_at':r['created_at'],'expires_at':r['expires_at']} for r in con.execute('SELECT * FROM sessions WHERE user_id=? AND expires_at>? ORDER BY created_at DESC',(user['id'],now()))]}

    @app.post('/api/security/revoke-others')
    def revoke(request: Request):
        with db(True) as con:
            user,session = auth(con,request)
            con.execute('DELETE FROM sessions WHERE user_id=? AND token_hash!=?',(user['id'],session['token_hash']))
            notify(con,user['id'],'Other sessions were signed out.')
            return {'ok':True}

    @app.post('/api/security/password')
    async def change_password(request: Request):
        data = await payload(request)
        old,new = text(data,'current_password',128,1),text(data,'new_password',128,12)
        with db() as con:
            user,_ = auth(con,request)
            limit(con,'password:'+user['id'],10,900)
        with db(True) as con:
            user,session = auth(con,request)
            if not check_password(old,user['password_hash']):
                fail('Current password is incorrect.',403)
            con.execute('UPDATE users SET password_hash=? WHERE id=?',(password_hash(new),user['id']))
            con.execute('DELETE FROM sessions WHERE user_id=? AND token_hash!=?',(user['id'],session['token_hash']))
            notify(con,user['id'],'Your password changed. Other sessions were signed out.')
            return {'ok':True}

    @app.post('/api/account/{action}')
    async def account_action(action: str, request: Request):
        if action not in ('delete','deactivate'):
            fail('Unknown account action.',404)
        data = await payload(request)
        with db(True) as con:
            user,_ = auth(con,request)
            if not check_password(text(data,'password',128,1),user['password_hash']):
                fail('Password is incorrect.',403)
            peers = con.execute('SELECT low_id,high_id FROM relationships WHERE low_id=? OR high_id=?',(user['id'],user['id'])).fetchall()
            for peer in peers:
                emit(con,*peer)
            if action=='delete':
                con.execute('DELETE FROM users WHERE id=?',(user['id'],))
            else:
                con.execute('UPDATE users SET status="deactivated",discoverable=0,dating_enabled=0 WHERE id=?',(user['id'],))
                con.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
            response = JSONResponse({'ok':True})
            response.delete_cookie('campuslink_session',path='/')
            return response

    install_social(app,db=db,auth=auth,payload=payload,text=text,number=number,fail=fail,now=now,limit=limit,emit=emit,notify=notify,public=public,get_user=get_user,blocked=blocked,campus_access=campus_access,pair=pair,authorized_relation=authorized_relation,dating_compatible=dating_compatible,like_dating=like_dating)

    if deployment.mode=='staging':
        app.add_middleware(StagingAccess,deployment=deployment)

    app.mount('/assets',StaticFiles(directory=ROOT/'web'),name='assets')

    @app.get('/{path:path}')
    def frontend(path: str):
        if path.startswith('api/'):
            fail('Endpoint not found.',404)
        return FileResponse(ROOT/'web'/'index.html')

    return app


app = create_app()
