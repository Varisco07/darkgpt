"""Runner dei tool: validazione, scope, conferma, timeout, persistenza.

Il runner e' l'unico percorso di esecuzione: sia le richieste API sia le
chiamate tool-calling del modello passano di qui.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from ..core.errors import ScopeError
from ..core.logging import get_logger
from ..core.security import is_network_target, redact_mapping, sha256_text
from ..models.enums import ToolRunStatus
from ..models.project import Project
from ..models.tool_run import ToolRun
from ..services.scope import ScopeService
from .registry import ToolContext, ToolSpec, registry
from .schema import SchemaValidationError, apply_defaults, validate

logger = get_logger("runner")


@dataclass
class ToolResult:
    """Esito di un'esecuzione di tool."""

    status: ToolRunStatus
    tool_name: str
    output: Any = None
    output_text: str = ""
    error: str = ""
    duration_ms: int = 0
    exit_code: int | None = None
    run_id: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status is ToolRunStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "tool": self.tool_name,
            "output": self.output,
            "output_text": self.output_text,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "run_id": self.run_id,
            "details": self.details,
        }


def _serialize(output: Any) -> str:
    """Serializza l'output di un tool in testo, in modo leggibile e stabile."""
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):  # pragma: no cover
        return str(output)


def _derive_target(spec: ToolSpec, tool_input: dict[str, Any]) -> str:
    """Deriva il target da controllare contro lo scope.

    I tool che non espongono un campo `target` esplicito dichiarano il
    bersaglio in altri modi: la prima URL di una sequenza di richieste, il
    percorso di una scansione, l'URL singolo.
    """
    explicit = tool_input.get("target")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    url = tool_input.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()

    requests = tool_input.get("requests")
    if isinstance(requests, list) and requests:
        first = requests[0]
        if isinstance(first, dict):
            first_url = first.get("url")
            if isinstance(first_url, str) and first_url.strip():
                return first_url.strip()

    path = tool_input.get("path")
    if isinstance(path, str) and path.strip():
        return path.strip()

    return ""


def run_tool(
    session: Session,
    project: Project,
    tool_name: str,
    tool_input: dict[str, Any],
    *,
    confirm: bool = False,
    target: str | None = None,
    technique: str | None = None,
) -> ToolResult:
    """Esegue un tool applicando l'intera catena di controlli.

    Ordine dei controlli (nessuno e' skippabile):
    1. esistenza del tool
    2. disponibilita' reale del tool
    3. validazione e normalizzazione dell'input
    4. controllo di scope sul target
    5. conferma dell'operatore per i tool mutanti
    6. esecuzione con timeout
    7. validazione dell'output
    8. persistenza in ``tool_runs``
    """
    spec: ToolSpec = registry.get(tool_name)

    # 2. Disponibilita'.
    availability = registry.availability(tool_name)
    if not availability.available:
        result = ToolResult(
            status=ToolRunStatus.UNAVAILABLE,
            tool_name=tool_name,
            error=availability.reason or "tool non disponibile",
            details={"install_hint": spec.install_hint},
        )
        _persist(session, project, tool_name, tool_input, result)
        return result

    # 3. Validazione input.
    normalized_input = apply_defaults(tool_input or {}, spec.input_schema)
    errors = validate(normalized_input, spec.input_schema)
    if errors:
        result = ToolResult(
            status=ToolRunStatus.INVALID_INPUT,
            tool_name=tool_name,
            error="input non valido: " + "; ".join(errors),
            details={"schema_errors": errors},
        )
        _persist(session, project, tool_name, tool_input, result)
        return result

    # 4. Controllo scope.
    # La policy di scope autorizza i bersagli di RETE. I percorsi del
    # filesystem sono autorizzati dalla jail del tool (root del progetto o
    # root del laboratorio), verificata dall'handler: richiederebbe una
    # regola di scope per analizzare il proprio codice, che non ha senso.
    effective_target = target or _derive_target(spec, normalized_input)
    effective_technique = (
        technique
        or str(normalized_input.get("technique") or "")
        or spec.technique
    )
    scope_result = None
    if spec.requires_scope and effective_target and is_network_target(effective_target):
        scope_service = ScopeService(session)
        try:
            scope_result = scope_service.require_allowed(
                project, effective_target, effective_technique
            )
        except ScopeError as exc:
            result = ToolResult(
                status=ToolRunStatus.DENIED,
                tool_name=tool_name,
                error=str(exc.message),
                details={"target": effective_target, **exc.details},
            )
            _persist(session, project, tool_name, normalized_input, result)
            return result

    # 5. Conferma dell'operatore.
    needs_confirmation = spec.mutating or bool(
        scope_result and scope_result.requires_confirmation
    )
    if needs_confirmation and not confirm:
        result = ToolResult(
            status=ToolRunStatus.DENIED,
            tool_name=tool_name,
            error="operazione che richiede conferma esplicita dell'operatore",
            details={
                "requires_confirmation": True,
                "target": effective_target,
                "technique": effective_technique,
            },
        )
        _persist(session, project, tool_name, normalized_input, result)
        return result

    # 6. Esecuzione.
    context = ToolContext(
        project_id=project.id,
        project_root=project.root_path,
        mode=project.mode.value,
        timeout=spec.timeout_seconds,
        session=session,
        project=project,
    )
    started = time.perf_counter()
    try:
        output = registry.handler(tool_name)(normalized_input, context)
    except TimeoutError as exc:
        result = ToolResult(
            status=ToolRunStatus.TIMEOUT,
            tool_name=tool_name,
            error=f"timeout dopo {spec.timeout_seconds}s: {exc}",
        )
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        _persist(session, project, tool_name, normalized_input, result)
        return result
    except ScopeError as exc:
        # Il tool ha rilevato che il bersaglio non e' in scope: e' una
        # violazione di scope, non un errore tecnico.
        result = ToolResult(
            status=ToolRunStatus.DENIED,
            tool_name=tool_name,
            error=str(exc.message),
            details=exc.details,
        )
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        _persist(session, project, tool_name, normalized_input, result)
        return result
    except PermissionError as exc:
        # Percorso fuori dai confini consentiti: e' una violazione di scope,
        # non un errore tecnico del tool.
        result = ToolResult(
            status=ToolRunStatus.DENIED,
            tool_name=tool_name,
            error=str(exc),
        )
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        _persist(session, project, tool_name, normalized_input, result)
        return result
    except Exception as exc:  # noqa: BLE001 - il runner non propaga eccezioni grezze
        logger.warning(
            "tool_execution_failed",
            extra={"extra_fields": {"tool": tool_name, "error": str(exc)}},
        )
        result = ToolResult(
            status=ToolRunStatus.FAILED,
            tool_name=tool_name,
            error=f"{type(exc).__name__}: {exc}",
        )
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        _persist(session, project, tool_name, normalized_input, result)
        return result

    result = ToolResult(
        status=ToolRunStatus.SUCCESS,
        tool_name=tool_name,
        output=output,
        output_text=_serialize(output),
    )
    result.duration_ms = int((time.perf_counter() - started) * 1000)

    # 7. Validazione output.
    if spec.output_schema:
        output_errors = validate(output, spec.output_schema)
        if output_errors:
            result.status = ToolRunStatus.FAILED
            result.error = "output del tool non conforme allo schema: " + "; ".join(
                output_errors
            )

    _persist(session, project, tool_name, normalized_input, result)
    return result


def _persist(
    session: Session,
    project: Project,
    tool_name: str,
    tool_input: dict[str, Any],
    result: ToolResult,
) -> None:
    """Registra l'esecuzione in ``tool_runs`` (fonte autorevole per l'audit)."""
    safe_input = redact_mapping(tool_input or {})
    output_text = result.output_text or ""
    run = ToolRun(
        project_id=project.id,
        tool_name=tool_name,
        status=result.status,
        input_json=safe_input,
        output_text=output_text[:2_000_000],
        output_hash=sha256_text(output_text),
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        error_text=result.error[:4000],
    )
    session.add(run)
    session.flush()
    result.run_id = run.id
