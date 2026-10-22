"""Schemi della chat AI."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .common import StrictModel


class ChatRequest(StrictModel):
    """Messaggio inviato alla chat AI di un progetto."""

    message: str = Field(min_length=1, max_length=100_000)
    role: str = Field(default="analysis", max_length=32)
    stream: bool = False


class ChatMessageRead(BaseModel):
    """Messaggio di chat in uscita."""

    id: int
    project_id: int
    role: str
    content: str
    tool_calls: dict[str, Any]
    simulated: bool
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """Cronologia della chat di un progetto."""

    project_id: int
    messages: list[ChatMessageRead]
    provider: str
    provider_configured: bool
