"""API della chat AI di progetto."""

from __future__ import annotations

from fastapi import APIRouter

from ...ai.provider import get_provider
from ...schemas.chat import ChatHistoryResponse, ChatMessageRead, ChatRequest
from ...services.chat_service import ChatService
from ..deps import CurrentProject, DbSession

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


@router.get("", response_model=ChatHistoryResponse, summary="Cronologia della chat")
def get_history(project: CurrentProject, session: DbSession) -> ChatHistoryResponse:
    service = ChatService(session)
    messages = service.history(project.id, limit=100)
    provider = get_provider()
    return ChatHistoryResponse(
        project_id=project.id,
        messages=[
            ChatMessageRead.model_validate(message, from_attributes=True)
            for message in messages
        ],
        provider=provider.name,
        provider_configured=not getattr(provider, "simulated", False)
        and provider.name != "mock",
    )


@router.post("", response_model=ChatMessageRead, summary="Invia un messaggio")
def send_message(
    payload: ChatRequest, project: CurrentProject, session: DbSession
) -> ChatMessageRead:
    """Invia un messaggio al provider con il contesto del progetto.

    Se il provider non e' configurato, la risposta arriva dal provider mock
    ed e' marcata `simulated=true`: la UI la mostra come simulata.
    """
    service = ChatService(session)
    _response, message = service.send(project, payload.message, payload.role)
    return ChatMessageRead.model_validate(message, from_attributes=True)
