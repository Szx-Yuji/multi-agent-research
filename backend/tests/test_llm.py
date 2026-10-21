"""Exercise the real SDK against a local HTTP mock, without model API calls."""
import json

import httpx
from openai import OpenAI
import pytest

import config
import events
import llm
from agents.analyst import analyst_node
from agents.planner import planner_node
from agents.refiner import refiner_node
from agents.writer import writer_node


@pytest.fixture
def deepseek_api(monkeypatch):
    requests = []
    monkeypatch.setattr(llm, "_client", None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setattr(config, "DEEPSEEK_BASE_URL", "https://deepseek.test/v1")
    monkeypatch.setattr(config, "DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setattr(config, "DEEPSEEK_THINKING", "disabled")

    def respond(response):
        def handle(request):
            requests.append(request)
            return response

        def build_client(**kwargs):
            return OpenAI(
                **kwargs,
                max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(handle)),
            )

        monkeypatch.setattr(llm, "OpenAI", build_client)
        return requests

    yield respond
    llm.reset_client()


def assert_request(request, max_tokens, streaming):
    assert str(request.url) == "https://deepseek.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-deepseek-key"
    body = json.loads(request.content)
    assert body["model"] == "deepseek-flash"
    assert body["max_tokens"] == max_tokens
    assert body.get("stream", False) is streaming
    assert body["thinking"] == {"type": "disabled"}
    assert [message["role"] for message in body["messages"]] == ["system", "user"]


def research_state():
    return {
        "query": "What are the findings?",
        "sub_tasks": ["original"],
        "unanswered_tasks": ["missing"],
        "retry_count": 0,
        "agent_logs": [],
        "analysis": "An existing analysis",
        "search_results": {
            "original": [{"title": "Source", "url": "https://example.com", "content": "Evidence"}]
        },
    }


@pytest.mark.parametrize(
    "node, result_key",
    [(planner_node, "sub_tasks"), (refiner_node, "unanswered_tasks")],
)
def test_planning_uses_deepseek_chat_completions(deepseek_api, node, result_key):
    requests = deepseek_api(httpx.Response(200, json={
        "id": "completion-test",
        "object": "chat.completion",
        "created": 0,
        "model": "deepseek-flash",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": '["a", "b"]'},
            "finish_reason": "stop",
        }],
    }))

    result = node(research_state())

    assert result["error"] is None
    assert result[result_key] == ["a", "b"]
    assert len(requests) == 1
    assert_request(requests[0], max_tokens=1024, streaming=False)
    assert llm.get_client() is llm.get_client()
    assert llm.get_client().timeout == config.DEEPSEEK_TIMEOUT_SECONDS


def stream_response(deltas):
    frames = []
    for choices in deltas:
        frames.append("data: " + json.dumps({
            "id": "stream-test",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "deepseek-flash",
            "choices": choices,
        }) + "\n\n")
    frames.append("data: [DONE]\n\n")
    return httpx.Response(
        200,
        headers={"Content-Type": "text/event-stream"},
        text="".join(frames),
    )


def choice(delta, finish_reason=None):
    return [{"index": 0, "delta": delta, "finish_reason": finish_reason}]


@pytest.mark.parametrize(
    "node, result_key, event_type, max_tokens",
    [
        (analyst_node, "analysis", "analysis_token", 2048),
        (writer_node, "final_report", "report_token", 4096),
    ],
)
def test_real_sdk_streams_only_answer_text(
    deepseek_api, node, result_key, event_type, max_tokens
):
    requests = deepseek_api(stream_response([
        choice({"role": "assistant", "content": ""}),
        choice({"reasoning_content": "internal reasoning"}),
        [],
        choice({"content": "## Findings"}),
        choice({"content": "\n\nEvidence."}),
        choice({}, "stop"),
    ]))
    seen = []
    events.set_emitter(lambda name, data: seen.append((name, data)))
    try:
        result = node(research_state())
    finally:
        events.set_emitter(None)

    assert result["error"] is None
    assert result[result_key] == "## Findings\n\nEvidence."
    assert [data["text"] for name, data in seen if name == event_type] == [
        "## Findings", "\n\nEvidence."
    ]
    assert len(requests) == 1
    assert_request(requests[0], max_tokens, streaming=True)


@pytest.mark.parametrize("node", [analyst_node, writer_node])
def test_reasoning_only_response_is_not_a_completed_report(deepseek_api, node):
    deepseek_api(stream_response([
        choice({"reasoning_content": "internal reasoning"}),
        choice({}, "stop"),
    ]))

    result = node(research_state())

    assert "DeepSeek returned no" in result["error"]
    assert not any(log["action"] in ("Report complete", "Synthesized findings")
                   for log in result.get("agent_logs", []))


def test_missing_deepseek_key_reaches_the_node_error_path(monkeypatch):
    monkeypatch.setattr(llm, "_client", None)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    result = planner_node(research_state())

    assert "DEEPSEEK_API_KEY environment variable not set" in result["error"]


def test_deepseek_auth_failure_reaches_the_node_error_path(deepseek_api):
    deepseek_api(httpx.Response(401, json={
        "error": {"message": "Invalid API key", "type": "authentication_error"}
    }))

    result = planner_node(research_state())

    assert "Planner failed" in result["error"]
    assert "Invalid API key" in result["error"]
