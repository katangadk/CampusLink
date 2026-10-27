"""Hosted preview settings, canonical-host checks and HTTPS enforcement."""
import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import urlsplit
import uuid

from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse, RedirectResponse


@dataclass(frozen=True)
class Deployment:
    mode: str
    database: Path
    origin: str = ''

    @classmethod
    def load(cls, root: Path, db_path=None):
        mode = os.getenv('CAMPUSLINK_MODE', 'local')
        if mode not in ('local', 'staging'):
            raise RuntimeError('Production mode requires a reviewed student/adult eligibility provider; use staging for the hosted preview.')
        if os.getenv('RENDER') == 'true' and mode != 'staging':
            raise RuntimeError('Render requires CAMPUSLINK_MODE=staging.')
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
        return cls(mode, database.resolve(), 'https://' + authority)

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
            return JSONResponse({'detail': 'This hosted preview requires HTTPS.'}, 403)
        return None


class StagingAccess:
    """Keep hosted transport checks independent of individual account login."""
    def __init__(self, app, *, deployment):
        self.app, self.deployment = app, deployment

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        async def secure_send(message):
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
            await error(scope, receive, secure_send)
            return
        # Old shared-access bookmarks go straight to the website too.
        if request.url.path == '/tester-access':
            await RedirectResponse('/', status_code=303)(scope, receive, secure_send)
            return
        await self.app(scope, receive, secure_send)
