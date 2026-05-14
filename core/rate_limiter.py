import os
import time
import threading
import re
from functools import wraps
from flask import request, jsonify

from core.exceptions import RateLimitError

REDIS_URL = os.getenv("REDIS_URL", "")

_redis_client = None
if REDIS_URL:
    try:
        import redis as _redis

        _redis_client = _redis.from_url(
            REDIS_URL, socket_connect_timeout=2, socket_timeout=2, decode_responses=True
        )
        _redis_client.ping()
    except Exception:
        _redis_client = None


class MemoryRateStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._store: dict[str, list[float]] = {}

    def _clean(self, key: str, window: float):
        now = time.time()
        timestamps = self._store.get(key, [])
        valid = [ts for ts in timestamps if now - ts < window]
        if valid:
            self._store[key] = valid
        else:
            self._store.pop(key, None)
        return len(valid)

    def add_and_check(self, key: str, max_requests: int, window: float) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            count = self._clean(key, window)
            if count >= max_requests:
                return False, count
            self._store.setdefault(key, []).append(now)
            return True, count + 1

    def remaining(self, key: str, max_requests: int, window: float) -> int:
        with self._lock:
            count = self._clean(key, window)
            remaining = max(0, max_requests - count)
            return remaining

    def reset(self, key: str):
        with self._lock:
            self._store.pop(key, None)


_memory_store = MemoryRateStore()


def _redis_add_and_check(
    redis_client, key: str, max_requests: int, window: float
) -> tuple[bool, int]:
    try:
        now = time.time()
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, int(window) + 1)
        _, count, _, _ = pipe.execute()
        count = int(count)
        if count > max_requests:
            return False, count
        return True, count
    except Exception:
        return _memory_store.add_and_check(key, max_requests, window)


def _redis_remaining(redis_client, key: str, max_requests: int, window: float) -> int:
    try:
        now = time.time()
        redis_client.zremrangebyscore(key, 0, now - window)
        count = redis_client.zcard(key)
        return max(0, max_requests - int(count))
    except Exception:
        return _memory_store.remaining(key, max_requests, window)


def check_rate_limit(
    key: str,
    max_requests: int = 10,
    window_seconds: int = 3600,
) -> tuple[bool, int]:
    if _redis_client:
        return _redis_add_and_check(_redis_client, key, max_requests, window_seconds)
    return _memory_store.add_and_check(key, max_requests, window_seconds)


def get_remaining(key: str, max_requests: int, window_seconds: int) -> int:
    if _redis_client:
        return _redis_remaining(_redis_client, key, max_requests, window_seconds)
    return _memory_store.remaining(key, max_requests, window_seconds)


def reset_rate_limit(key: str):
    if _redis_client:
        try:
            _redis_client.delete(key)
        except Exception:
            pass
    _memory_store.reset(key)


def get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.remote_addr or "127.0.0.1"
    return ip


def rate_limit_key(prefix: str = "rl") -> str:
    ip = get_client_ip()
    session_id = request.headers.get("X-Session-Id", "") or request.args.get(
        "session_id", ""
    )
    if session_id:
        return f"{prefix}:session:{session_id}"
    return f"{prefix}:ip:{ip}"


def make_rate_limit(
    max_requests: int = 10,
    window_seconds: int = 3600,
    prefix: str = "rl",
    endpoint: str | None = None,
):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ep = endpoint or request.endpoint or "unknown"
            key = f"{rate_limit_key(prefix)}:{ep}"
            allowed, count = check_rate_limit(key, max_requests, window_seconds)
            if not allowed:
                remaining = 0
                resp = jsonify(
                    {
                        "error": "Rate limit exceeded. Please slow down.",
                        "retry_after_seconds": window_seconds,
                        "limit": max_requests,
                        "remaining": 0,
                    }
                )
                resp.status_code = 429
                resp.headers["X-RateLimit-Limit"] = str(max_requests)
                resp.headers["X-RateLimit-Remaining"] = "0"
                resp.headers["X-RateLimit-Reset"] = str(int(time.time() + window_seconds))
                resp.headers["Retry-After"] = str(window_seconds)
                return resp
            remaining = max_requests - count
            resp = f(*args, **kwargs)
            if hasattr(resp, "headers"):
                resp.headers["X-RateLimit-Limit"] = str(max_requests)
                resp.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
                resp.headers["X-RateLimit-Reset"] = str(int(time.time() + window_seconds))
            return resp

        return wrapper

    return decorator


ANON_GENERATION_LIMIT = int(os.getenv("ANON_GENERATION_LIMIT", "20"))
ANON_GENERATION_WINDOW = int(os.getenv("ANON_GENERATION_WINDOW", "3600"))
ANON_EXPORT_LIMIT = int(os.getenv("ANON_EXPORT_LIMIT", "10"))
ANON_EXPORT_WINDOW = int(os.getenv("ANON_EXPORT_WINDOW", "3600"))
AUTH_GENERATION_LIMIT = int(os.getenv("AUTH_GENERATION_LIMIT", "200"))
AUTH_GENERATION_WINDOW = int(os.getenv("AUTH_GENERATION_WINDOW", "86400"))
AUTH_EXPORT_LIMIT = int(os.getenv("AUTH_EXPORT_LIMIT", "100"))
AUTH_EXPORT_WINDOW = int(os.getenv("AUTH_EXPORT_WINDOW", "86400"))
UPLOAD_LIMIT = int(os.getenv("UPLOAD_LIMIT", "60"))
UPLOAD_WINDOW = int(os.getenv("UPLOAD_WINDOW", "3600"))


def is_authenticated() -> bool:
    api_key = request.headers.get("X-API-Key", "")
    if api_key and api_key == os.getenv("API_KEY", ""):
        return True
    return False


def generation_rate_limit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if is_authenticated():
            limit = AUTH_GENERATION_LIMIT
            window = AUTH_GENERATION_WINDOW
        else:
            limit = ANON_GENERATION_LIMIT
            window = ANON_GENERATION_WINDOW
        return make_rate_limit(
            max_requests=limit, window_seconds=window, prefix="gen"
        )(f)(*args, **kwargs)

    return wrapper


def export_rate_limit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if is_authenticated():
            limit = AUTH_EXPORT_LIMIT
            window = AUTH_EXPORT_WINDOW
        else:
            limit = ANON_EXPORT_LIMIT
            window = ANON_EXPORT_WINDOW
        return make_rate_limit(
            max_requests=limit, window_seconds=window, prefix="export"
        )(f)(*args, **kwargs)

    return wrapper


def upload_rate_limit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return make_rate_limit(
            max_requests=UPLOAD_LIMIT, window_seconds=UPLOAD_WINDOW, prefix="upload"
        )(f)(*args, **kwargs)

    return wrapper


class RateLimitState:
    def __init__(self):
        self._lock = threading.Lock()
        self._generation_in_flight: dict[str, int] = {}

    def try_acquire(self, key: str) -> bool:
        with self._lock:
            current = self._generation_in_flight.get(key, 0)
            if current >= 2:
                return False
            self._generation_in_flight[key] = current + 1
            return True

    def release(self, key: str):
        with self._lock:
            current = self._generation_in_flight.get(key, 0)
            if current > 1:
                self._generation_in_flight[key] = current - 1
            else:
                self._generation_in_flight.pop(key, None)


burst_limiter = RateLimitState()
