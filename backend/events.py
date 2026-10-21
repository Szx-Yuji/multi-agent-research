"""Lets graph nodes push incremental output back to the run's event queue.

The nodes run on a worker thread owned by main.py. A ContextVar avoids adding a
callback argument to every node signature. With no emitter installed, emit() is
a no-op.
"""
import contextvars
from typing import Callable, Optional

_emitter: contextvars.ContextVar[Optional[Callable[[str, dict], None]]] = (
    contextvars.ContextVar("research_emitter", default=None)
)


def set_emitter(fn: Optional[Callable[[str, dict], None]]) -> None:
    _emitter.set(fn)


def emit(event_type: str, data: dict) -> None:
    fn = _emitter.get()
    if fn is not None:
        fn(event_type, data)


def emit_log(logs: list[dict], entry: dict) -> list[dict]:
    """Record a log entry and stream it now.

    The graph only yields to main.py when a node returns, so a node that does
    several seconds of work per item (the Researcher) would otherwise report
    all of it in one burst at the end.
    """
    logs.append(entry)
    emit("agent_update", entry)
    return logs
