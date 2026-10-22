"""Modelli dello Scope Manager: policy, regole e asset derivati."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, enum_column
from .enums import ScopeRuleEffect, ScopeRuleKind


class ScopePolicy(Base, TimestampMixin):
    """Policy di scope di un progetto, importata da testo o costruita a mano."""

    __tablename__ = "scope_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    asset_count: Mapped[int] = mapped_column(default=0, nullable=False)
    prohibited_techniques: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )

    project = relationship("Project", back_populates="scope_policy")
    rules = relationship(
        "ScopeRule", back_populates="policy", cascade="all, delete-orphan"
    )
    assets = relationship(
        "ScopeAsset", back_populates="policy", cascade="all, delete-orphan"
    )


class ScopeRule(Base):
    """Regola singola della policy (ALLOW/DENY su dominio, path, tecnica)."""

    __tablename__ = "scope_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("scope_policies.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ScopeRuleKind] = enum_column(ScopeRuleKind, "scope_rule_kind")
    effect: Mapped[ScopeRuleEffect] = enum_column(ScopeRuleEffect, "scope_rule_effect")
    pattern: Mapped[str] = mapped_column(String(1024), nullable=False)
    technique: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    policy = relationship("ScopePolicy", back_populates="rules")


class ScopeAsset(Base):
    """Asset in scope, DERIVATO dalle regole: non inseribile a mano."""

    __tablename__ = "scope_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("scope_policies.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ScopeRuleKind] = enum_column(ScopeRuleKind, "scope_rule_kind")
    value: Mapped[str] = mapped_column(String(1024), nullable=False)
    allowed: Mapped[bool] = mapped_column(default=True, nullable=False)
    technique: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("scope_rules.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    policy = relationship("ScopePolicy", back_populates="assets")
