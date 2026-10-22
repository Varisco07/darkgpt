"""Schemi comuni a tutte le API."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class StrictModel(BaseModel):
    """Base dei modelli di richiesta: campi extra non ammessi."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ErrorResponse(BaseModel):
    """Struttura degli errori applicativi."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Stato di salute del servizio."""

    status: str
    version: str
    database: str
    llm_provider: str
    llm_configured: bool
    tools_available: int
    tools_total: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Risposta paginata generica."""

    items: list[T]
    total: int
    limit: int
    offset: int
