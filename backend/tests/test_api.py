import time

import pytest
from fastapi.testclient import TestClient

import config
import main
import sessions as session_store
from main import app


@pytest.fixture(autouse=True)
def _fresh_store():
    session_store.reset_store()
    yield
    session_store.reset_store()


@pytest.fixture
def client(monkeypatch):
    # Routing and agents have their own suites.
    monkeypatch.setattr(main, "_run_graph_streaming", lambda *a, **k: None)
    with TestClient(app) as c:
        yield c


def test_health_reports_model_and_session_count(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["model"] == config.DEEPSEEK_MODEL
    assert body["active_sessions"] == 0


def test_health_reports_whether_multiple_workers_are_safe(client):
    # No REDIS_URL in tests, so state is process-local.
    assert client.get("/api/health").json()["multi_worker_safe"] is False


def test_empty_query_rejected(client):
    assert client.post("/api/research", json={"query": "   "}).status_code == 400


def test_research_returns_a_session_id(client):
    body = client.post("/api/research", json={"query": "why"}).json()
    assert session_store.get_store().exists(body["session_id"])


def test_unknown_session_stream_is_404(client):
    assert client.get("/api/research/nope/stream").status_code == 404


def test_backpressure_returns_429(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_ACTIVE_SESSIONS", 2)
    assert client.post("/api/research", json={"query": "a"}).status_code == 200
    assert client.post("/api/research", json={"query": "b"}).status_code == 200
    assert client.post("/api/research", json={"query": "c"}).status_code == 429


def test_abandoned_sessions_are_reaped(monkeypatch):
    """A POST whose client never opens the stream must not leak a queue."""
    monkeypatch.setattr(config, "SESSION_TTL_SECONDS", 60)
    store = session_store.InMemorySessionStore()
    now = time.monotonic()
    store.create("fresh")
    store.create("stale")
    store._created["stale"] = now - 3600

    assert store.reap(now=now) == 1
    assert store.exists("fresh")
    assert not store.exists("stale")
