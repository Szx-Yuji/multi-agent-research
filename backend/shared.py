"""Optional Redis connection.

Returns None when REDIS_URL is unset or unreachable, which is the signal to
every caller to fall back to in-process behaviour.
"""
import threading

import config

_redis = None
_checked = False
_lock = threading.Lock()


def get_redis():
    global _redis, _checked
    if _checked:
        return _redis

    with _lock:
        if _checked:
            return _redis
        _checked = True
        if not config.REDIS_URL:
            _redis = None
            return None
        try:
            import redis as redis_lib

            client = redis_lib.Redis.from_url(
                config.REDIS_URL, decode_responses=True, socket_timeout=5
            )
            client.ping()
            _redis = client
        except Exception:
            _redis = None
    return _redis


def reset() -> None:
    """Forget the cached connection. Used by tests."""
    global _redis, _checked
    with _lock:
        _redis = None
        _checked = False
