"""Tool-calling: espone i tool del registry al provider LLM.

Regola di sicurezza: il modello puo' **proporre** una chiamata, ma
l'esecuzione passa sempre dal runner, che riapplica validazione, scope,
conferma e budget. Il modello non ottiene mai la conferma automatica, e i
tool attivi non sono esposti (non e' il posto giusto per eseguire test
attivi).
"""

from __future__ import annotations

import json
from typing import Any

from ..tools.registry import registry
from ..tools.runner import run_tool

#: Numero massimo di cicli di tool-calling in una singola risposta.
MAX_TOOL_ITERATIONS = 3


def build_tool_schemas() -> list[dict[str, Any]]:
    """Deriva gli schemi tool dal registry, in formato OpenAI-compatible.

    Sono esposti solo i tool marcati `model_callable`: i tool attivi (che
    modificano lo stato) restano sotto il controllo diretto dell'operatore.
    """
    schemas: list[dict[str, Any]] = []
    for spec in registry.list():
        if not spec.model_callable:
            continue
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema,
                },
            }
        )
    return schemas


def execute_tool_call(
    session: Any,
    project: Any,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Esegue una chiamata richiesta dal modello e restituisce l'osservazione.

    Il modello non riceve mai `confirm=True`: un tool che richiede conferma
    viene eseguito ma la conferma arriva dal runner, non dal modello.
    """
    try:
        result = run_tool(
            session,
            project,
            tool_name,
            arguments,
            # Il modello non autorizza mai operazioni mutanti: la conferma
            # e'-responsabilita' dell'operatore.
            confirm=False,
        )
    except Exception as exc:  # noqa: BLE001 - l'osservazione deve essere JSON
        return {
            "tool": tool_name,
            "status": "ERROR",
            "output": f"{type(exc).__name__}: {exc}",
        }

    observation: dict[str, Any] = {
        "tool": result.tool_name,
        "status": result.status.value,
    }
    if result.status.value == "SUCCESS":
        observation["output"] = result.output
    else:
        observation["error"] = result.error
        if result.details:
            observation["details"] = result.details
    return observation


def tool_result_messages(
    tool_calls: list[Any],
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Costruisce i messaggi di risultato per il secondo turno del provider."""
    messages: list[dict[str, Any]] = []
    for index, call in enumerate(tool_calls):
        observation = observations[index] if index < len(observations) else {}
        messages.append(
            {
                "role": "tool",
                "tool_call_id": getattr(call, "id", f"call_{index}"),
                "content": json.dumps(observation, ensure_ascii=False, default=str),
            }
        )
    return messages


def assistant_tool_call_message(response: Any) -> dict[str, Any]:
    """Ricostruisce il messaggio assistant che contiene le chiamate ai tool."""
    return {
        "role": "assistant",
        "content": response.content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in response.tool_calls
        ],
    }
