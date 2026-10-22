"""Schemi di progetto, file analizzati e report."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..models.enums import ProjectMode, ReportFormat
from .common import StrictModel


class ProjectCreate(StrictModel):
    """Creazione di un progetto."""

    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    mode: ProjectMode = ProjectMode.PASSIVE
    stack: list[str] = Field(default_factory=list, max_length=50)
    root_path: str = Field(default="", max_length=1024)


class ProjectUpdate(StrictModel):
    """Modifica dei campi modificabili di un progetto."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    stack: list[str] | None = Field(default=None, max_length=50)
    root_path: str | None = Field(default=None, max_length=1024)


class ProjectModeUpdate(StrictModel):
    """Cambio della modalita' operativa del progetto."""

    mode: ProjectMode


class ProjectRead(BaseModel):
    """Progetto in uscita."""

    id: int
    name: str
    description: str
    mode: ProjectMode
    stack: list[str]
    root_path: str
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseModel):
    """Riepilogo di un progetto con i contatori dei finding."""

    project: ProjectRead
    findings_total: int
    findings_confirmed: int
    findings_open: int
    assets_in_scope: int
    tool_runs: int


class FileRecordRead(BaseModel):
    """File analizzato registrato nella memoria del progetto."""

    id: int
    path: str
    sha256: str
    language: str
    size_bytes: int
    analyzed_at: datetime


class ReportRead(BaseModel):
    """Report generato."""

    id: int
    project_id: int
    format: ReportFormat
    content: str
    created_at: datetime
