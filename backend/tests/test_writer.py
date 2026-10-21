from contextlib import contextmanager
from types import SimpleNamespace

import events
from agents import writer as writer_mod
from agents.writer import collect_sources, writer_node


class FakeStreamClient:
    def __init__(self, chunks):
        self.chunks = chunks
        self.chat = self
        self.completions = self
        self.closed = False

    @contextmanager
    def create(self, **kwargs):
        assert kwargs["stream"] is True
        try:
            yield iter(self.chunks)
        finally:
            self.closed = True


def _chunk(content=None, **delta):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content, **delta))]
    )


def test_collect_sources_dedupes_preserving_order():
    results = {
        "a": [
            {"title": "A", "url": "https://x.com", "content": ""},
            {"title": "B", "url": "https://y.com", "content": ""},
        ],
        "b": [{"title": "A again", "url": "https://x.com", "content": ""}],
    }
    assert [s["url"] for s in collect_sources(results)] == [
        "https://x.com",
        "https://y.com",
    ]


def test_writer_streams_tokens_and_returns_assembled_report(monkeypatch):
    client = FakeStreamClient([_chunk("# Title"), _chunk("\n\nBody.")])
    monkeypatch.setattr(writer_mod, "get_client", lambda: client)

    seen = []
    events.set_emitter(lambda t, d: seen.append((t, d)))
    try:
        out = writer_node({
            "query": "q",
            "analysis": "a",
            "search_results": {"a": [{"title": "T", "url": "https://x.com", "content": ""}]},
            "agent_logs": [],
        })
    finally:
        events.set_emitter(None)

    tokens = [d for t, d in seen if t == "report_token"]
    assert len(tokens) == 2
    assert "".join(d["text"] for d in tokens) == "# Title\n\nBody."
    # The completion log streams too, rather than waiting for the node to return.
    assert any(t == "agent_update" for t, _ in seen)
    assert out["final_report"] == "# Title\n\nBody."
    assert out["error"] is None
    assert client.closed


def test_writer_keeps_reasoning_and_stream_metadata_out_of_the_report(monkeypatch):
    client = FakeStreamClient([
        _chunk(role="assistant"),
        SimpleNamespace(choices=[]),
        _chunk(reasoning_content="Private chain of thought"),
        _chunk(""),
        _chunk("# Report"),
        _chunk(),  # An empty SDK delta has content=None.
        _chunk("\nVisible answer.", reasoning_content="More private reasoning"),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason="stop")]
        ),
    ])
    monkeypatch.setattr(writer_mod, "get_client", lambda: client)

    seen = []
    events.set_emitter(lambda t, d: seen.append((t, d)))
    try:
        out = writer_node({"query": "q", "analysis": "a", "search_results": {}, "agent_logs": []})
    finally:
        events.set_emitter(None)

    tokens = [d["text"] for t, d in seen if t == "report_token"]
    assert tokens == ["# Report", "\nVisible answer."]
    assert out["final_report"] == "# Report\nVisible answer."
    assert out["error"] is None
    assert client.closed


def test_writer_reports_failure_instead_of_raising(monkeypatch):
    class Boom:
        def __getattr__(self, name):
            raise RuntimeError("api down")

    monkeypatch.setattr(writer_mod, "get_client", lambda: Boom())
    out = writer_node({"query": "q", "analysis": "a", "search_results": {}, "agent_logs": []})
    assert out["error"] and "Writer failed" in out["error"]


def test_emit_without_an_emitter_is_a_noop():
    events.set_emitter(None)
    events.emit("report_token", {"text": "x"})  # must not raise
