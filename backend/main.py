import asyncio
import json
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

load_dotenv()

# Imported after load_dotenv() so API keys are present when clients are built.
import config  # noqa: E402
import sessions as session_store  # noqa: E402
from agents.writer import collect_sources  # noqa: E402
from auth import (  # noqa: E402
    create_token,
    current_user,
    current_user_optional,
    hash_password,
    verify_password,
)
from db import ResearchRun, User, get_session, init_db  # noqa: E402
from events import set_emitter  # noqa: E402
from graph import compiled_graph  # noqa: E402


class ResearchRequest(BaseModel):
    query: str


class ResearchResponse(BaseModel):
    session_id: str


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    for problem in config.check_auth_secret():
        logger.warning("SECURITY: %s", problem)
    init_db()

    async def sweeper():
        while True:
            await asyncio.sleep(config.SESSION_SWEEP_INTERVAL_SECONDS)
            await asyncio.to_thread(session_store.get_store().reap)

    task = asyncio.create_task(sweeper())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Multi-Agent Research API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOW_ORIGINS,
    allow_origin_regex=config.CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _save_run(user_id: int, query: str, payload: dict, duration: float) -> None:
    """Persist a finished run. A storage failure must not break the stream."""
    try:
        with get_session() as session:
            session.add(
                ResearchRun(
                    user_id=user_id,
                    query=query,
                    final_report=payload.get("final_report", ""),
                    sub_tasks_json=json.dumps(payload.get("sub_tasks", [])),
                    sources_json=json.dumps(payload.get("sources", [])),
                    duration_seconds=duration,
                )
            )
            session.commit()
    except Exception:
        pass


def _run_graph_streaming(session_id: str, query: str, user_id: Optional[int]) -> None:
    """Run the graph on a worker thread, pushing events onto the session queue."""
    store = session_store.get_store()
    started = time.monotonic()

    accumulated_state: dict = {
        "query": query,
        "sub_tasks": [],
        "search_results": {},
        "analysis": "",
        "final_report": "",
        "agent_logs": [],
        "current_agent": "",
        "error": None,
        "unanswered_tasks": [],
        "retry_count": 0,
    }

    # Lets the Analyst and Writer stream chunks straight onto this queue.
    set_emitter(lambda event_type, data: store.push(session_id, event_type, data))

    try:
        for chunk in compiled_graph.stream(accumulated_state, stream_mode="updates"):
            for _node_name, node_output in chunk.items():
                for k, v in node_output.items():
                    if k == "agent_logs" and isinstance(v, list):
                        accumulated_state["agent_logs"] = v
                    elif v is not None:
                        accumulated_state[k] = v

                if accumulated_state.get("error"):
                    store.push(session_id, "error", {"message": accumulated_state["error"]})
                    return

        payload = {
            "final_report": accumulated_state.get("final_report", ""),
            "sub_tasks": accumulated_state.get("sub_tasks", []),
            "sources": collect_sources(accumulated_state.get("search_results", {})),
            "unanswered_tasks": accumulated_state.get("unanswered_tasks", []),
        }
        duration = time.monotonic() - started
        if user_id is not None and payload["final_report"]:
            _save_run(user_id, query, payload, duration)
        payload["saved"] = user_id is not None and bool(payload["final_report"])
        store.push(session_id, "complete", payload)
    except Exception as exc:  # noqa: BLE001 - last resort, must reach the client
        store.push(session_id, "error", {"message": str(exc)})
    finally:
        set_emitter(None)


@app.post("/api/research", response_model=ResearchResponse)
async def start_research(
    request: ResearchRequest, user: Optional[User] = Depends(current_user_optional)
):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    store = session_store.get_store()
    await asyncio.to_thread(store.reap)
    if store.count() >= config.MAX_ACTIVE_SESSIONS:
        raise HTTPException(
            status_code=429,
            detail="Too many research sessions in flight. Try again shortly.",
        )

    session_id = str(uuid.uuid4())
    store.create(session_id)

    threading.Thread(
        target=_run_graph_streaming,
        args=(session_id, request.query.strip(), user.id if user else None),
        daemon=True,
    ).start()

    return ResearchResponse(session_id=session_id)


@app.get("/api/research/{session_id}/stream")
async def stream_research(session_id: str):
    store = session_store.get_store()
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        start = asyncio.get_running_loop().time()
        try:
            while True:
                if asyncio.get_running_loop().time() - start > config.RESEARCH_TIMEOUT_SECONDS:
                    yield _sse_event(
                        "error",
                        {
                            "message": (
                                "Research timed out after "
                                f"{config.RESEARCH_TIMEOUT_SECONDS} seconds"
                            )
                        },
                    )
                    break

                item = await asyncio.to_thread(store.pop, session_id, 1.0)
                if item is None:
                    yield ": keepalive\n\n"
                    continue

                event_type, data = item
                yield _sse_event(event_type, data)

                if event_type in ("complete", "error"):
                    break
        finally:
            store.delete(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/auth/register", response_model=TokenResponse, status_code=201)
async def register(creds: Credentials):
    email = creds.email.lower()
    with get_session() as session:
        if session.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=409, detail="Email already registered")
        user = User(email=email, password_hash=hash_password(creds.password))
        session.add(user)
        session.commit()
        session.refresh(user)
        return TokenResponse(access_token=create_token(user.id), email=user.email)


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(creds: Credentials):
    email = creds.email.lower()
    with get_session() as session:
        user = session.query(User).filter(User.email == email).first()
        # Same message either way, so the response cannot enumerate accounts.
        if user is None or not verify_password(creds.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return TokenResponse(access_token=create_token(user.id), email=user.email)


@app.get("/api/auth/me")
async def me(user: User = Depends(current_user)):
    return {"email": user.email, "created_at": user.created_at.isoformat()}


@app.get("/api/history")
async def list_history(user: User = Depends(current_user), limit: int = 50):
    with get_session() as session:
        runs = (
            session.query(ResearchRun)
            .filter(ResearchRun.user_id == user.id)
            .order_by(ResearchRun.created_at.desc())
            .limit(min(limit, 200))
            .all()
        )
        return {"runs": [r.summary() for r in runs]}


@app.get("/api/history/{run_id}")
async def get_history_item(run_id: int, user: User = Depends(current_user)):
    with get_session() as session:
        run = session.get(ResearchRun, run_id)
        # 404 rather than 403 for someone else's run, so ids cannot be probed.
        if run is None or run.user_id != user.id:
            raise HTTPException(status_code=404, detail="Not found")
        return run.detail()


@app.delete("/api/history/{run_id}", status_code=204)
async def delete_history_item(run_id: int, user: User = Depends(current_user)):
    with get_session() as session:
        run = session.get(ResearchRun, run_id)
        if run is None or run.user_id != user.id:
            raise HTTPException(status_code=404, detail="Not found")
        session.delete(run)
        session.commit()


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@app.get("/api/health")
async def health():
    store = session_store.get_store()
    return {
        "status": "ok",
        "model": config.DEEPSEEK_MODEL,
        "active_sessions": store.count(),
        "shared_state": session_store.is_shared(),
        "multi_worker_safe": session_store.is_shared(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
