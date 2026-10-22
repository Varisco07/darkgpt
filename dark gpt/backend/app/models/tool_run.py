"""Modello delle esecuzioni dei tool."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, enum_column
from .enums import ToolRunStatus


class ToolRun(Base):
    """Traccia di una esecuzione di tool: fonte autorevole per l'audit."""

    __tablename__ = "tool_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    status: Mapped[ToolRunStatus] = enum_column(ToolRunStatus, "tool_run_status")
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    exit_code: Mapped[int | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int] = mapped_column(default=0, nullable=False)
    error_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    project = relationship("Project", back_populates="tool_runs")
