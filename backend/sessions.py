"""Per-run event queues.

Two implementations behind one interface. Without Redis the queues live in
process memory, which is fine for one worker. With Redis they are shared, so
the POST that starts a run and the GET that streams it can be served by
different workers or different instances.
"""
import json
import queue
import threading
import time
from typing import Optional

import config
from shared import get_redis

_ACTIVE = "sessions:active"


class SessionStore:
    def create(self, session_id: str) -> None:
        raise NotImplementedError

    def exists(self, session_id: str) -> bool:
        raise NotImplementedError

    def push(self, session_id: str, event_type: str, data: dict) -> None:
        raise NotImplementedError

    def pop(self, session_id: str, timeout: float) -> Optional[tuple[str, dict]]:
        """Next event, or None if nothing arrived within `timeout` seconds."""
        raise NotImplementedError

    def delete(self, session_id: str) -> None:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def reap(self, now: float | None = None) -> int:
        """Drop sessions whose client never connected. Returns how many."""
        raise NotImplementedError


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._queues: dict[str, queue.Queue] = {}
        self._created: dict[str, float] = {}
        self._lock = threading.Lock()

    def create(self, session_id: str) -> None:
        with self._lock:
            self._queues[session_id] = queue.Queue()
            self._created[session_id] = time.monotonic()

    def exists(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._queues

    def push(self, session_id: str, event_type: str, data: dict) -> None:
        with self._lock:
            q = self._queues.get(session_id)
        if q is not None:
            q.put((event_type, data))

    def pop(self, session_id: str, timeout: float) -> Optional[tuple[str, dict]]:
        with self._lock:
            q = self._queues.get(session_id)
        if q is None:
            return None
        try:
            return q.get(True, timeout)
        except queue.Empty:
            return None

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._queues.pop(session_id, None)
            self._created.pop(session_id, None)

    def count(self) -> int:
        with self._lock:
            return len(self._queues)

    def reap(self, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        with self._lock:
            stale = [
                sid
                for sid, created in self._created.items()
                if now - created > config.SESSION_TTL_SECONDS
            ]
            for sid in stale:
                self._queues.pop(sid, None)
                self._created.pop(sid, None)
        return len(stale)

    def clear(self) -> None:
        with self._lock:
            self._queues.clear()
            self._created.clear()


class RedisSessionStore(SessionStore):
    """Queues as Redis lists, plus a sorted set of live sessions keyed by
    creation time so they can be counted and reaped."""

    def __init__(self, client) -> None:
        self._r = client

    @staticmethod
    def _q(session_id: str) -> str:
        return f"session:{session_id}:events"

    def create(self, session_id: str) -> None:
        self._r.zadd(_ACTIVE, {session_id: time.time()})
        # Guards against a worker dying mid-run and leaving the list forever.
        self._r.expire(self._q(session_id), config.SESSION_TTL_SECONDS * 2)

    def exists(self, session_id: str) -> bool:
        return self._r.zscore(_ACTIVE, session_id) is not None

    def push(self, session_id: str, event_type: str, data: dict) -> None:
        self._r.rpush(self._q(session_id), json.dumps([event_type, data]))
        self._r.expire(self._q(session_id), config.SESSION_TTL_SECONDS * 2)

    def pop(self, session_id: str, timeout: float) -> Optional[tuple[str, dict]]:
        # BLPOP takes whole seconds and treats 0 as "block forever".
        item = self._r.blpop(self._q(session_id), timeout=max(1, int(timeout)))
        if item is None:
            return None
        event_type, data = json.loads(item[1])
        return event_type, data

    def delete(self, session_id: str) -> None:
        self._r.zrem(_ACTIVE, session_id)
        self._r.delete(self._q(session_id))

    def count(self) -> int:
        return int(self._r.zcard(_ACTIVE))

    def reap(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        cutoff = now - config.SESSION_TTL_SECONDS
        stale = self._r.zrangebyscore(_ACTIVE, "-inf", cutoff)
        for sid in stale:
            self.delete(sid)
        return len(stale)


_store: SessionStore | None = None
_store_lock = threading.Lock()


def get_store() -> SessionStore:
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            client = get_redis()
            _store = RedisSessionStore(client) if client else InMemorySessionStore()
    return _store


def reset_store() -> None:
    """Forget the store so the next call rebuilds it. Used by tests."""
    global _store
    with _store_lock:
        _store = None


def is_shared() -> bool:
    """True when session state is shared, i.e. more than one worker is safe."""
    return isinstance(get_store(), RedisSessionStore)
