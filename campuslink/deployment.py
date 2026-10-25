"""Fail-closed settings and access control for the restricted hosted test."""
import base64
import binascii
import hashlib
import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit
import uuid

from fastapi import HTTPException, Request
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse


@dataclass(frozen=True)
class Deployment:
    mode: str
    database: Path
    origin: str = ''
    gate_user: str = ''
    gate_password: str = field(default='', repr=False)

    @classmethod
    def load(cls, root: Path, db_path=None):
        mode = os.getenv('CAMPUSLINK_MODE', 'local')
        if mode not in ('local', 'staging'):
            raise RuntimeError('Public launch is disabled: configure a reviewed student/adult eligibility provider first.')
        if os.getenv('RENDER') == 'true' and mode != 'staging':
            raise RuntimeError('Render requires CAMPUSLINK_MODE=staging and restricted tester access.')
        raw_db = str(db_path or os.getenv('CAMPUSLINK_DB', root / 'data' / 'campuslink.sqlite3'))
        database = Path(raw_db).expanduser()
        if mode == 'local':
            return cls(mode, database.resolve())
        if not database.is_absolute() or database.resolve().is_relative_to((root / 'data').resolve()):
            raise RuntimeError('Staging requires an absolute CAMPUSLINK_DB on separate persistent storage, outside the local data directory.')
        base = os.getenv('CAMPUSLINK_BASE_URL') or os.getenv('RENDER_EXTERNAL_URL', '')
        try:
            parsed = urlsplit(base)
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                    or parsed.query or parsed.fragment or parsed.path not in ('', '/') or parsed.port == 0
                    or parsed.hostname in ('localhost', '127.0.0.1', '::1')):
                raise ValueError()
            host = parsed.hostname.encode('idna').decode('ascii').lower()
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                if len(host) > 253 or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in host.split('.')):
                    raise ValueError()
            else:
                if address.is_loopback:
                    raise ValueError()
            authority = host
            if ':' in authority:
                authority = '[' + authority + ']'
            if parsed.port not in (None, 443):
                authority += ':' + str(parsed.port)
        except (ValueError, UnicodeError):
            raise RuntimeError('Staging requires a valid HTTPS CAMPUSLINK_BASE_URL (or RENDER_EXTERNAL_URL), with no path, credentials or query.') from None
        user = os.getenv('CAMPUSLINK_STAGING_USERNAME', '')
        password = os.getenv('CAMPUSLINK_STAGING_PASSWORD', '')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}', user):
            raise RuntimeError('Set CAMPUSLINK_STAGING_USERNAME to 3–64 letters, numbers, dots, underscores or hyphens.')
        if not 24 <= len(password) <= 128 or password != password.strip() or any(ord(c) < 32 for c in password):
            raise RuntimeError('Set CAMPUSLINK_STAGING_PASSWORD to a random 24–128 character secret without surrounding whitespace.')
        if password.lower().startswith(('replace', 'change', 'example')):
            raise RuntimeError('Replace the staging password placeholder with a random secret.')
        return cls(mode, database.resolve(), 'https://' + authority, user, password)

    def reject_fixture_database(self, con):
        if self.mode != 'staging':
            return
        # Importing fixture definitions does not seed or initialize a database.
        from .seed import FIXTURES, DATING_FIXTURES
        names = [row[0] for row in FIXTURES + DATING_FIXTURES] + ['moderator']
        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, 'campuslink-local:' + name)) for name in names]
        if con.execute('SELECT 1 FROM users WHERE id IN (' + ','.join('?' for _ in ids) + ') LIMIT 1', ids).fetchone():
            raise RuntimeError('Staging refuses supplied demo accounts. Use a clean persistent database and create individual tester accounts.')

    def request_error(self, request):
        if request.method == 'GET' and request.url.path == '/api/health':
            return None
        expected = urlsplit(self.origin).netloc
        actual = request.headers.get('host', '').lower()
        if actual.endswith(':443'):
            actual = actual[:-4]
        if actual != expected:
            return JSONResponse({'detail': 'Host unavailable.'}, 400)
        if request.url.scheme != 'https':
            return JSONResponse({'detail': 'This restricted test requires HTTPS.'}, 403)
        try:
            scheme, encoded = request.headers.get('authorization', '').split(' ', 1)
            if scheme.lower() != 'basic' or len(encoded) > 1024:
                raise ValueError()
            user, password = base64.b64decode(encoded, validate=True).decode('utf-8').split(':', 1)
            def equal(a, b):
                return secrets.compare_digest(hashlib.sha256(a.encode()).digest(), hashlib.sha256(b.encode()).digest())
            user_ok, password_ok = equal(user, self.gate_user), equal(password, self.gate_password)
            if user_ok and password_ok:
                return None
        except (ValueError, UnicodeDecodeError, binascii.Error):
            pass
        return JSONResponse({'detail': 'Restricted CampusLink test. Tester access is required.'}, 401,
                            headers={'WWW-Authenticate': 'Basic realm="CampusLink private test", charset="UTF-8"'})


class StagingAccess:
    """Protect every HTTP route, including static files and the SSE stream."""
    def __init__(self, app, *, deployment, record_failure):
        self.app, self.deployment, self.record_failure = app, deployment, record_failure

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        async def restricted_send(message):
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                headers['Cache-Control'] = 'no-store'
                headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
                headers['X-Content-Type-Options'] = 'nosniff'
                headers['Referrer-Policy'] = 'same-origin'
                if request.url.scheme == 'https':
                    headers['Strict-Transport-Security'] = 'max-age=15552000'
            await send(message)
        error = self.deployment.request_error(request)
        if error is not None:
            if error.status_code == 401:
                try:
                    self.record_failure(request.client.host if request.client else 'unknown')
                except HTTPException as exc:
                    error = JSONResponse({'detail': exc.detail}, exc.status_code, headers={'Retry-After': '60'})
            await error(scope, receive, restricted_send)
            return
        await self.app(scope, receive, restricted_send)
