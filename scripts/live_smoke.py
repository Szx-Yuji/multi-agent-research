#!/usr/bin/env python
"""Smoke test against the real DeepSeek and Tavily APIs.

Starts a uvicorn server, submits a query over HTTP, consumes the SSE stream and
checks a sourced report streamed in. Costs real credits: DeepSeek model calls
and Tavily searches, including additional calls when refinement is needed.

    python scripts/live_smoke.py
    python scripts/live_smoke.py --query "what is the state of fusion energy"

Needs DEEPSEEK_API_KEY and TAVILY_API_KEY in .env or the environment.
Optional DEEPSEEK_MODEL, DEEPSEEK_BASE_URL, DEEPSEEK_TIMEOUT_SECONDS and
DEEPSEEK_THINKING overrides are passed through to the backend.
Exit 0 success, 1 a check failed, 2 not configured.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    import httpx
    from dotenv import load_dotenv
except ImportError:
    sys.exit(
        "Missing dependencies. Install them with:\n"
        "    pip install -r backend/requirements-dev.txt"
    )

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

DEFAULT_QUERY = "What are the main health effects of long-term sleep deprivation?"


def log(msg: str) -> None:
    print(msg, flush=True)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_keys() -> None:
    load_dotenv(ROOT / ".env")
    missing = [
        k for k in ("DEEPSEEK_API_KEY", "TAVILY_API_KEY")
        if not os.getenv(k, "").strip()
    ]
    if missing:
        print(
            f"Missing {' and '.join(missing)}.\n\n"
            f"Add them to {ROOT / '.env'} (copy .env.example first):\n"
            "    DEEPSEEK_API_KEY=your-deepseek-api-key\n"
            "    TAVILY_API_KEY=tvly-...\n\n"
            "This script makes real, billable API calls -- it is deliberately "
            "not part of the pytest suite.",
            file=sys.stderr,
        )
        # 2 distinguishes "not configured" from "ran and a check failed".
        raise SystemExit(2)


def wait_for_health(base: str, proc: subprocess.Popen, timeout: float = 45.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            sys.exit(f"Server exited early with code {proc.returncode}.")
        try:
            r = httpx.get(f"{base}/api/health", timeout=2.0)
            if r.status_code == 200:
                return r.json()
        except Exception as exc:  # noqa: BLE001 - server not up yet
            last_error = exc
        time.sleep(0.3)
    sys.exit(f"Server did not become healthy within {timeout}s ({last_error}).")


def run(query: str, timeout: float) -> int:
    check_keys()

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    log(f"Starting server on port {port} ...")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "main:app",
            "--host", "127.0.0.1", "--port", str(port), "--workers", "1",
        ],
        cwd=BACKEND,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        health = wait_for_health(base, proc)
        log(f"  healthy -- model: {health.get('model')}\n")
        log(f"Query: {query!r}\n")

        started = time.monotonic()
        r = httpx.post(f"{base}/api/research", json={"query": query}, timeout=30.0)
        r.raise_for_status()
        session_id = r.json()["session_id"]

        tokens: list[str] = []
        agent_events: list[dict] = []
        complete: dict | None = None
        error: str | None = None
        first_token_at: float | None = None
        first_output_at: float | None = None
        analysis: list[str] = []
        event = None

        with httpx.stream(
            "GET", f"{base}/api/research/{session_id}/stream", timeout=timeout
        ) as stream:
            for line in stream.iter_lines():
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
                    elapsed = time.monotonic() - started
                    if event == "agent_update":
                        agent_events.append(data)
                        detail = data.get("detail")
                        if isinstance(detail, list):
                            detail = f"{len(detail)} item(s)"
                        log(f"  [{elapsed:6.1f}s] {data['agent']:<11} {data['action']}"
                            + (f" -- {detail}" if detail else ""))
                    elif event == "analysis_token":
                        if first_output_at is None:
                            first_output_at = elapsed
                            log(f"  [{elapsed:6.1f}s] Analyst     streaming analysis ...")
                        analysis.append(data["text"])
                    elif event == "report_token":
                        if first_token_at is None:
                            first_token_at = elapsed
                            if first_output_at is None:
                                first_output_at = elapsed
                            log(f"  [{elapsed:6.1f}s] Writer      streaming report ...")
                        tokens.append(data["text"])
                    elif event == "complete":
                        complete = data
                        log(f"  [{elapsed:6.1f}s] complete")
                    elif event == "error":
                        error = data.get("message")
                        log(f"  [{elapsed:6.1f}s] ERROR: {error}")

        total = time.monotonic() - started
        return report(
            query, tokens, agent_events, complete, error,
            first_token_at, first_output_at, analysis, total,
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def report(
    query, tokens, agent_events, complete, error,
    first_token_at, first_output_at, analysis, total,
) -> int:
    log("\n" + "=" * 70)
    checks: list[tuple[str, bool, str]] = []

    checks.append(("no error event", error is None, error or ""))
    checks.append(("run completed", complete is not None, ""))
    checks.append((
        "agents reported progress",
        len(agent_events) >= 3,
        f"{len(agent_events)} events",
    ))
    checks.append((
        "report streamed incrementally",
        len(tokens) > 1,
        f"{len(tokens)} chunks",
    ))
    checks.append((
        "analysis streamed before the report",
        len(analysis) > 1,
        f"{len(analysis)} chunks",
    ))

    if complete:
        final = complete.get("final_report", "")
        streamed = "".join(tokens)
        checks.append((
            "streamed text matches final report",
            streamed == final,
            f"{len(streamed)} vs {len(final)} chars",
        ))
        checks.append(("report is substantial", len(final) > 500, f"{len(final)} chars"))
        checks.append((
            "report cites sources",
            len(complete.get("sources", [])) > 0,
            f"{len(complete.get('sources', []))} sources",
        ))
        checks.append((
            "report has the requested structure",
            "## " in final,
            "markdown headers present",
        ))

    for name, ok, detail in checks:
        log(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))

    log("")
    if first_output_at is not None:
        log(f"  time to first visible output : {first_output_at:.1f}s")
    if first_token_at is not None:
        log(f"  time to first report token   : {first_token_at:.1f}s")
    log(f"  total run time               : {total:.1f}s")

    if complete and complete.get("unanswered_tasks"):
        log(f"  sub-questions with no sources: {complete['unanswered_tasks']}")

    if complete and complete.get("final_report"):
        out = ROOT / "scripts" / "last_live_report.md"
        out.write_text(
            f"# Live smoke run\n\n**Query:** {query}\n\n"
            f"**Sources:** {len(complete.get('sources', []))}  \n"
            f"**Total time:** {total:.1f}s\n\n---\n\n{complete['final_report']}\n",
            encoding="utf-8",
        )
        log(f"\n  report written to {out.relative_to(ROOT)}")

    failed = [n for n, ok, _ in checks if not ok]
    log("=" * 70)
    if failed:
        log(f"FAILED: {', '.join(failed)}")
        return 1
    log("All checks passed.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", default=DEFAULT_QUERY)
    p.add_argument("--timeout", type=float, default=240.0)
    args = p.parse_args()
    return run(args.query, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
