"""Settings, read from the environment."""
import os


def _split_env(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "60"))
# Keep the current output budgets focused on the answer, not hidden reasoning.
DEEPSEEK_THINKING = os.getenv("DEEPSEEK_THINKING", "disabled")

SEARCH_MAX_RESULTS = int(os.getenv("SEARCH_MAX_RESULTS", "3"))
SEARCH_MAX_ATTEMPTS = int(os.getenv("SEARCH_MAX_ATTEMPTS", "3"))
SEARCH_BACKOFF_SECONDS = float(os.getenv("SEARCH_BACKOFF_SECONDS", "1.0"))
SEARCH_PACING_SECONDS = float(os.getenv("SEARCH_PACING_SECONDS", "0.5"))

# Refine-and-search-again rounds allowed before giving up. 0 disables retries.
MAX_RESEARCH_RETRIES = int(os.getenv("MAX_RESEARCH_RETRIES", "1"))
# A pass is thin if fewer than this fraction of sub-tasks found anything.
MIN_COVERAGE_RATIO = float(os.getenv("MIN_COVERAGE_RATIO", "0.6"))

RESEARCH_TIMEOUT_SECONDS = int(os.getenv("RESEARCH_TIMEOUT_SECONDS", "180"))
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "600"))
SESSION_SWEEP_INTERVAL_SECONDS = int(os.getenv("SESSION_SWEEP_INTERVAL_SECONDS", "30"))
MAX_ACTIVE_SESSIONS = int(os.getenv("MAX_ACTIVE_SESSIONS", "50"))

CORS_ALLOW_ORIGINS = _split_env(
    "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
# For origins whose hostname varies per build, e.g. Vercel previews.
CORS_ALLOW_ORIGIN_REGEX = os.getenv("CORS_ALLOW_ORIGIN_REGEX") or None

# Searches run concurrently; this bounds how many hit Tavily at once.
SEARCH_CONCURRENCY = int(os.getenv("SEARCH_CONCURRENCY", "5"))

# Search result cache. 0 disables it.
SEARCH_CACHE_TTL_SECONDS = int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "21600"))
SEARCH_CACHE_MAX_ENTRIES = int(os.getenv("SEARCH_CACHE_MAX_ENTRIES", "512"))

# Shared state for sessions and cache. Unset means in-process only, which
# limits the app to one worker.
REDIS_URL = os.getenv("REDIS_URL") or None

# Users and saved history. SQLite needs no setup; point at Postgres to run
# more than one instance.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
# Signs session tokens. The default is for local development only; anything
# reachable from outside must set its own. check_auth_secret() enforces it.
DEFAULT_AUTH_SECRET = "insecure-development-secret-do-not-use-in-production"
AUTH_SECRET = os.getenv("AUTH_SECRET", DEFAULT_AUTH_SECRET)
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", str(14 * 24 * 3600)))


def check_auth_secret() -> list[str]:
    """Problems with the signing secret, worst first. Empty when it is sound.

    Anyone who knows the secret can mint a token for any account, so a shipped
    default is the same as no authentication at all.
    """
    problems = []
    if AUTH_SECRET == DEFAULT_AUTH_SECRET:
        problems.append(
            "AUTH_SECRET is still the built-in development default. Anyone who "
            "has read this repository can forge a login token. Set AUTH_SECRET "
            "to a random value before exposing this to a network."
        )
    elif len(AUTH_SECRET) < 32:
        problems.append(
            f"AUTH_SECRET is {len(AUTH_SECRET)} characters. HS256 wants at "
            "least 32. Generate one with: python -c "
            "\"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return problems
