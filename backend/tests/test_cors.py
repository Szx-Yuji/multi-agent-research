import importlib

import pytest


@pytest.fixture
def reloaded_config(monkeypatch):
    def _load(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        import config

        return importlib.reload(config)

    yield _load
    import config

    importlib.reload(config)


def test_defaults_to_local_dev_origins(reloaded_config, monkeypatch):
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ALLOW_ORIGIN_REGEX", raising=False)
    cfg = reloaded_config()
    assert cfg.CORS_ALLOW_ORIGINS == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    assert cfg.CORS_ALLOW_ORIGIN_REGEX is None


def test_deployed_origins_are_configurable(reloaded_config):
    cfg = reloaded_config(
        CORS_ALLOW_ORIGINS="https://app.vercel.app, https://www.example.com",
        CORS_ALLOW_ORIGIN_REGEX=r"https://mar-.*\.vercel\.app",
    )
    assert cfg.CORS_ALLOW_ORIGINS == [
        "https://app.vercel.app",
        "https://www.example.com",
    ]
    assert cfg.CORS_ALLOW_ORIGIN_REGEX == r"https://mar-.*\.vercel\.app"


def test_model_id_is_configurable(reloaded_config):
    assert reloaded_config(DEEPSEEK_MODEL="deepseek-pro").DEEPSEEK_MODEL == "deepseek-pro"


def test_deepseek_defaults(reloaded_config, monkeypatch):
    for name in ("DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL", "DEEPSEEK_TIMEOUT_SECONDS", "DEEPSEEK_THINKING"):
        monkeypatch.delenv(name, raising=False)

    cfg = reloaded_config()
    assert cfg.DEEPSEEK_MODEL == "deepseek-flash"
    assert cfg.DEEPSEEK_BASE_URL == "https://api.deepseek.com"
    assert cfg.DEEPSEEK_TIMEOUT_SECONDS == 60
    assert cfg.DEEPSEEK_THINKING == "disabled"


def test_deepseek_connection_and_thinking_are_configurable(reloaded_config):
    cfg = reloaded_config(
        DEEPSEEK_BASE_URL="https://deepseek.example.com/v1",
        DEEPSEEK_TIMEOUT_SECONDS="90",
        DEEPSEEK_THINKING="enabled",
    )
    assert cfg.DEEPSEEK_BASE_URL == "https://deepseek.example.com/v1"
    assert cfg.DEEPSEEK_TIMEOUT_SECONDS == 90
    assert cfg.DEEPSEEK_THINKING == "enabled"
