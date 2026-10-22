"""API delle impostazioni: stato del provider LLM e configurazione operativa.

Le impostazioni non espongono mai i segreti: la chiave API e' indicata solo
come booleano.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ...core.config import get_settings
from ...core.logging import recent_logs
from ...tools.registry import registry

router = APIRouter(tags=["settings"])


class LlmStatus(BaseModel):
    """Stato del provider LLM (senza segreti)."""

    provider: str
    base_url: str
    model: str
    api_key_set: bool
    configured: bool
    temperature: float
    max_tokens: int
    timeout: float


class LimitsStatus(BaseModel):
    """Limiti operativi in vigore."""

    http_max_requests_per_run: int
    http_timeout: float
    tool_timeout_default: int
    tool_max_output_bytes: int
    scan_max_files: int
    scan_max_file_bytes: int
    llm_context_max_chars: int


class LogEntry(BaseModel):
    """Record di log in memoria."""

    ts: str
    level: str
    event: str
    logger: str = ""


@router.get("/settings/llm", response_model=LlmStatus, summary="Stato del provider LLM")
def llm_status() -> LlmStatus:
    settings = get_settings()
    from ...ai.provider import get_provider

    provider = get_provider(settings)
    return LlmStatus(
        provider=provider.name,
        base_url=settings.effective_llm_base_url,
        model=settings.llm_model,
        api_key_set=bool(settings.llm_api_key),
        configured=settings.llm_configured and provider.name != "mock",
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout,
    )


@router.get("/settings/limits", response_model=LimitsStatus, summary="Limiti operativi")
def limits_status() -> LimitsStatus:
    settings = get_settings()
    return LimitsStatus(
        http_max_requests_per_run=settings.http_max_requests_per_run,
        http_timeout=settings.http_timeout,
        tool_timeout_default=settings.tool_timeout_default,
        tool_max_output_bytes=settings.tool_max_output_bytes,
        scan_max_files=settings.scan_max_files,
        scan_max_file_bytes=settings.scan_max_file_bytes,
        llm_context_max_chars=settings.llm_context_max_chars,
    )


@router.get("/logs", response_model=list[LogEntry], summary="Log recenti in memoria")
def logs(limit: int = Query(default=100, ge=1, le=500)) -> list[LogEntry]:
    """Ultimi record di log.

    Il buffer e' volatile: non e' un archivio di audit. La fonte autorevole
    per l'audit e' la tabella `tool_runs`.
    """
    return [LogEntry(**entry) for entry in recent_logs(limit)]


@router.get("/overview", summary="Panoramica operativa")
def overview() -> dict[str, Any]:
    """Panoramica sintetica per la dashboard."""
    settings = get_settings()
    described = registry.describe()
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "llm_configured": settings.llm_configured,
        "tools": {
            "total": len(described),
            "available": sum(1 for item in described if item["availability"] == "available"),
            "unavailable": sum(
                1 for item in described if item["availability"] == "unavailable"
            ),
        },
        "lab_root": str(settings.lab_root),
    }
