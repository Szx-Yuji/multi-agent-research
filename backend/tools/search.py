import time

from tavily import TavilyClient

import cache
import config

_client: TavilyClient | None = None


class SearchError(RuntimeError):
    """A search could not be run. Not the same as a search that found nothing."""


def get_client() -> TavilyClient:
    global _client
    if _client is None:
        import os

        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise SearchError("TAVILY_API_KEY environment variable not set")
        _client = TavilyClient(api_key=api_key)
    return _client


def reset_client() -> None:
    global _client
    _client = None


def search_web(
    query: str, max_results: int | None = None, use_cache: bool = True
) -> list[dict]:
    """Top Tavily results. Empty list if nothing matched, SearchError if the
    request could not be made."""
    if max_results is None:
        max_results = config.SEARCH_MAX_RESULTS

    if use_cache:
        hit = cache.get(query, max_results)
        if hit is not None:
            return hit

    client = get_client()
    last_error: Exception | None = None

    for attempt in range(1, config.SEARCH_MAX_ATTEMPTS + 1):
        try:
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",
            )
        except Exception as exc:  # noqa: BLE001 - Tavily raises bare Exceptions
            last_error = exc
            if attempt < config.SEARCH_MAX_ATTEMPTS:
                time.sleep(config.SEARCH_BACKOFF_SECONDS * attempt)
            continue

        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": (r.get("content") or "")[:500],
            }
            for r in response.get("results", [])
        ]
        if use_cache and results:
            cache.set(query, max_results, results)
        return results

    raise SearchError(
        f"Search failed after {config.SEARCH_MAX_ATTEMPTS} attempts: {last_error}"
    )
