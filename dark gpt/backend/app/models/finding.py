"""Modelli dei finding, delle evidenze e della macchina a stati."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, enum_column
from .enums import EvidenceKind, FindingSeverity, FindingStatus


class Finding(Base, TimestampMixin):
    """Una vulnerabilita' ipotizzata, validata o confermata."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    component: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    status: Mapped[FindingStatus] = enum_column(
        FindingStatus, "finding_status", default=FindingStatus.POTENTIAL
    )
    severity: Mapped[FindingSeverity] = enum_column(
        FindingSeverity, "finding_severity", default=FindingSeverity.MEDIUM
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cvss_vector: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    impact: Mapped[str] = mapped_column(Text, default="", nullable=False)
    remediation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    location: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    cwe: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    owasp: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    project = relationship("Project", back_populates="findings")
    evidences = relationship(
        "FindingEvidence",
        back_populates="finding",
        cascade="all, delete-orphan",
        order_by="FindingEvidence.id",
    )
    state_changes = relationship(
        "StateChange",
        back_populates="finding",
        cascade="all, delete-orphan",
        order_by="StateChange.id",
    )


class FindingEvidence(Base):
    """Evidenza a supporto di un finding."""

    __tablename__ = "finding_evidences"

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[EvidenceKind] = enum_column(EvidenceKind, "evidence_kind")
    payload: Mapped[str] = mapped_column(Text, default="", nullable=False)
    observed: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    finding = relationship("Finding", back_populates="evidences")


class StateChange(Base):
    """Transizione di stato registrata: ogni cambio deve essere motivato."""

    __tablename__ = "finding_state_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[FindingStatus] = enum_column(
        FindingStatus, "finding_status_from"
    )
    to_status: Mapped[FindingStatus] = enum_column(FindingStatus, "finding_status_to")
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    actor: Mapped[str] = mapped_column(String(120), default="operator", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    finding = relationship("Finding", back_populates="state_changes")
