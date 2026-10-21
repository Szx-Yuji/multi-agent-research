import pytest

from agents.planner import parse_task_list


def test_plain_json_array():
    assert parse_task_list('["a", "b"]') == ["a", "b"]


def test_markdown_fenced_json():
    assert parse_task_list('```json\n["a", "b"]\n```') == ["a", "b"]


def test_bare_fence():
    assert parse_task_list('```\n["a"]\n```') == ["a"]


def test_rejects_non_array():
    with pytest.raises(ValueError):
        parse_task_list('{"a": 1}')


def test_rejects_non_string_items():
    with pytest.raises(ValueError):
        parse_task_list("[1, 2]")
