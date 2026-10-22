"""Gerarchia di errori applicativi e mapping verso codici HTTP.

Le API non devono mai far trapelare traceback al cliente: ogni errore noto
diventa una risposta JSON strutturata con `code`, `message` e `details`.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base di tutti gli errori applicativi."""

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    """Stato non coerente con l'operazione richiesta (es. transizione finding)."""

    status_code = 409
    code = "conflict"


class ScopeError(AppError):
    """Operazione fuori dallo scope autorizzato."""

    status_code = 403
    code = "out_of_scope"


class ScopeRequiredError(ScopeError):
    """Manca una policy di scope valida per l'operazione richiesta."""

    status_code = 409
    code = "scope_required"


class ToolUnavailableError(AppError):
    """Il tool richiesto non e' installato o non e' utilizzabile."""

    status_code = 503
    code = "tool_unavailable"


class ToolExecutionError(AppError):
    """Il tool e' fallito durante l'esecuzione."""

    status_code = 500
    code = "tool_execution_failed"


class ConfirmationRequiredError(AppError):
    """L'operazione richiede conferma esplicita dell'operatore."""

    status_code = 428
    code = "confirmation_required"


class ProviderError(AppError):
    """Errore del provider LLM (rete, quota, formato risposta)."""

    status_code = 502
    code = "llm_provider_error"
