"""Logging strutturato JSON + buffer in memoria per la UI.

Un unico logger `darkgpt` emette record JSON su stderr. Gli stessi record
alimentano un buffer circolare in memoria consumato dall'endpoint /api/logs:
il buffer NON e' un archivio di audit (i `tool_runs` in database lo sono).
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

LOGGER_NAME = "darkgpt"
_BUFFER_SIZE = 500

# Chiavi i cui valori non devono mai finire in un log.
_SENSITIVE = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_token",
        "private_key",
        "cookie",
    }
)


class JsonFormatter(logging.Formatter):
    """Formatta i record di log come JSON su una singola riga."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key.lower() in _SENSITIVE:
                    payload[key] = "[REDACTED]"
                else:
                    payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class MemoryLogHandler(logging.Handler):
    """Mantiene gli ultimi N record in memoria per la UI."""

    def __init__(self, maxlen: int = _BUFFER_SIZE) -> None:
        super().__init__()
        self.records: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            entry: dict[str, Any] = {
                "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "event": message,
                "logger": record.name,
            }
            extra = getattr(record, "extra_fields", None)
            if isinstance(extra, dict):
                for key, value in extra.items():
                    entry[key] = "[REDACTED]" if key.lower() in _SENSITIVE else value
            with self._lock:
                self.records.append(entry)
        except Exception:  # pragma: no cover - il logging non deve mai crashare
            pass


memory_handler = MemoryLogHandler()


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Restituisce il logger strutturato dell'applicazione."""
    return logging.getLogger(name if name.startswith(LOGGER_NAME) else f"{LOGGER_NAME}.{name}")


def setup_logging(level: int = logging.INFO) -> None:
    """Configura il logging JSON. Idempotente."""
    root = logging.getLogger(LOGGER_NAME)
    root.setLevel(level)
    root.propagate = False
    for handler in list(root.handlers):
        root.removeHandler(handler)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(JsonFormatter())
    root.addHandler(stream_handler)
    root.addHandler(memory_handler)


def recent_logs(limit: int = 100) -> list[dict[str, Any]]:
    """Ultimi record di log, dal piu recente al meno recente."""
    with memory_handler._lock:  # noqa: SLF001 - accesso intenzionale al buffer
        entries = list(memory_handler.records)
    return list(reversed(entries[-limit:]))


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Log strutturato con campi extra."""
    logger.log(level, event, extra={"extra_fields": fields})
