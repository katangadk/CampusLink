"""Fail-closed settings and access control for the restricted hosted test."""
import base64
import binascii
import hashlib
import hmac
from html import escape
import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
import re
import secrets
import time
from urllib.parse import parse_qs, unquote, urlencode, urlsplit
import uuid

from fastapi import HTTPException, Request
from starlette.datastructures import MutableHeaders
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response


ACCESS_COOKIE = '__Host-campuslink_staging'
ACCESS_SECONDS = 7 * 86400
ACCESS_PATH = '/tester-access'
ACCESS_CSRF_COOKIE = '__Host-campuslink_staging_csrf'


def access_next(value):
    """Only return a local navigation target, never another access form."""
    try:
        if not isinstance(value, str) or len(value) > 1024:
            return '/signup'
        decoded = unquote(value)
        if (not decoded.startswith('/') or decoded.startswith('//') or '\\' in decoded
                or any(ord(c) < 32 or ord(c) == 127 for c in decoded)):
            return '/signup'
        parsed = urlsplit(decoded)
        if parsed.scheme or parsed.netloc or parsed.path.rstrip('/') == ACCESS_PATH:
            return '/signup'
        return value
    except ValueError:
        return '/signup'


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

    def access_signature(self, value):
        # Bind the separate tester session to this service and its current
        # credentials. Rotating either credential invalidates existing cookies.
        message = '\0'.join(('campuslink-staging-v1', self.origin, self.gate_user, value))
        return hmac.new(self.gate_password.encode(), message.encode(), hashlib.sha256).hexdigest()

    def access_cookie(self):
        value = f'{int(time.time()) + ACCESS_SECONDS}.{secrets.token_urlsafe(24)}'
        return value + '.' + self.access_signature(value)

    def valid_access_cookie(self, request):
        try:
            cookie = request.cookies.get(ACCESS_COOKIE, '')
            if len(cookie) > 160:
                return False
            expires, nonce, signature = cookie.split('.')
            if not re.fullmatch(r'[0-9]{1,12}', expires) or not re.fullmatch(r'[A-Za-z0-9_-]{32}', nonce):
                return False
            now = int(time.time())
            if not now < int(expires) <= now + ACCESS_SECONDS:
                return False
            return secrets.compare_digest(signature, self.access_signature(expires + '.' + nonce))
        except (ValueError, TypeError):
            return False

    def valid_credentials(self, user, password):
        def equal(a, b):
            return secrets.compare_digest(hashlib.sha256(a.encode()).digest(), hashlib.sha256(b.encode()).digest())
        user_ok, password_ok = equal(user, self.gate_user), equal(password, self.gate_password)
        return user_ok and password_ok

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
        if self.valid_access_cookie(request):
            return None
        try:
            scheme, encoded = request.headers.get('authorization', '').split(' ', 1)
            if scheme.lower() != 'basic' or len(encoded) > 1024:
                raise ValueError()
            user, password = base64.b64decode(encoded, validate=True).decode('utf-8').split(':', 1)
            if self.valid_credentials(user, password):
                return None
        except (ValueError, UnicodeDecodeError, binascii.Error):
            pass
        # Never challenge with WWW-Authenticate: even an incorrect password
        # must produce a normal, usable page instead of a repeating modal.
        return JSONResponse({'detail': 'Tester access is required. Open the tester access page.',
                             'tester_access_required': True}, 401)


class StagingAccess:
    """Protect every HTTP route, including static files and the SSE stream."""
    def __init__(self, app, *, deployment, record_failure):
        self.app, self.deployment, self.record_failure = app, deployment, record_failure
        self.template = (Path(__file__).resolve().parent.parent / 'web' / 'tester-access.html').read_text()

    def remember(self, response):
        response.set_cookie(ACCESS_COOKIE, self.deployment.access_cookie(),
            max_age=ACCESS_SECONDS, path='/', secure=True, httponly=True, samesite='lax')

    def access_page(self, request, target, error='', status=200):
        csrf = request.cookies.get(ACCESS_CSRF_COOKIE, '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', csrf):
            csrf = secrets.token_urlsafe(32)
        values = {'NEXT':escape(access_next(target), quote=True), 'CSRF':csrf,
                  'ERROR':'<p class="error" role="alert">' + escape(error) + '</p>' if error else ''}
        html = re.sub(r'{{(NEXT|CSRF|ERROR)}}', lambda match:values[match[1]], self.template)
        response = HTMLResponse(html, status_code=status)
        response.headers['Content-Security-Policy'] = ("default-src 'none'; style-src 'unsafe-inline'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        response.set_cookie(ACCESS_CSRF_COOKIE, csrf, max_age=1800,
            path='/', secure=True, httponly=True, samesite='lax')
        return response

    async def access_form(self, request):
        target = access_next(request.query_params.get('next', '/signup'))
        if request.method == 'GET':
            if self.deployment.valid_access_cookie(request):
                return RedirectResponse(target, status_code=303)
            error = ''
            if request.query_params.get('check') == '1':
                error = 'Your browser did not keep the access cookie. Allow cookies for this site and try again.'
            return self.access_page(request, target, error)
        if request.method != 'POST':
            return Response(status_code=405, headers={'Allow':'GET, POST'})
        if (request.headers.get('origin') != self.deployment.origin
                or request.headers.get('sec-fetch-site') == 'cross-site'):
            return self.access_page(request, target, 'Reload this page and try again.', 403)
        if request.headers.get('content-type', '').split(';',1)[0].strip().lower() != 'application/x-www-form-urlencoded':
            return self.access_page(request, target, 'Submit the access form to continue.', 415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                return self.access_page(request, target, 'This request is too large. Reload and try again.', 413)
        try:
            fields = parse_qs(body.decode('utf-8'), keep_blank_values=True, strict_parsing=True, max_num_fields=3)
            if any(len(v) != 1 for v in fields.values()) or set(fields) != {'password','csrf','next'}:
                raise ValueError()
            fields = {k:v[0] for k,v in fields.items()}
            target = access_next(fields['next'])
            csrf = request.cookies.get(ACCESS_CSRF_COOKIE, '')
            if not re.fullmatch(r'[A-Za-z0-9_-]{43}', csrf):
                return self.access_page(request, target,
                    'This access form expired or cookies are blocked. Allow cookies for this site, then reload and try again.', 403)
            if not secrets.compare_digest(csrf, fields['csrf']):
                raise ValueError()
        except (ValueError, UnicodeError, TypeError):
            return self.access_page(request, target, 'This access form expired. Reload the page and try again.', 403)
        if not self.deployment.valid_credentials(self.deployment.gate_user, fields['password']):
            try:
                self.record_failure(request.client.host if request.client else 'unknown')
            except HTTPException:
                response = self.access_page(request, target, 'Too many attempts. Wait a minute and try again.', 429)
                response.headers['Retry-After'] = '60'
                return response
            return self.access_page(request, target,
                'That access password was not accepted. Try again or ask the person who shared this test site for the current password.', 401)
        # Check cookie persistence before navigating back. A browser that blocks
        # cookies receives a clear error, never an endless sign-in redirect.
        response = RedirectResponse(ACCESS_PATH + '?' + urlencode({'next':target,'check':'1'}), status_code=303)
        self.remember(response)
        response.delete_cookie(ACCESS_CSRF_COOKIE, path='/', secure=True, httponly=True, samesite='lax')
        return response

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        error = self.deployment.request_error(request)
        health_probe = request.method == 'GET' and request.url.path == '/api/health'
        remember = error is None and not health_probe and request.url.path != ACCESS_PATH and not self.deployment.valid_access_cookie(request)
        async def restricted_send(message):
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                headers['Cache-Control'] = 'no-store'
                headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
                headers['X-Content-Type-Options'] = 'nosniff'
                headers['Referrer-Policy'] = 'same-origin'
                if request.url.scheme == 'https':
                    headers['Strict-Transport-Security'] = 'max-age=15552000'
                if remember:
                    # Account APIs also use 401. Browsers can discard cached
                    # Basic credentials on those responses, reopening their
                    # native prompt. Keep tester access separate from app login.
                    response = Response()
                    self.remember(response)
                    headers.append('Set-Cookie', response.headers['set-cookie'])
            await send(message)
        if request.url.path == ACCESS_PATH and (error is None or error.status_code == 401):
            response = await self.access_form(request)
            await response(scope, receive, restricted_send)
            return
        if error is not None:
            if error.status_code == 401:
                if request.headers.get('authorization'):
                    try:
                        self.record_failure(request.client.host if request.client else 'unknown')
                    except HTTPException as exc:
                        error = JSONResponse({'detail': exc.detail}, exc.status_code, headers={'Retry-After': '60'})
                if error.status_code == 401 and request.method == 'GET' and not request.url.path.startswith(('/api/', '/assets/')):
                    target = access_next(request.url.path + ('?' + request.url.query if request.url.query else ''))
                    error = RedirectResponse(ACCESS_PATH + '?' + urlencode({'next':target}), status_code=303)
            await error(scope, receive, restricted_send)
            return
        await self.app(scope, receive, restricted_send)
