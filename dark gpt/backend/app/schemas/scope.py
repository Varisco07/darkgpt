"""Schemi dello Scope Manager."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..models.enums import ScopeRuleEffect, ScopeRuleKind
from .common import StrictModel


class ScopePolicyImport(StrictModel):
    """Importazione di una policy di scope in formato testo libero."""

    text: str = Field(min_length=1, max_length=200_000)
    notes: str = Field(default="", max_length=4000)


class ScopeRuleCreate(StrictModel):
    """Creazione manuale di una regola di scope."""

    kind: ScopeRuleKind
    effect: ScopeRuleEffect
    pattern: str = Field(min_length=1, max_length=1024)
    technique: str = Field(default="", max_length=128)
    notes: str = Field(default="", max_length=2000)


class ScopeRuleRead(BaseModel):
    """Regola di scope in uscita."""

    id: int
    kind: ScopeRuleKind
    effect: ScopeRuleEffect
    pattern: str
    technique: str
    notes: str


class ScopeAssetRead(BaseModel):
    """Asset in scope in uscita."""

    id: int
    kind: ScopeRuleKind
    value: str
    allowed: bool
    technique: str
    notes: str


class ScopePolicyRead(BaseModel):
    """Policy di scope completa."""

    id: int
    project_id: int
    raw_text: str
    notes: str
    asset_count: int
    prohibited_techniques: list[str]
    rules: list[ScopeRuleRead]
    assets: list[ScopeAssetRead]
    created_at: datetime


class ScopeCheckRequest(StrictModel):
    """Richiesta di verifica di un target contro lo scope."""

    target: str = Field(min_length=1, max_length=2048)
    technique: str = Field(default="", max_length=128)


class ScopeCheckResponse(BaseModel):
    """Esito della verifica di scope."""

    decision: str
    reason: str
    matched_rule_id: int | None = None
    matched_pattern: str | None = None
    requires_confirmation: bool = False
    prohibited: list[str] = Field(default_factory=list)
