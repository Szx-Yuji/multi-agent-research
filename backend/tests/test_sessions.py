"""Session store behaviour, and the fallback that decides worker safety."""
import time

import pytest

import config
import sessions as session_store
from sessions import InMemorySessionStore, RedisSessionStore


@pytest.fixture
def store():
    return InMemorySessionStore()


def test_events_come_back_in_order(store):
    store.create("s")
    store.push("s", "agent_update", {"n": 1})
    store.push("s", "report_token", {"text": "x"})

    assert store.pop("s", 0.1) == ("agent_update", {"n": 1})
    assert store.pop("s", 0.1) == ("report_token", {"text": "x"})


def test_pop_times_out_rather_than_blocking_forever(store):
    store.create("s")
    started = time.monotonic()
    assert store.pop("s", 0.2) is None
    assert time.monotonic() - started < 2


def test_pop_on_unknown_session_is_none(store):
    assert store.pop("missing", 0.05) is None


def test_push_to_unknown_session_is_dropped_not_raised(store):
    store.push("missing", "x", {})  # must not raise


def test_delete_removes_the_session(store):
    store.create("s")
    store.delete("s")
    assert not store.exists("s")
    assert store.count() == 0


def test_reap_only_removes_expired(store, monkeypatch):
    monkeypatch.setattr(config, "SESSION_TTL_SECONDS", 60)
    now = time.monotonic()
    store.create("fresh")
    store.create("stale")
    store._created["stale"] = now - 3600

    assert store.reap(now=now) == 1
    assert store.exists("fresh") and not store.exists("stale")


def test_without_redis_the_store_is_process_local(monkeypatch):
    monkeypatch.setattr(config, "REDIS_URL", None)
    session_store.reset_store()
    assert isinstance(session_store.get_store(), InMemorySessionStore)
    assert session_store.is_shared() is False


def test_with_redis_the_store_is_shared(monkeypatch):
    """A reachable Redis is what makes more than one worker safe."""
    import shared

    class FakeRedis:
        def ping(self):
            return True

    monkeypatch.setattr(shared, "_redis", FakeRedis())
    monkeypatch.setattr(shared, "_checked", True)
    session_store.reset_store()

    assert isinstance(session_store.get_store(), RedisSessionStore)
    assert session_store.is_shared() is True


def test_redis_store_round_trips_through_the_client(monkeypatch):
    """The Redis path encodes events as JSON and reads them back unchanged."""
    import json

    class FakeRedis:
        def __init__(self):
            self.lists = {}
            self.zset = {}

        def zadd(self, key, mapping):
            self.zset.update(mapping)

        def zrem(self, key, member):
            self.zset.pop(member, None)

        def zscore(self, key, member):
            return self.zset.get(member)

        def zcard(self, key):
            return len(self.zset)

        def zrangebyscore(self, key, lo, hi):
            return [m for m, s in self.zset.items() if s <= hi]

        def rpush(self, key, value):
            self.lists.setdefault(key, []).append(value)

        def blpop(self, key, timeout):
            items = self.lists.get(key) or []
            return (key, items.pop(0)) if items else None

        def expire(self, key, ttl):
            pass

        def delete(self, key):
            self.lists.pop(key, None)

    fake = FakeRedis()
    store = RedisSessionStore(fake)

    store.create("s")
    assert store.exists("s")
    store.push("s", "report_token", {"text": "hello"})
    assert store.pop("s", 1) == ("report_token", {"text": "hello"})
    assert store.pop("s", 1) is None

    store.delete("s")
    assert not store.exists("s")


def test_redis_reap_drops_sessions_past_the_ttl(monkeypatch):
    monkeypatch.setattr(config, "SESSION_TTL_SECONDS", 60)

    class FakeRedis:
        def __init__(self):
            self.zset = {"old": time.time() - 3600, "new": time.time()}
            self.deleted = []

        def zrangebyscore(self, key, lo, hi):
            return [m for m, s in self.zset.items() if s <= hi]

        def zrem(self, key, member):
            self.zset.pop(member, None)

        def delete(self, key):
            self.deleted.append(key)

    fake = FakeRedis()
    assert RedisSessionStore(fake).reap() == 1
    assert "old" not in fake.zset and "new" in fake.zset
