"""Schemi dei finding e delle evidenze."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..models.enums import EvidenceKind, FindingSeverity, FindingStatus
from .common import StrictModel


class EvidenceCreate(StrictModel):
    """Evidenza da allegare a un finding."""

    kind: EvidenceKind = EvidenceKind.MANUAL_NOTE
    payload: str = Field(default="", max_length=200_000)
    observed: str = Field(default="", max_length=100_000)
    source: str = Field(default="", max_length=2000)


class EvidenceRead(BaseModel):
    """Evidenza in uscita."""

    id: int
    finding_id: int
    kind: EvidenceKind
    payload: str
    observed: str
    source: str
    created_at: datetime


class StateChangeRead(BaseModel):
    """Transizione di stato registrata."""

    id: int
    finding_id: int
    from_status: FindingStatus
    to_status: FindingStatus
    reason: str
    actor: str
    created_at: datetime


class FindingCreate(StrictModel):
    """Creazione di un finding."""

    title: str = Field(min_length=1, max_length=300)
    category: str = Field(default="", max_length=100)
    component: str = Field(default="", max_length=300)
    severity: FindingSeverity = FindingSeverity.MEDIUM
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    hypothesis: str = Field(default="", max_length=50_000)
    impact: str = Field(default="", max_length=50_000)
    remediation: str = Field(default="", max_length=50_000)
    location: str = Field(default="", max_length=1024)
    cwe: str = Field(default="", max_length=32)
    owasp: str = Field(default="", max_length=64)
    evidence: list[EvidenceCreate] = Field(default_factory=list, max_length=50)


class FindingUpdate(StrictModel):
    """Modifica dei campi descrittivi di un finding (non dello stato)."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    category: str | None = Field(default=None, max_length=100)
    component: str | None = Field(default=None, max_length=300)
    severity: FindingSeverity | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    hypothesis: str | None = Field(default=None, max_length=50_000)
    impact: str | None = Field(default=None, max_length=50_000)
    remediation: str | None = Field(default=None, max_length=50_000)
    location: str | None = Field(default=None, max_length=1024)
    cwe: str | None = Field(default=None, max_length=32)
    owasp: str | None = Field(default=None, max_length=64)
    cvss_vector: str | None = Field(default=None, max_length=128)


class FindingTransitionRequest(StrictModel):
    """Richiesta di transizione di stato."""

    status: FindingStatus
    reason: str = Field(min_length=1, max_length=4000)
    actor: str = Field(default="operator", max_length=120)
    evidence: list[EvidenceCreate] = Field(default_factory=list, max_length=50)


class FindingRead(BaseModel):
    """Finding in uscita."""

    id: int
    project_id: int
    title: str
    category: str
    component: str
    status: FindingStatus
    severity: FindingSeverity
    confidence: float
    cvss_score: float | None
    cvss_vector: str
    hypothesis: str
    impact: str
    remediation: str
    location: str
    cwe: str
    owasp: str
    created_at: datetime
    updated_at: datetime
    evidences: list[EvidenceRead] = Field(default_factory=list)
    state_changes: list[StateChangeRead] = Field(default_factory=list)
