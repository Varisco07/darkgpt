"""Fixture di test: database temporaneo, client HTTP e progetto di esempio.

I test usano un database SQLite in-memory: nessun dato finisce nel database
reale dell'applicazione.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Le impostazioni devono essere applicate prima dell'import di `app.core.config`.
os.environ["DARKGPT_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DARKGPT_LLM_BASE_URL"] = ""

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core import db as db_module  # noqa: E402
from app.models import Base, Project  # noqa: E402
from app.models.enums import ProjectMode  # noqa: E402


@pytest.fixture()
def engine():
    """Engine SQLite in-memory condiviso tra tutti i thread.

    `StaticPool` e' necessario: con il pool di default ogni thread aprirebbe
    una connessione distinta e quindi un database in-memory diverso.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def session(engine) -> Session:  # noqa: ANN001
    """Sessione SQLAlchemy su database temporaneo."""
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db_session:
        yield db_session


@pytest.fixture()
def client(engine, monkeypatch) -> TestClient:  # noqa: ANN001
    """TestClient FastAPI con il database temporaneo iniettato."""
    from app.main import create_app

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(db_module, "get_session_factory", lambda: factory)
    monkeypatch.setattr(db_module, "get_engine", lambda: engine)
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture()
def project(session) -> Project:  # noqa: ANN001
    """Progetto di esempio in modalita' PASSIVE."""
    sample = Project(
        name="Progetto di test",
        description="Progetto usato dai test automatici",
        mode=ProjectMode.PASSIVE,
        stack=["python"],
        root_path="",
    )
    session.add(sample)
    session.flush()
    return sample
