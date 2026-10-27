import base64
import sqlite3
import uuid

from fastapi.testclient import TestClient
import pytest

from campuslink.app import create_app, ROOT
from campuslink.backup import backup_database
from campuslink.deployment import Deployment
from campuslink.seed import seed
from campuslink.serve import options
from .test_photos import image_bytes

ORIGIN = 'https://staging.campuslink.test'
PASSWORD = 'Individual-test-password-2026!'


@pytest.fixture
def staging(monkeypatch, tmp_path):
    for name in ('RENDER','RENDER_EXTERNAL_URL','CAMPUSLINK_STAGING_USERNAME','CAMPUSLINK_STAGING_PASSWORD'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('CAMPUSLINK_MODE', 'staging')
    monkeypatch.setenv('CAMPUSLINK_REQUIRE_APPROVAL', 'false')
    monkeypatch.setenv('CAMPUSLINK_DB', str(tmp_path / 'staging.sqlite3'))
    monkeypatch.setenv('CAMPUSLINK_BASE_URL', ORIGIN)
    return create_app()


def client(app, origin=ORIGIN):
    return TestClient(app, base_url=origin)


def register(c, name):
    r = c.post('/api/auth/register', json={'username': name, 'display_name': name,
        'email': name + '@campuslink.test', 'password': PASSWORD, 'agreement': True})
    assert r.status_code == 200, r.text
    assert 'Secure' in r.headers['set-cookie'] and 'HttpOnly' in r.headers['set-cookie']
    assert r.json()['user']['verified'] is False
    c.headers['X-CSRF-Token'] = r.json()['csrf']
    return r.json()['user']


@pytest.mark.parametrize('path', ['/', '/signup', '/login', '/assets/app.js', '/api/catalog'])
def test_visitors_open_website_directly_without_shared_credentials(staging, path):
    response = client(staging).get(path, follow_redirects=False)
    assert response.status_code == 200
    assert 'location' not in response.headers and 'WWW-Authenticate' not in response.headers
    assert 'set-cookie' not in response.headers
    assert 'tester-access-form' not in response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow, noarchive'
    assert response.headers['Strict-Transport-Security'].startswith('max-age=')


@pytest.mark.parametrize('path', ['/api/me','/api/feed','/api/chats','/api/notifications',
    '/api/message-requests','/api/events','/api/photos/unknown','/api/post-photos/unknown',
    '/api/profiles/unknown','/api/security/sessions'])
def test_private_data_and_live_events_still_require_account_login(staging, path):
    response = client(staging).get(path)
    assert response.status_code == 401
    assert response.json()['detail'] == 'Please sign in again.'
    assert 'WWW-Authenticate' not in response.headers
    assert 'tester_access_required' not in response.json()


def test_health_is_minimal_and_catalog_hides_demo_accounts(staging):
    r = client(staging, origin='http://internal-probe').get('/api/health')
    assert r.status_code == 200 and r.json() == {'status':'ok','mode':'staging','public_launch_ready':False}
    assert 'database' not in r.text
    catalog = client(staging).get('/api/catalog').json()
    assert catalog['mode'] == 'staging' and catalog['demo_accounts_available'] is False


def test_only_individual_account_password_is_required_and_session_survives_restart(staging):
    c = client(staging)
    user = register(c, 'direct_ada')
    cookie = c.cookies.get('campuslink_session')
    assert cookie and '__Host-campuslink_staging' not in c.cookies
    assert c.get('/api/me').json()['user']['id'] == user['id']
    restored = client(create_app())
    restored.cookies.update(c.cookies)
    assert restored.get('/api/me').json()['user']['id'] == user['id']
    assert c.patch('/api/me',json={'bio':'wrong'},headers={'X-CSRF-Token':'invalid'}).status_code == 403
    assert c.post('/api/auth/logout',json={}).status_code == 200
    assert c.get('/api/me').status_code == 401
    assert c.get('/login').status_code == 200
    wrong = c.post('/api/auth/login',json={'email':'direct_ada@campuslink.test','password':'wrong'})
    assert wrong.status_code == 401 and 'WWW-Authenticate' not in wrong.headers
    signed_in = c.post('/api/auth/login',json={'email':'direct_ada@campuslink.test','password':PASSWORD})
    assert signed_in.status_code == 200
    assert c.get('/api/me').json()['user']['id'] == user['id']


@pytest.mark.parametrize('legacy_password', ['', 'short', 'Old-shared-access-password-2026!'])
def test_old_render_password_settings_do_not_enable_a_gate(staging, monkeypatch, legacy_password):
    monkeypatch.setenv('CAMPUSLINK_STAGING_USERNAME','old-tester')
    monkeypatch.setenv('CAMPUSLINK_STAGING_PASSWORD',legacy_password)
    c = client(create_app())
    c.headers['Authorization'] = 'Basic ' + base64.b64encode(('old-tester:'+legacy_password).encode()).decode()
    c.cookies.set('__Host-campuslink_staging','old-cookie')
    assert c.get('/signup',follow_redirects=False).status_code == 200
    assert c.get('/api/me').status_code == 401
    if legacy_password:
        assert legacy_password not in repr(Deployment.load(ROOT))


@pytest.mark.parametrize('method', ['GET','POST'])
def test_old_tester_access_bookmark_returns_to_website(staging, method):
    response = client(staging).request(method, '/tester-access?next=https://attacker.test',follow_redirects=False)
    assert response.status_code == 303 and response.headers['location'] == '/'
    assert 'WWW-Authenticate' not in response.headers and 'set-cookie' not in response.headers


def test_hosted_preview_keeps_https_and_canonical_host_checks(staging):
    insecure = client(staging, origin=ORIGIN.replace('https:','http:'))
    assert insecure.get('/').status_code == 403
    assert insecure.get('/api/catalog',headers={'X-Forwarded-Proto':'https'}).status_code == 403
    assert client(staging,origin='https://other.test').get('/').status_code == 400
    assert client(staging).get('/',headers={'Host':'staging.campuslink.test:443'}).status_code == 200


def test_trusted_proxy_preserves_https_origin_and_secure_sessions(staging):
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    trusted = client(ProxyHeadersMiddleware(staging,trusted_hosts='testclient'),origin=ORIGIN.replace('https:','http:'))
    trusted.headers['X-Forwarded-Proto'] = 'https'
    trusted.headers['Origin'] = ORIGIN
    register(trusted,'proxy_tester')
    untrusted = client(ProxyHeadersMiddleware(staging,trusted_hosts='10.0.0.1'),origin=ORIGIN.replace('https:','http:'))
    assert untrusted.get('/',headers={'X-Forwarded-Proto':'https'}).status_code == 403


def test_direct_registration_rejects_cross_origin_requests(staging):
    response = client(staging).post('/api/auth/register',json={},headers={'Origin':'https://attacker.test'})
    assert response.status_code == 403


def test_staging_keeps_csrf_and_persists_accounts_messages_photos_after_backup(staging, tmp_path):
    a, b = client(staging), client(staging)
    ua, ub = register(a,'private_ada'), register(b,'private_ben')
    assert a.patch('/api/me',json={'bio':'wrong'},headers={'X-CSRF-Token':'invalid'}).status_code == 403
    assert a.patch('/api/me',json={'bio':'wrong'},headers={'Origin':'https://attacker.test'}).status_code == 403
    for c in (a,b):
        assert c.patch('/api/me',json={'program':'Computer Science','onboarding_step':6}).status_code == 200
    rid = a.post('/api/connections',json={'target_id':ub['id'],'kind':'friend'}).json()['id']
    assert b.post('/api/connections/'+rid+'/accept',json={}).status_code == 200
    r = a.post('/api/chats/'+rid+'/messages',json={'body':'A persisted hosted test message.','client_id':str(uuid.uuid4())})
    assert r.status_code == 200
    photo = a.post('/api/me/photos',content=image_bytes(),headers={'Content-Type':'image/png','X-Upload-Id':str(uuid.uuid4())})
    assert photo.status_code == 200, photo.text
    url = photo.json()['user']['main_photo_url']
    original = b.get(url).content
    assert client(staging).get(url).status_code == 401
    backup = backup_database(staging.state.db_path,tmp_path/'backup.sqlite3')
    assert backup.stat().st_mode & 0o777 == 0o600
    restored = create_app(backup)
    c = client(restored);c.cookies.update(a.cookies)
    assert c.get('/api/me').json()['user']['id'] == ua['id']
    assert c.get('/api/chats/'+rid+'/messages').json()['items'][0]['body'] == 'A persisted hosted test message.'
    assert c.get(url).content == original


def test_backup_never_overwrites_or_creates_missing_source(staging, tmp_path):
    dest = tmp_path/'backup.sqlite3'
    backup_database(staging.state.db_path,dest)
    before = dest.read_bytes()
    with pytest.raises(FileExistsError):
        backup_database(staging.state.db_path,dest)
    assert dest.read_bytes() == before
    with pytest.raises(ValueError):
        backup_database(staging.state.db_path,staging.state.db_path)
    missing = tmp_path/'missing.sqlite3'
    with pytest.raises(sqlite3.OperationalError):
        backup_database(missing,tmp_path/'should-not-exist.sqlite3')
    assert not missing.exists() and not (tmp_path/'should-not-exist.sqlite3').exists()


@pytest.mark.parametrize('key,value', [('CAMPUSLINK_MODE','public'),('CAMPUSLINK_MODE','production'),
    ('CAMPUSLINK_DB','relative.sqlite3'),('CAMPUSLINK_DB',str(ROOT/'data'/'accidental.sqlite3')),
    ('CAMPUSLINK_BASE_URL',''),('CAMPUSLINK_BASE_URL','http://example.test'),
    ('CAMPUSLINK_BASE_URL','https://user:pass@example.test'),('CAMPUSLINK_BASE_URL','https://example.test/path'),
    ('CAMPUSLINK_BASE_URL','https://example.test?query=1'),('CAMPUSLINK_BASE_URL','https://localhost'),
    ('CAMPUSLINK_BASE_URL','https://bad host.test'),('CAMPUSLINK_BASE_URL','https://example..test')])
def test_invalid_hosted_settings_refuse_startup(staging, monkeypatch, key, value):
    monkeypatch.setenv(key,value)
    with pytest.raises(RuntimeError) as exc:
        create_app()
    assert PASSWORD not in str(exc.value)


def test_render_requires_hosted_mode_and_uses_its_canonical_https_url(staging, monkeypatch):
    monkeypatch.setenv('RENDER','true')
    monkeypatch.delenv('CAMPUSLINK_BASE_URL')
    monkeypatch.setenv('RENDER_EXTERNAL_URL',ORIGIN)
    assert Deployment.load(ROOT).origin == ORIGIN
    _,opts = options()
    assert opts['workers'] == 1 and opts['proxy_headers'] and opts['forwarded_allow_ips'] == '*'
    monkeypatch.setenv('CAMPUSLINK_MODE','local')
    with pytest.raises(RuntimeError):
        create_app()


def test_staging_cannot_seed_or_import_known_demo_accounts(staging, monkeypatch, tmp_path):
    absent = tmp_path/'never-created.sqlite3'
    with pytest.raises(RuntimeError,match='seeding'):
        seed(absent)
    assert not absent.exists()
    seeded = tmp_path/'copied-local.sqlite3'
    with monkeypatch.context() as local:
        local.setenv('CAMPUSLINK_MODE','local')
        seed(seeded)
    with pytest.raises(RuntimeError,match='demo accounts'):
        create_app(seeded)


def test_launcher_validates_port(staging, monkeypatch):
    monkeypatch.setenv('PORT','12345')
    _,opts=options()
    assert opts['port'] == 12345 and opts['forwarded_allow_ips'] == '127.0.0.1'
    monkeypatch.setenv('PORT','not-a-port')
    with pytest.raises(RuntimeError):
        options()
