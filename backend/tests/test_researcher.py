import pytest

import config
from agents import researcher as researcher_mod
from agents.researcher import researcher_node
from tools.search import SearchError


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch):
    monkeypatch.setattr(config, "SEARCH_PACING_SECONDS", 0.0)


def _state(**over):
    base = {
        "query": "q",
        "sub_tasks": ["a", "b"],
        "search_results": {},
        "agent_logs": [],
        "unanswered_tasks": [],
        "retry_count": 0,
    }
    base.update(over)
    return base


def test_partial_failure_does_not_abort_the_run(monkeypatch):
    def fake_search(task, max_results=None):
        if task == "a":
            raise SearchError("down")
        return [{"title": "T", "url": "https://e.com", "content": "c"}]

    monkeypatch.setattr(researcher_mod, "search_web", fake_search)
    out = researcher_node(_state())

    assert out["error"] is None
    assert list(out["search_results"]) == ["b"]
    assert out["unanswered_tasks"] == ["a"]


def test_total_failure_sets_error(monkeypatch):
    """Every search failing must not proceed to the Analyst."""
    monkeypatch.setattr(
        researcher_mod,
        "search_web",
        lambda task, max_results=None: (_ for _ in ()).throw(SearchError("down")),
    )
    out = researcher_node(_state())

    assert out["error"] is not None
    assert "every search request failed" in out["error"]
    assert out["unanswered_tasks"] == ["a", "b"]


def test_empty_results_are_unanswered_but_not_an_error(monkeypatch):
    monkeypatch.setattr(researcher_mod, "search_web", lambda task, max_results=None: [])
    out = researcher_node(_state())

    assert out["error"] is None
    assert out["search_results"] == {}
    assert out["unanswered_tasks"] == ["a", "b"]


def test_retry_pass_searches_only_unanswered_and_keeps_prior_results(monkeypatch):
    searched = []

    def fake_search(task, max_results=None):
        searched.append(task)
        return [{"title": "T", "url": f"https://{task}.com", "content": "c"}]

    monkeypatch.setattr(researcher_mod, "search_web", fake_search)
    out = researcher_node(
        _state(
            sub_tasks=["a", "b", "b-refined"],
            search_results={"a": [{"title": "A", "url": "https://a.com", "content": ""}]},
            unanswered_tasks=["b-refined"],
        )
    )

    assert searched == ["b-refined"]
    assert set(out["search_results"]) == {"a", "b-refined"}
