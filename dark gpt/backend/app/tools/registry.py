"""Registro dei tool: specifica, disponibilita' reale e lookup.

Un tool che non e' installato viene dichiarato `unavailable` con il motivo e
il comando di installazione. Non viene mai simulato alcun output.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from ..core.errors import NotFoundError
from ..core.logging import get_logger

logger = get_logger("tools")

#: Stati di disponibilita' di un tool.
AVAILABLE = "available"
UNAVAILABLE = "unavailable"
DEGRADED = "degraded"


@dataclass(frozen=True)
class ToolSpec:
    """Specifica dichiarativa di un tool."""

    name: str
    category: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] = field(default_factory=dict)
    requires_scope: bool = False
    mutating: bool = False
    timeout_seconds: int = 120
    technique: str = ""
    install_hint: str = ""
    #: Eseguito in-process (Python puro) invece che come subprocess.
    in_process: bool = False
    #: Esposto al provider LLM come tool chiamabile.
    #: I tool attivi restano esclusi: sono sotto il controllo dell'operatore.
    model_callable: bool = True


@dataclass(frozen=True)
class Availability:
    """Esito della verifica di disponibilita' di un tool."""

    status: str
    reason: str = ""
    version: str = ""

    @property
    def available(self) -> bool:
        return self.status == AVAILABLE


def probe_binary(binary: str, version_args: list[str] | None = None) -> Availability:
    """Verifica se un binario e' presente nel PATH e ne' rileva la versione.

    Non simula: se il binario non esiste, lo dichiara.
    """
    path = shutil.which(binary)
    if path is None:
        return Availability(
            status=UNAVAILABLE,
            reason=f"binario '{binary}' non trovato nel PATH",
        )
    version = ""
    if version_args:
        try:
            completed = subprocess.run(  # noqa: S603 - argv statico, shell=False
                [binary, *version_args],
                capture_output=True,
                text=True,
                timeout=15,
                shell=False,
            )
            output = (completed.stdout or completed.stderr or "").strip()
            version = output.splitlines()[0][:200] if output else ""
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("tool_version_probe_failed", extra={"extra_fields": {"binary": binary, "error": str(exc)}})
            return Availability(
                status=DEGRADED,
                reason=f"binario presente ma non interrogabile: {exc}",
                version="",
            )
    return Availability(status=AVAILABLE, reason="binario disponibile", version=version)


class ToolRegistry:
    """Registro globale dei tool con i relativi handler."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Callable[[dict[str, Any], "ToolContext"], Any]] = {}
        self._availability: dict[str, Availability] = {}

    def register(
        self,
        spec: ToolSpec,
        handler: Callable[[dict[str, Any], "ToolContext"], Any],
    ) -> None:
        """Registra un tool e il suo handler.

        La registrazione e' idempotente: ricaricare l'applicazione non deve
        sollevare un errore per un tool gia' presente.
        """
        if spec.name in self._specs:
            # Il tool esiste gia': si aggiorna solo l'handler.
            self._handlers[spec.name] = handler
            return
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler

    def has(self, name: str) -> bool:
        """True se il tool e' gia' registrato."""
        return name in self._specs

    def get(self, name: str) -> ToolSpec:
        """Restituisce la specifica di un tool. Solleva 404 se non esiste."""
        spec = self._specs.get(name)
        if spec is None:
            raise NotFoundError(
                f"tool sconosciuto: {name}",
                details={"available": sorted(self._specs)},
            )
        return spec

    def handler(self, name: str) -> Callable[[dict[str, Any], "ToolContext"], Any]:
        """Restituisce l'handler di un tool."""
        self.get(name)
        return self._handlers[name]

    def list(self) -> list[ToolSpec]:
        """Elenco delle specifiche registrate."""
        return sorted(self._specs.values(), key=lambda s: s.name)

    def set_availability(self, name: str, availability: Availability) -> None:
        """Registra l'esito della verifica di disponibilita'."""
        self._availability[name] = availability

    def availability(self, name: str) -> Availability:
        """Disponibilita' nota di un tool (default: unknown -> unavailable)."""
        return self._availability.get(name, Availability(status=UNAVAILABLE, reason="non verificato"))

    def describe(self) -> list[dict[str, Any]]:
        """Descrizione completa dei tool per la UI (Tool Manager)."""
        described: list[dict[str, Any]] = []
        for spec in self.list():
            availability = self.availability(spec.name)
            described.append(
                {
                    "name": spec.name,
                    "category": spec.category,
                    "description": spec.description,
                    "input_schema": spec.input_schema,
                    "requires_scope": spec.requires_scope,
                    "mutating": spec.mutating,
                    "timeout_seconds": spec.timeout_seconds,
                    "technique": spec.technique,
                    "install_hint": spec.install_hint,
                    "in_process": spec.in_process,
                    "availability": availability.status,
                    "availability_reason": availability.reason,
                    "version": availability.version,
                }
            )
        return described


class ToolContext:
    """Contesto passato agli handler dei tool.

    Include la sessione del database e il progetto corrente: un handler che
    ha bisogno di verificare lo scope (o di registrare dati) puo' farlo
    senza dipendere da moduli globali.
    """

    def __init__(
        self,
        project_id: int,
        project_root: str,
        mode: str,
        timeout: int = 120,
        session: Any = None,
        project: Any = None,
    ) -> None:
        self.project_id = project_id
        self.project_root = project_root
        self.mode = mode
        self.timeout = timeout
        #: Sessione SQLAlchemy della richiesta (None per esecuzioni isolate).
        self.session = session
        #: Progetto corrente (None per esecuzioni isolate).
        self.project = project


registry = ToolRegistry()
