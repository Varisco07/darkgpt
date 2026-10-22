"""Engine SQLAlchemy, session factory e bootstrap del database."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..models.base import Base
from .config import get_settings
from .logging import get_logger

logger = get_logger("db")

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _build_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url
    kwargs: dict = {"echo": settings.sql_echo, "future": True}
    if url.startswith("sqlite"):
        # FastAPI serve le richieste da thread diversi dal thread principale.
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
            finally:
                cursor.close()

    return engine


def get_engine() -> Engine:
    """Restituisce l'engine globale, creandolo alla prima chiamata."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
        logger.info("engine_created", extra={"extra_fields": {"dialect": _engine.dialect.name}})
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Restituisce la session factory globale."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False, future=True
        )
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessione transazionale: commit on success, rollback on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Crea le tabelle mancanti."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("db_initialized", extra={"extra_fields": {"tables": len(Base.metadata.tables)}})


def reset_db_state() -> None:
    """Scarta engine e session factory (usato dai test)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def database_file_path() -> Path | None:
    """Percorso del file SQLite, se il backend e' SQLite. None altrimenti."""
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        return None
    raw = url.removeprefix("sqlite:///").split("?", 1)[0]
    return Path(raw)
