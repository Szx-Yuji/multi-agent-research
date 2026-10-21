# Architecture Decision Records

## ADR-001: Use LangGraph over raw LangChain chains

**Status**: Accepted — implemented

**Context**: The research workflow requires conditional branching — if a search pass returns poor results, the workflow should retry with refined queries. Linear chains can't express this cleanly.

**Decision**: Use LangGraph's `StateGraph` to model the agent workflow as a directed graph with explicit state transitions.

**Implementation**: `route_after_research` in `backend/graph.py` inspects coverage (how many sub-questions produced sources) after every research pass. A thin pass with retry budget left routes to the `refiner` node, which rewrites the unproductive sub-questions; the graph then loops back to `researcher`. `retry_count` and `MAX_RESEARCH_RETRIES` bound the cycle. A healthy pass goes straight to `analyst`.

**Consequences**: More setup boilerplate, but the workflow is inspectable, testable per-node, and easy to extend. The cycle needs an explicit bound — an unbounded refine loop would spend the API budget on a query that will never match anything.

---

## ADR-002: Server-Sent Events over WebSockets for streaming

**Status**: Accepted

**Context**: Needed real-time streaming from FastAPI to React. Both SSE and WebSockets support this.

**Decision**: Use SSE (`text/event-stream`). It's unidirectional (server → client), which matches our use case exactly. No need for bidirectional communication.

**Consequences**: Simpler server implementation (`StreamingResponse` in FastAPI). Client uses the native `EventSource` API. The browser handles reconnect automatically — though a reconnect cannot resume a completed run, since session queues are dropped once drained.

---

## ADR-003: Separate Render (backend) and Vercel (frontend) deployments

**Status**: Accepted

**Context**: Could deploy everything on one platform or split across specialized platforms.

**Decision**: Backend on Render (Docker container support, persistent services), frontend on Vercel (optimized for static/React builds, global CDN).

**Consequences**: CORS and environment variables must be managed across two platforms. The backend's allowed origins are configuration, not code — `CORS_ALLOW_ORIGINS` for the production origin and `CORS_ALLOW_ORIGIN_REGEX` for Vercel preview URLs, whose hostname changes per build. Both free tiers are sufficient for demo purposes.

---

## ADR-004: DeepSeek as primary LLM

**Status**: Accepted

**Context**: The project is migrating its model provider to DeepSeek while
preserving the LangGraph workflow, sourced reports and SSE interface.

**Decision**: Use DeepSeek with `deepseek-flash` as the default model and
`https://api.deepseek.com` as the default base URL. The OpenAI Python SDK connects
to the DeepSeek service and calls `chat.completions.create`; system prompts are
messages with `role="system"`. Planner and Refiner read the returned message
content, while Analyst and Writer use `stream=True` and forward
`chunk.choices[0].delta.content` as the existing SSE text events.

**Consequences**: Model calls are billed by DeepSeek. All four LLM agents share
the client factory in `backend/llm.py`. The API key is read in that factory;
the model, endpoint, request timeout and thinking mode are read in
`backend/config.py`. They use
`DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL`,
`DEEPSEEK_TIMEOUT_SECONDS` and `DEEPSEEK_THINKING`. The project explicitly sends
`extra_body={"thinking": {"type": "disabled"}}` by default; `enabled` is an
optional configuration value. Streamed product content uses the answer field,
not the separate reasoning field. The SDK package does not select the provider:
the configured endpoint, credentials and model route these calls to DeepSeek.
Migration checks use fake clients and the real SDK with a mocked HTTP transport;
live output quality and latency require a separate billable smoke run.

---

## ADR-005: Keep session state in process, and run one worker

**Status**: Superseded by ADR-006

**Context**: A research run is started by `POST /api/research` and consumed by a later `GET .../stream`. The two requests need to share a queue.

**Decision**: Hold session queues in a process-local dict, and run uvicorn with `--workers 1`. A background sweeper drops sessions whose client never connected, and `MAX_ACTIVE_SESSIONS` applies backpressure.

**Consequences**: Simple, no extra infrastructure, and correct for a single-instance demo. It does not survive a restart and cannot scale horizontally — with two workers, a POST handled by worker A creates a session worker B cannot find. Redis is the migration path if this ever needs more than one instance. This constraint is recorded in the Dockerfile, the README, and the `Session` docstring so it is not rediscovered by accident.


---

## ADR-006: Optional Redis for session state and the search cache

**Status**: Accepted

**Context**: ADR-005 accepted a single worker because session queues lived in a process-local dict. That ceiling was reached: two workers meant a POST handled by worker A created a session worker B could not find. Separately, repeated sub-questions were re-fetched from Tavily on every run.

**Decision**: Put both behind a `SessionStore` interface and a small cache module, each with two backends. Without `REDIS_URL` they use process memory and behave exactly as before. With it, queues become Redis lists and cached results become keyed entries with a TTL, so any worker can serve any session.

Redis is optional rather than required because a reviewer cloning this repo should not need to run infrastructure to see it work.

**Consequences**: `WEB_CONCURRENCY` above 1 is now safe, but only when Redis is configured — so `/api/health` reports `multi_worker_safe`, making the difference observable rather than assumed. Two code paths exist for both concerns, and both are tested. Cache staleness is bounded by `SEARCH_CACHE_TTL_SECONDS` (six hours by default), which suits research questions where the answer moves slowly; it is the wrong default for breaking news.

---

## ADR-007: Accounts and history in SQL, with anonymous use preserved

**Status**: Accepted

**Context**: The v1 plan put authentication and history out of scope. Both were later requested. The question was whether research should require an account.

**Decision**: Email and password with Argon2 hashing, bearer tokens signed with HS256, and runs saved per user. Research works signed out; history is the reason to sign in, not a gate in front of the product. Storage is SQLAlchemy against SQLite by default, so nothing needs configuring locally, with `DATABASE_URL` pointing at Postgres for a real deployment.

Argon2 rather than bcrypt because it has no password length ceiling and is the current password-hashing competition winner. Tokens are stateless, so signing out is a client-side discard rather than server revocation.

**Consequences**: Anonymous runs are not recoverable, which is the honest trade for not forcing signup. Stateless tokens cannot be revoked before they expire, so `AUTH_TOKEN_TTL_SECONDS` defaults to 14 days rather than something longer. `AUTH_SECRET` becomes security-critical: anyone holding it can forge a token for any account, so the app checks it at startup and refuses to be quiet about the built-in default, and `render.yaml` has the platform generate one. SQLite does not scale past a single host, which is why `DATABASE_URL` exists.
