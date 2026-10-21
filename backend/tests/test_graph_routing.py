import pytest

import config
from graph import coverage_ratio, route_after_node, route_after_research


def _state(**over):
    base = {
        "query": "q",
        "sub_tasks": ["a", "b", "c"],
        "search_results": {},
        "unanswered_tasks": [],
        "retry_count": 0,
        "error": None,
    }
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def _retry_budget(monkeypatch):
    monkeypatch.setattr(config, "MAX_RESEARCH_RETRIES", 1)
    monkeypatch.setattr(config, "MIN_COVERAGE_RATIO", 0.6)


def test_coverage_ratio():
    assert coverage_ratio(_state()) == 0.0
    assert coverage_ratio(_state(search_results={"a": [], "b": []})) == pytest.approx(2 / 3)
    assert coverage_ratio(_state(sub_tasks=[])) == 0.0


def test_error_always_routes_to_handler():
    assert route_after_node(_state(error="boom")) == "error_handler"
    assert route_after_research(_state(error="boom")) == "error_handler"


def test_thin_coverage_with_budget_left_refines():
    """A poor pass loops back for another try."""
    state = _state(search_results={"a": []}, unanswered_tasks=["b", "c"])
    assert route_after_research(state) == "refine"


def test_good_coverage_proceeds_even_with_a_gap():
    state = _state(search_results={"a": [], "b": []}, unanswered_tasks=["c"])
    assert route_after_research(state) == "continue"


def test_retry_budget_is_respected():
    """The refiner/researcher edge must not cycle forever."""
    state = _state(search_results={"a": []}, unanswered_tasks=["b", "c"], retry_count=1)
    assert route_after_research(state) == "continue"


def test_no_unanswered_tasks_proceeds():
    state = _state(search_results={"a": [], "b": [], "c": []})
    assert route_after_research(state) == "continue"
