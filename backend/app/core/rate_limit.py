"""Redis-backed login limiter with a bounded local fallback."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Lock
from time import monotonic

from app.core.config import get_settings


class LoginRateLimiter:
    def __init__(self, attempts: int = 8, window_seconds: int = 300, max_local_keys: int = 10_000) -> None:
        self.attempts = attempts
        self.window = timedelta(seconds=window_seconds)
        self.window_seconds = window_seconds
        self.max_local_keys = max_local_keys
        self._records: dict[str, deque[datetime]] = {}
        self._lock = Lock()
        self._redis = None
        self._redis_url: str | None = None
        self._redis_failure_until = 0.0

    def _redis_client(self):
        settings = get_settings()
        if settings.redis_url.startswith("memory://"):
            return None
        if monotonic() < self._redis_failure_until:
            return None
        if self._redis_url == settings.redis_url and self._redis is not None:
            return self._redis
        try:
            import redis

            self._redis = redis.Redis.from_url(
                settings.redis_url,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
                decode_responses=True,
            )
            self._redis_url = settings.redis_url
            return self._redis
        except Exception:
            self._redis = None
            self._redis_url = settings.redis_url
            self._redis_failure_until = monotonic() + 5.0
            return None

    def _redis_allowed(self, key: str) -> bool | None:
        client = self._redis_client()
        if client is None:
            return None
        redis_key = "trip-helper:login:" + sha256(key.encode("utf-8")).hexdigest()
        try:
            with client.pipeline(transaction=True) as pipe:
                pipe.incr(redis_key)
                pipe.expire(redis_key, self.window_seconds)
                count, _ = pipe.execute()
            return int(count) <= self.attempts
        except Exception:
            self._redis = None
            self._redis_failure_until = monotonic() + 5.0
            return None

    def allowed(self, key: str) -> bool:
        redis_result = self._redis_allowed(key)
        if redis_result is not None:
            return redis_result
        now = datetime.now(UTC)
        with self._lock:
            values = self._records.setdefault(key, deque())
            while values and now - values[0] > self.window:
                values.popleft()
            if len(values) >= self.attempts:
                return False
            values.append(now)
            if len(self._records) > self.max_local_keys:
                stale_key = min(
                    self._records,
                    key=lambda item: self._records[item][-1] if self._records[item] else now,
                )
                self._records.pop(stale_key, None)
            return True

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


login_rate_limiter = LoginRateLimiter()
