"""Registration, login, and per-user history isolation."""
import pytest
from fastapi.testclient import TestClient

import config
import db
import main
import sessions as session_store
from main import app

CREDS = {"email": "Ada@Example.com", "password": "correct-horse-battery"}
OTHER = {"email": "grace@example.com", "password": "another-good-passphrase"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(config, "AUTH_SECRET", "t" * 48)
    monkeypatch.setattr(main, "_run_graph_streaming", lambda *a, **k: None)
    db.reset()
    session_store.reset_store()
    with TestClient(app) as c:
        yield c
    db.reset()
    session_store.reset_store()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def register(client, creds=CREDS):
    r = client.post("/api/auth/register", json=creds)
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def test_register_then_me(client):
    token = register(client)
    body = client.get("/api/auth/me", headers=auth(token)).json()
    assert body["email"] == "ada@example.com"  # normalized to lowercase


def test_duplicate_email_is_rejected(client):
    register(client)
    assert client.post("/api/auth/register", json=CREDS).status_code == 409


def test_short_password_is_rejected(client):
    r = client.post("/api/auth/register", json={"email": "a@b.com", "password": "short"})
    assert r.status_code == 422


def test_login_is_case_insensitive_on_email(client):
    register(client)
    r = client.post(
        "/api/auth/login", json={"email": "ADA@example.com", "password": CREDS["password"]}
    )
    assert r.status_code == 200


def test_wrong_password_rejected_without_revealing_the_account(client):
    register(client)
    wrong = client.post(
        "/api/auth/login", json={"email": CREDS["email"], "password": "not-the-password"}
    )
    missing = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever12"}
    )
    assert wrong.status_code == missing.status_code == 401
    # Identical wording, so the response cannot be used to enumerate accounts.
    assert wrong.json()["detail"] == missing.json()["detail"]


def test_password_is_not_stored_in_plaintext(client):
    register(client)
    with db.get_session() as s:
        user = s.query(db.User).first()
    assert CREDS["password"] not in user.password_hash
    assert user.password_hash.startswith("$argon2")


def test_history_requires_authentication(client):
    assert client.get("/api/history").status_code == 401


def test_garbage_token_is_rejected(client):
    assert client.get("/api/history", headers=auth("not.a.token")).status_code == 401


def test_research_still_works_anonymously(client):
    assert client.post("/api/research", json={"query": "why"}).status_code == 200


def _seed_run(user_email, query="q"):
    with db.get_session() as s:
        user = s.query(db.User).filter(db.User.email == user_email).first()
        run = db.ResearchRun(
            user_id=user.id,
            query=query,
            final_report="# Report",
            sub_tasks_json='["a"]',
            sources_json='[{"title":"T","url":"https://e.com"}]',
            duration_seconds=12.5,
        )
        s.add(run)
        s.commit()
        return run.id


def test_history_lists_only_your_own_runs(client):
    token_a = register(client)
    token_b = register(client, OTHER)
    _seed_run("ada@example.com", "ada's question")
    _seed_run("grace@example.com", "grace's question")

    a = client.get("/api/history", headers=auth(token_a)).json()["runs"]
    b = client.get("/api/history", headers=auth(token_b)).json()["runs"]

    assert [r["query"] for r in a] == ["ada's question"]
    assert [r["query"] for r in b] == ["grace's question"]
    assert a[0]["source_count"] == 1


def test_cannot_read_another_users_run(client):
    token_a = register(client)
    register(client, OTHER)
    grace_run = _seed_run("grace@example.com")

    r = client.get(f"/api/history/{grace_run}", headers=auth(token_a))
    # 404 not 403, so ids cannot be probed for existence.
    assert r.status_code == 404


def test_run_detail_returns_report_and_sources(client):
    token = register(client)
    run_id = _seed_run("ada@example.com")
    body = client.get(f"/api/history/{run_id}", headers=auth(token)).json()
    assert body["final_report"] == "# Report"
    assert body["sources"][0]["url"] == "https://e.com"


def test_cannot_delete_another_users_run(client):
    token_a = register(client)
    register(client, OTHER)
    grace_run = _seed_run("grace@example.com")

    assert client.delete(f"/api/history/{grace_run}", headers=auth(token_a)).status_code == 404
    with db.get_session() as s:
        assert s.get(db.ResearchRun, grace_run) is not None


def test_delete_your_own_run(client):
    token = register(client)
    run_id = _seed_run("ada@example.com")
    assert client.delete(f"/api/history/{run_id}", headers=auth(token)).status_code == 204
    assert client.get("/api/history", headers=auth(token)).json()["runs"] == []


def test_default_auth_secret_is_reported_as_insecure(monkeypatch):
    monkeypatch.setattr(config, "AUTH_SECRET", config.DEFAULT_AUTH_SECRET)
    problems = config.check_auth_secret()
    assert problems and "development default" in problems[0]


def test_short_auth_secret_is_reported(monkeypatch):
    monkeypatch.setattr(config, "AUTH_SECRET", "abc123")
    assert "at least 32" in config.check_auth_secret()[0]


def test_strong_auth_secret_passes(monkeypatch):
    monkeypatch.setattr(config, "AUTH_SECRET", "x" * 48)
    assert config.check_auth_secret() == []
