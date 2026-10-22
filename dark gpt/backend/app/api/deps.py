"""Dipendenze FastAPI: sessione DB, progetto corrente e servizi."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.orm import Session

from ..core import db as db_module
from ..core.errors import NotFoundError
from ..models.project import Project


def get_db() -> Iterator[Session]:
    """Sessione SQLAlchemy per la richiesta, con commit/rollback automatici.

    La session factory e' richiamata via il modulo `core.db`: in questo modo
    i test possono sostituirla senza che la dipendenza resti legata a una
    funzione importata per nome.
    """
    session = db_module.get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]


def get_project(
    session: DbSession,
    project_id: Annotated[int, Path(ge=1, description="ID del progetto")],
) -> Project:
    """Carica il progetto indicato dalla rotta, verificando che esista."""
    project = session.get(Project, project_id)
    if project is None:
        raise NotFoundError(
            f"progetto {project_id} non trovato",
            details={"project_id": project_id},
        )
    return project


CurrentProject = Annotated[Project, Depends(get_project)]
