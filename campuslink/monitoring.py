"""Bounded, content-free request metrics for the operator console."""
from collections import deque
import logging
import threading
import time
import uuid

from starlette.datastructures import MutableHeaders


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.requests = self.errors = self.active_streams = 0
        self.timings = deque(maxlen=1000)

    def snapshot(self):
        with self.lock:
            values = sorted(self.timings)
            percentile = lambda p: round(values[min(len(values)-1, int((len(values)-1)*p))], 2) if values else 0
            return {'uptime_seconds':int(time.monotonic()-self.started),
                    'requests':self.requests, 'server_errors':self.errors,
                    'active_streams':self.active_streams, 'sample_size':len(values),
                    'latency_ms':{'p50':percentile(.5),'p95':percentile(.95),'p99':percentile(.99)}}


class RequestMetrics:
    def __init__(self, app, *, metrics):
        self.app, self.metrics = app, metrics

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid.uuid4().hex
        started, status = time.monotonic(), 500
        stream = scope.get('path') == '/api/events'
        if stream:
            with self.metrics.lock:
                self.metrics.active_streams += 1
        async def measured_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                MutableHeaders(scope=message)['X-Request-ID'] = request_id
            await send(message)
        try:
            await self.app(scope, receive, measured_send)
        finally:
            elapsed = (time.monotonic()-started)*1000
            with self.metrics.lock:
                self.metrics.requests += 1
                self.metrics.errors += int(status >= 500)
                if stream:
                    self.metrics.active_streams -= 1
                else:
                    self.metrics.timings.append(elapsed)
            if status >= 500 or (not stream and elapsed > 2000):
                # Never log raw URLs, query strings, emails, bodies or tokens.
                route = getattr(scope.get('route'), 'path', 'unmatched')
                logging.getLogger('campuslink.requests').warning(
                    'request_id=%s method=%s route=%s status=%s duration_ms=%d',
                    request_id, scope.get('method'), route, status, elapsed)
