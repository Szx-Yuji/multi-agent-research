from datetime import datetime, timezone

import config
from events import emit, emit_log
from llm import get_client
from models import ResearchState

SYSTEM_PROMPT = (
    "You are a research writer. Given an analysis and the original sources, "
    "write a comprehensive research report in Markdown format. Include: an "
    "Executive Summary, 3-5 sections covering the main findings, a Limitations "
    "section, and a numbered References list with URLs. Use clear headers (##). "
    "Be thorough but concise."
)


def collect_sources(search_results: dict[str, list]) -> list[dict]:
    """Flatten results into a de-duplicated source list, order preserved."""
    seen_urls: set[str] = set()
    sources = []
    for results in search_results.values():
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                sources.append(r)
    return sources


def writer_node(state: ResearchState) -> dict:
    """Write the final report, emitting each chunk as a report_token event."""
    logs = list(state.get("agent_logs", []))
    sources = collect_sources(state.get("search_results", {}))

    try:
        sources_text = "\n".join(
            f"[{i + 1}] {s['title']} - {s['url']}" for i, s in enumerate(sources)
        )
        user_message = (
            f"Original question: {state['query']}\n\n"
            f"Analysis:\n{state.get('analysis', '')}\n\n"
            f"Available sources:\n{sources_text}"
        )

        chunks: list[str] = []
        client = get_client()
        with client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            stream=True,
            extra_body={"thinking": {"type": config.DEEPSEEK_THINKING}},
        ) as stream:
            for chunk in stream:
                if not chunk.choices:
                    continue
                text = chunk.choices[0].delta.content
                if text:
                    chunks.append(text)
                    emit("report_token", {"text": text})

        final_report = "".join(chunks).strip()
        if not final_report:
            raise ValueError("DeepSeek returned no report text")

        emit_log(logs, {
            "agent": "Writer",
            "action": "Report complete",
            "detail": f"Generated report with {len(sources)} sources",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "final_report": final_report,
            "agent_logs": logs,
            "current_agent": "Writer",
            "error": None,
        }
    except Exception as e:
        return {
            "agent_logs": logs,
            "current_agent": "Writer",
            "error": f"Writer failed: {e}",
        }
