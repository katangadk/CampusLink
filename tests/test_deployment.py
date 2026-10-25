import base64
from pathlib import Path
import sqlite3
import uuid

from fastapi.testclient import TestClient
import pytest

from campuslink.app import create_app, ROOT
from campuslink.backup import backup_database
from campuslink.deployment import Deployment
from campuslink.seed import seed
from campuslink.serve import options
from .conftest import sql
from .test_photos import image_bytes

USER = 'private-tester'
PASSWORD = 'Synthetic-staging-gate-2026-only!'
ORIGIN = 'https://staging.campuslink.test'


@pytest.fixture
def staging(monkeypatch, tmp_path):
    monkeypatch.delenv('RENDER', raising=False)
    monkeypatch.delenv('RENDER_EXTERNAL_URL', raising=False)
    monkeypatch.setenv('CAMPUSLINK_MODE', 'staging')
    monkeypatch.setenv('CAMPUSLINK_DB', str(tmp_path / 'staging.sqlite3'))
    monkeypatch.setenv('CAMPUSLINK_BASE_URL', ORIGIN)
    monkeypatch.setenv('CAMPUSLINK_STAGING_USERNAME', USER)
    monkeypatch.setenv('CAMPUSLINK_STAGING_PASSWORD', PASSWORD)
    return create_app()


def client(app, gate=True, origin=ORIGIN):
    c = TestClient(app, base_url=origin)
    if gate:
        c.headers['Authorization'] = 'Basic ' + base64.b64encode((USER + ':' + PASSWORD).encode()).decode()
    return c


def register(c, name):
    r = c.post('/api/auth/register', json={'username': name, 'display_name': name,
        'email': name + '@campuslink.test', 'password': 'Individual-test-password-2026!', 'agreement': True})
    assert r.status_code == 200, r.text
    assert 'Secure' in r.headers['set-cookie'] and 'HttpOnly' in r.headers['set-cookie']
    assert r.json()['user']['verified'] is False
    c.headers['X-CSRF-Token'] = r.json()['csrf']
    return r.json()['user']


@pytest.mark.parametrize('path,method', [('/', 'GET'),('/signup','GET'),('/assets/app.js','GET'),
    ('/api/catalog','GET'),('/api/events','GET'),('/api/feed','GET'),('/api/me/photos','POST'),
    ('/api/auth/register','POST'),('/api/photos/unknown','GET'),('/api/post-photos/unknown','GET')])
def test_gate_protects_pages_assets_apis_photos_and_streams(staging, path, method):
    response = client(staging, gate=False).request(method, path)
    assert response.status_code == 401
    assert response.headers['WWW-Authenticate'].startswith('Basic ')
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow, noarchive'
    assert response.headers['Strict-Transport-Security'].startswith('max-age=')
    assert PASSWORD not in response.text


def test_health_is_public_and_gate_does_not_replace_account_login(staging):
    r = client(staging, gate=False, origin='http://internal-probe').get('/api/health')
    assert r.status_code == 200 and r.json() == {'status':'ok','mode':'staging','public_launch_ready':False}
    assert 'database' not in r.text and USER not in r.text
    c = client(staging)
    catalog = c.get('/api/catalog').json()
    assert catalog['mode'] == 'staging' and catalog['demo_accounts_available'] is False
    assert c.get('/api/me').status_code == 401  # Gate credentials are not a student session.
    assert c.get('/assets/app.js').status_code == 200


@pytest.mark.parametrize('authorization', ['Bearer test','Basic invalid!', 'Basic ',
    'Basic ' + base64.b64encode(b'wrong:wrong').decode(),
    'Basic ' + base64.b64encode(b'no-colon').decode(),
    'Basic ' + base64.b64encode(b'\xff:invalid').decode()])
def test_malformed_or_wrong_gate_credentials_fail_closed(staging, authorization):
    r = client(staging, gate=False).get('/api/catalog', headers={'Authorization':authorization})
    assert r.status_code == 401


def test_gate_rejects_http_wrong_hosts_and_spoofed_proxy_headers(staging):
    c = client(staging, origin=ORIGIN.replace('https:', 'http:'))
    assert c.get('/api/catalog', headers={'X-Forwarded-Proto':'https'}).status_code == 403
    assert client(staging, origin='https://other.test').get('/api/catalog', headers={'X-Forwarded-Host':'staging.campuslink.test'}).status_code == 400
    assert client(staging).get('/api/catalog', headers={'Host':'staging.campuslink.test:443'}).status_code == 200


def test_trusted_proxy_preserves_https_origin_and_secure_sessions(staging):
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    trusted = client(ProxyHeadersMiddleware(staging, trusted_hosts='testclient'), origin=ORIGIN.replace('https:', 'http:'))
    trusted.headers['X-Forwarded-Proto'] = 'https'
    trusted.headers['Origin'] = ORIGIN
    register(trusted, 'proxy_tester')
    untrusted = client(ProxyHeadersMiddleware(staging, trusted_hosts='10.0.0.1'), origin=ORIGIN.replace('https:', 'http:'))
    assert untrusted.get('/api/catalog',headers={'X-Forwarded-Proto':'https'}).status_code == 403


def test_wrong_gate_attempts_are_limited_without_locking_out_valid_testers(staging):
    c = client(staging, gate=False)
    assert c.get('/api/catalog').status_code == 401
    sql(staging, 'UPDATE rate_limits SET count=30 WHERE key="staging-gate:testclient"')
    assert c.get('/api/catalog').status_code == 429
    assert client(staging).get('/api/catalog').status_code == 200
    assert c.get('/api/health').status_code == 200


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
    assert client(staging,gate=False).get(url).status_code == 401
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
    ('CAMPUSLINK_BASE_URL','https://bad host.test'),('CAMPUSLINK_BASE_URL','https://example..test'),
    ('CAMPUSLINK_STAGING_USERNAME',''),('CAMPUSLINK_STAGING_USERNAME','user:name'),
    ('CAMPUSLINK_STAGING_PASSWORD',''),('CAMPUSLINK_STAGING_PASSWORD','short'),
    ('CAMPUSLINK_STAGING_PASSWORD','replace-this-with-a-random-password')])
def test_invalid_hosted_settings_refuse_startup(staging, monkeypatch, key, value):
    monkeypatch.setenv(key,value)
    with pytest.raises(RuntimeError) as exc:
        create_app()
    assert PASSWORD not in str(exc.value)


def test_render_requires_gate_and_uses_its_canonical_https_url(staging, monkeypatch):
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


def test_gate_secret_not_in_settings_repr_and_launcher_validates_port(staging, monkeypatch):
    assert PASSWORD not in repr(Deployment.load(ROOT))
    monkeypatch.setenv('PORT','12345')
    _,opts=options()
    assert opts['port'] == 12345 and opts['forwarded_allow_ips'] == '127.0.0.1'
    monkeypatch.setenv('PORT','not-a-port')
    with pytest.raises(RuntimeError):
        options()
