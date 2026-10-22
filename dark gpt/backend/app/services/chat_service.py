"""Servizio chat: costruzione del contesto di progetto e orchestrazione LLM.

Il contesto inviato al provider e' derivato esclusivamente dai dati gia'
presenti nel database del progetto. Il contenuto e' redattato e troncato
secondo un budget di caratteri configurabile.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.prompts import get_prompt
from ..ai.provider import LlmResponse, LLMProvider, get_provider
from ..ai.tools import (
    MAX_TOOL_ITERATIONS,
    assistant_tool_call_message,
    build_tool_schemas,
    execute_tool_call,
    tool_result_messages,
)
from ..core.config import get_settings
from ..core.security import redact
from ..models.chat import ChatMessage
from ..models.finding import Finding
from ..models.project import Project
from ..models.tool_run import ToolRun

#: Numero massimo di finding inclusi nel contesto.
MAX_CONTEXT_FINDINGS = 25

#: Numero massimo di esecuzioni di tool incluse nel contesto.
MAX_CONTEXT_RUNS = 10


def build_context(project: Project, session: Session) -> str:
    """Costruisce il contesto testuale del progetto per il provider LLM.

    Contiene solo informazioni gia' raccolte: descrizione, stack, asset in
    scope, finding registrati e ultime esecuzioni di tool.
    """
    settings = get_settings()
    blocks: list[str] = []

    blocks.append("## Contesto del progetto")
    blocks.append(f"- Nome: {project.name}")
    if project.description:
        blocks.append(f"- Descrizione: {project.description}")
    if project.stack:
        blocks.append(f"- Stack: {', '.join(project.stack)}")
    blocks.append(f"- Modalita' operativa: {project.mode.value}")
    if project.root_path:
        blocks.append(f"- Root dei sorgenti: {project.root_path}")

    scope_service_assets = _project_assets(project, session)
    if scope_service_assets:
        listed = ", ".join(asset.value for asset in scope_service_assets[:40])
        blocks.append(f"- Asset in scope ({len(scope_service_assets)}): {listed}")

    findings = list(
        session.scalars(
            select(Finding)
            .where(Finding.project_id == project.id)
            .order_by(Finding.id.desc())
            .limit(MAX_CONTEXT_FINDINGS)
        )
    )
    if findings:
        blocks.append("")
        blocks.append("## Finding registrati")
        for finding in findings:
            blocks.append(
                f"- [{finding.status.value}] {finding.title} "
                f"(severita' {finding.severity.value}, {finding.category or 'n.d.'})"
            )
            if finding.hypothesis:
                blocks.append(f"  ipotesi: {finding.hypothesis[:300]}")

    runs = list(
        session.scalars(
            select(ToolRun)
            .where(ToolRun.project_id == project.id)
            .order_by(ToolRun.id.desc())
            .limit(MAX_CONTEXT_RUNS)
        )
    )
    if runs:
        blocks.append("")
        blocks.append("## Ultime esecuzioni di tool")
        for run in runs:
            blocks.append(
                f"- {run.tool_name}: {run.status.value} "
                f"({run.duration_ms} ms) {run.error_text[:160]}"
            )

    context = redact("\n".join(blocks))
    budget = settings.llm_context_max_chars
    if len(context) > budget:
        context = context[:budget] + "\n...[contesto troncato]"
    return context


def _project_assets(project: Project, session: Session) -> list:
    """Asset della policy di scope del progetto."""
    from ..models.scope import ScopePolicy

    policy = session.scalar(
        select(ScopePolicy).where(ScopePolicy.project_id == project.id)
    )
    if policy is None:
        return []
    return list(policy.assets)


def build_messages(
    project: Project,
    session: Session,
    user_message: str,
    role: str = "analysis",
    history: list[ChatMessage] | None = None,
) -> list[dict[str, Any]]:
    """Costruisce la lista di messaggi per il provider."""
    system = get_prompt(role)
    context = build_context(project, session)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": f"{system}\n\n{context}"},
    ]
    for message in history or []:
        messages.append({"role": message.role, "content": message.content})
    messages.append({"role": "user", "content": redact(user_message)})
    return messages


class ChatService:
    """Orchestrazione della chat AI di un progetto."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def history(self, project_id: int, limit: int = 50) -> list[ChatMessage]:
        """Cronologia dei messaggi di un progetto (dal piu' recente)."""
        return list(
            self.session.scalars(
                select(ChatMessage)
                .where(ChatMessage.project_id == project_id)
                .order_by(ChatMessage.id.desc())
                .limit(limit)
            )
        )[::-1]

    def send(
        self,
        project: Project,
        user_message: str,
        role: str = "analysis",
        provider: LLMProvider | None = None,
    ) -> tuple[LlmResponse, ChatMessage]:
        """Invia un messaggio al provider e persiste lo scambio.

        Se il provider richiama dei tool, le chiamate vengono eseguite dal
        runner (convalidazione, scope, budget) e i risultati sono rimandati al
        provider per un secondo turno. Il numero di cicli e' limitato.

        Restituisce la risposta del provider e il messaggio persistito.
        """
        provider = provider or get_provider()
        history = self.history(project.id, limit=20)
        messages = build_messages(project, self.session, user_message, role, history)
        tool_schemas = build_tool_schemas()

        user_record = ChatMessage(
            project_id=project.id,
            role="user",
            content=redact(user_message),
            tool_calls={},
            simulated=False,
        )
        self.session.add(user_record)
        self.session.flush()

        response = provider.chat(messages, tools=tool_schemas, stream=False)
        if not isinstance(response, LlmResponse):  # pragma: no cover - difensivo
            raise TypeError("il provider ha restituito un tipo non atteso")

        used_tools: list[dict[str, Any]] = []
        iterations = 0
        while response.tool_calls and iterations < MAX_TOOL_ITERATIONS:
            observations = [
                execute_tool_call(self.session, project, call.name, call.arguments)
                for call in response.tool_calls
            ]
            used_tools.extend(observations)
            messages.append(assistant_tool_call_message(response))
            messages.extend(tool_result_messages(response.tool_calls, observations))
            response = provider.chat(messages, tools=tool_schemas, stream=False)
            if not isinstance(response, LlmResponse):  # pragma: no cover - difensivo
                raise TypeError("il provider ha restituito un tipo non atteso")
            iterations += 1

        assistant_record = ChatMessage(
            project_id=project.id,
            role="assistant",
            content=redact(response.content),
            tool_calls={
                "executed": used_tools,
                "requested": response.to_dict()["tool_calls"],
            },
            simulated=response.simulated,
        )
        self.session.add(assistant_record)
        self.session.flush()
        return response, assistant_record
