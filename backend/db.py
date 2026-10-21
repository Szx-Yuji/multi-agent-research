"""Database models and session handling for users and saved research runs.

SQLite by default so the app runs with no setup. Point DATABASE_URL at
Postgres to run more than one instance.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

import config


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    runs: Mapped[list["ResearchRun"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    query: Mapped[str] = mapped_column(Text)
    final_report: Mapped[str] = mapped_column(Text)
    # JSON-encoded; portable across SQLite and Postgres without a dialect type.
    sub_tasks_json: Mapped[str] = mapped_column(Text, default="[]")
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

    user: Mapped[User] = relationship(back_populates="runs")

    def summary(self) -> dict:
        return {
            "id": self.id,
            "query": self.query,
            "created_at": self.created_at.isoformat(),
            "duration_seconds": round(self.duration_seconds, 1),
            "source_count": len(json.loads(self.sources_json or "[]")),
        }

    def detail(self) -> dict:
        return {
            **self.summary(),
            "final_report": self.final_report,
            "sub_tasks": json.loads(self.sub_tasks_json or "[]"),
            "sources": json.loads(self.sources_json or "[]"),
        }


_engine = None
_SessionLocal = None


def _make_engine():
    url = config.DATABASE_URL
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        # The path is relative to the backend dir; make sure it exists.
        if ":///" in url and not url.endswith(":memory:"):
            Path(url.split(":///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def init_db() -> None:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = _make_engine()
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)


def get_session():
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()


def reset() -> None:
    """Drop the engine so the next init picks up a new DATABASE_URL. Tests only."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
