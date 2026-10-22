"""Base dichiarativa e tipi condivisi dei modelli."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Timestamp UTC corrente, naive (compatibile SQLite e PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Base dichiarativa SQLAlchemy 2.0."""


def enum_column(
    enum_cls: type[enum.Enum], name: str, **kwargs: Any
) -> Mapped[Any]:
    """Colonna Enum persistita come stringa (portabile SQLite/PostgreSQL).

    I parametri aggiuntivi (``default``, ``nullable``, ``index``...) vengono
    inoltrati a :class:`sqlalchemy.Enum`.
    """
    return mapped_column(
        SAEnum(
            enum_cls,
            name=name,
            native_enum=False,
            values_callable=lambda e: [member.value for member in e],
            length=64,
        ),
        **kwargs,
    )


class TimestampMixin:
    """Aggiunge created_at/updated_at automatici."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
