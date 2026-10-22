"""Schemi dei tool, delle scansioni e delle chat."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..models.enums import ToolRunStatus
from .common import StrictModel


class ToolDescribe(BaseModel):
    """Descrizione di un tool per la UI (Tool Manager)."""

    name: str
    category: str
    description: str
    input_schema: dict[str, Any]
    requires_scope: bool
    mutating: bool
    timeout_seconds: int
    technique: str
    install_hint: str
    in_process: bool
    availability: str
    availability_reason: str
    version: str


class ScanRequest(StrictModel):
    """Avvio di una scansione con un tool del registry."""

    tool: str = Field(min_length=1, max_length=120)
    input: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False
    target: str | None = Field(default=None, max_length=2048)
    technique: str | None = Field(default=None, max_length=128)


class ToolRunRead(BaseModel):
    """Esecuzione di tool in uscita."""

    id: int
    project_id: int
    tool_name: str
    status: ToolRunStatus
    input_json: dict[str, Any]
    output_text: str
    output_hash: str
    exit_code: int | None
    duration_ms: int
    error_text: str
    created_at: datetime


class ToolRunResult(BaseModel):
    """Esito immediato di una scansione."""

    status: ToolRunStatus
    tool: str
    output: Any = None
    output_text: str = ""
    error: str = ""
    duration_ms: int = 0
    exit_code: int | None = None
    run_id: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
