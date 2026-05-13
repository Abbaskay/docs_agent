import os
import time
import threading
import json

REDIS_URL = os.getenv("REDIS_URL", "")
CACHE_DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "300"))

_redis_client = None
if REDIS_URL:
    try:
        import redis as _redis

        _redis_client = _redis.from_url(
            REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
        _redis_client.ping()
    except Exception:
        _redis_client = None


class MemoryCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: str, ttl: int = CACHE_DEFAULT_TTL):
        with self._lock:
            self._store[key] = (time.time() + ttl, value)

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()


_memory_cache = MemoryCache()


def cache_get(key: str) -> str | None:
    if _redis_client:
        try:
            return _redis_client.get(key)
        except Exception:
            return _memory_cache.get(key)
    return _memory_cache.get(key)


def cache_set(key: str, value: str, ttl: int = CACHE_DEFAULT_TTL):
    if _redis_client:
        try:
            _redis_client.setex(key, ttl, value)
            return
        except Exception:
            pass
    _memory_cache.set(key, value, ttl)


def cache_delete(key: str):
    if _redis_client:
        try:
            _redis_client.delete(key)
            return
        except Exception:
            pass
    _memory_cache.delete(key)


def cache_get_json(key: str):
    raw = cache_get(key)
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def cache_set_json(key: str, value, ttl: int = CACHE_DEFAULT_TTL):
    try:
        raw = json.dumps(value)
        cache_set(key, raw, ttl)
    except (TypeError, ValueError):
        pass


def cache_key(*parts) -> str:
    return ":".join(str(p) for p in parts)


def make_cache_key(prefix: str, *args) -> str:
    safe_parts = [str(a).replace(":", "_") for a in args]
    return f"cache:{prefix}:{':'.join(safe_parts)}"
