"""Modelli di progetto, file analizzati e report."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, enum_column
from .enums import ProjectMode, ReportFormat


class Project(Base, TimestampMixin):
    """Un progetto di sicurezza: e' il contenitore di ogni altro dato."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mode: Mapped[ProjectMode] = enum_column(ProjectMode, "project_mode")
    stack: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    root_path: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    scope_policy = relationship(
        "ScopePolicy", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    findings = relationship(
        "Finding", back_populates="project", cascade="all, delete-orphan"
    )
    files = relationship(
        "FileRecord", back_populates="project", cascade="all, delete-orphan"
    )
    tool_runs = relationship(
        "ToolRun", back_populates="project", cascade="all, delete-orphan"
    )
    chat_messages = relationship(
        "ChatMessage", back_populates="project", cascade="all, delete-orphan"
    )
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan")


class FileRecord(Base):
    """File analizzato: costituisce la memoria del progetto."""

    __tablename__ = "file_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    language: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(default=0, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    project = relationship("Project", back_populates="files")


class Report(Base):
    """Report generato a partire dai finding di un progetto."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    format: Mapped[ReportFormat] = enum_column(ReportFormat, "report_format")
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    project = relationship("Project", back_populates="reports")
