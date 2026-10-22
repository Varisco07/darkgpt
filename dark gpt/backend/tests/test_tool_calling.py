"""Test del tool-calling del provider LLM.

Si usa un provider finto che richiama un tool: l'obiettivo e' verificare che
l'esecuzione passi dal runner (quindi con scope, validazione e budget) e che
il tool attivo non sia mai esposto al modello.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.ai.provider import LlmResponse, ToolCall
from app.ai.tools import (
    MAX_TOOL_ITERATIONS,
    build_tool_schemas,
    execute_tool_call,
)
from app.models.enums import ProjectMode
from app.services.chat_service import ChatService
from app.tools.registry import registry


class ScriptedProvider:
    """Provider finto: restituisce risposte predefinite in sequenza."""

    name = "scripted"

    def __init__(self, responses: list[LlmResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages, tools=None, stream=False):  # noqa: ANN001, ANN201
        self.calls.append({"messages": messages, "tools": tools})
        if not self.responses:
            return LlmResponse(content="esaurito", model="scripted")
        return self.responses.pop(0)


@pytest.fixture()
def lab_project(session, project):
    """Progetto in modalita' LAB con la root del laboratorio."""
    project.mode = ProjectMode.LAB
    project.root_path = str(
        (__import__("pathlib").Path(__file__).resolve().parents[2] / "lab" / "sqli_app")
    )
    session.flush()
    return project


def test_active_tool_is_not_exposed_to_the_model():
    """Il tool HTTP non deve comparire fra i tool chiamabili dal modello."""
    names = {schema["function"]["name"] for schema in build_tool_schemas()}
    assert "http.request" not in names
    assert "sast.sql.python" in names


def test_schemas_follow_openai_format():
    for schema in build_tool_schemas():
        assert schema["type"] == "function"
        function = schema["function"]
        assert function["name"]
        assert function["description"]
        assert function["parameters"]["type"] == "object"


def test_execute_tool_call_runs_through_the_runner(session, lab_project):
    observation = execute_tool_call(
        session,
        lab_project,
        "sast.sql.python",
        {"path": lab_project.root_path},
    )
    assert observation["status"] == "SUCCESS"
    assert observation["output"]["summary"]["total"] >= 3


def test_execute_tool_call_reports_scope_denial(session, project):
    """Un tool fuori scope viene negato, non eseguito."""
    project.mode = ProjectMode.PASSIVE
    session.flush()
    observation = execute_tool_call(
        session,
        project,
        "sast.sql.python",
        {"path": project.root_path or "."},
    )
    assert observation["status"] == "DENIED"
    assert "error" in observation


def test_execute_tool_call_handles_unknown_tool(session, project):
    observation = execute_tool_call(session, project, "tool.inesistente", {})
    assert observation["status"] == "ERROR"


def test_chat_executes_tool_calls_and_continues(session, lab_project):
    """Il primo turno chiede un tool, il secondo turno usa il risultato."""
    provider = ScriptedProvider(
        [
            LlmResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="sast.sql.python",
                        arguments={"path": lab_project.root_path},
                    )
                ],
                model="scripted",
            ),
            LlmResponse(content="Ho analizzato il codice: 3 sospetti.", model="scripted"),
        ]
    )
    service = ChatService(session)
    response, message = service.send(lab_project, "analizza il lab", provider=provider)

    assert response.content == "Ho analizzato il codice: 3 sospetti."
    assert len(provider.calls) == 2
    # Il tool e' stato eseguito e il risultato e' stato rimandato al provider.
    assert message.tool_calls["executed"][0]["status"] == "SUCCESS"
    second_turn_roles = [message["role"] for message in provider.calls[1]["messages"]]
    assert "tool" in second_turn_roles


def test_chat_limits_tool_iterations(session, lab_project):
    """Il numero di cicli di tool-calling e' limitato."""
    provider = ScriptedProvider(
        [
            LlmResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id=f"call_{index}",
                        name="sast.sql.python",
                        arguments={"path": lab_project.root_path},
                    )
                ],
                model="scripted",
            )
            for index in range(MAX_TOOL_ITERATIONS + 3)
        ]
    )
    ChatService(session).send(lab_project, "loop", provider=provider)
    assert len(provider.calls) <= MAX_TOOL_ITERATIONS + 1


def test_registry_exposes_model_callable_flag():
    assert registry.get("sast.sql.python").model_callable is True
    assert registry.get("http.request").model_callable is False
