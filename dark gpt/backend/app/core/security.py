"""Funzioni di sicurezza: redazione dei segreti, hashing, normalizzazione target.

Nessuna di queste funzioni deve mai essere bypassata: sono usate da tutti i
punti in cui dati non attendibili (output di tool, contenuto di file, risposte
del provider) entrano nel sistema.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
from pathlib import Path
from urllib.parse import urlparse

# Pattern di segreti comuni. Ordine importante: piu specifico per primo.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # L'header Authorization va redatto per intero: il token si estende fino a
    # fine riga, non solo fino al primo spazio.
    (re.compile(r"(?i)\b(authorization)\s*[:=]\s*[^\r\n]+"), r"\1: [REDACTED]"),
    (re.compile(r"(?i)\b(api[_-]?key|apikey|access[_-]?token|secret[_-]?key)\b\s*[:=]\s*[^\r\n,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*[^\r\n,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\b(secret)\b\s*[:=]\s*[^\r\n,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED PRIVATE KEY]"),
    (re.compile(r"\b(sk-[A-Za-z0-9]{16,})\b"), "[REDACTED]"),
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{16,})\b"), "[REDACTED]"),
    (re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b"), "[REDACTED]"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._-]{16,}"), r"\1 [REDACTED]"),
)

# Chiavi i cui valori devono essere mascherati in strutture annidate.
SENSITIVE_KEYS = frozenset(
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
        "refresh_token",
        "private_key",
        "cookie",
        "set_cookie",
        "session",
    }
)

REDACTED = "[REDACTED]"


def redact(text: str | None) -> str:
    """Rimuove segreti da un testo libero.

    Usata su output di tool, contenuto di file, log e contesto LLM.
    """
    if not text:
        return ""
    result = text
    for pattern, replacement in _SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_mapping(data: object) -> object:
    """Applica :func:`redact` ricorsivamente a dict/list/str.

    I valori delle chiavi in :data:`SENSITIVE_KEYS` sono sempre mascherati,
    indipendentemente dal contenuto.
    """
    if isinstance(data, dict):
        out: dict[str, object] = {}
        for key, value in data.items():
            if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
                out[key] = REDACTED
            else:
                out[key] = redact_mapping(value)
        return out
    if isinstance(data, (list, tuple)):
        return [redact_mapping(item) for item in data]
    if isinstance(data, str):
        return redact(data)
    return data


def sha256_text(text: str) -> str:
    """SHA-256 esadecimale di un testo (per hash di output e file)."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha256_file(path: Path) -> str:
    """SHA-256 esadecimale del contenuto di un file, letto a blocchi."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


LOOPBACK_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def is_loopback_host(host: str) -> bool:
    """True se l'host e' loopback (localhost o indirizzo privato di loopback)."""
    if not host:
        return False
    hostname = host.strip().lower().strip("[]")
    if hostname in LOOPBACK_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def normalize_target(target: str) -> str:
    """Normalizza un target per il confronto con le regole di scope.

    - URL con schema: `https://Host/Path` -> `host/path` (host in minuscolo).
    - Host con percorso opzionale: `Host/Path` -> `host/path`.
    - Percorso del filesystem: risolto in forma assoluta.
    - Host semplice: minuscolo.

    La funzione e' idempotente: normalizzare un valore gia' normalizzato
    restituisce lo stesso risultato.
    """
    value = (target or "").strip()
    if not value:
        return ""
    if "://" in value:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        path = parsed.path or "/"
        while "//" in path:
            path = path.replace("//", "/")
        port = f":{parsed.port}" if parsed.port else ""
        return f"{host}{port}{path}"
    if "\\" in value or value.startswith(("/", "./", "../")):
        try:
            return Path(value).resolve().as_posix()
        except OSError:  # pragma: no cover - path non risolvibile
            return value
    # Host con eventuale porta e percorso.
    head, _, tail = value.partition("/")
    if _looks_like_host(head):
        host = head.lower()
        path = f"/{tail}" if tail else ""
        return f"{host}{path}"
    try:
        return Path(value).resolve().as_posix()
    except OSError:  # pragma: no cover
        return value


def _looks_like_host(segment: str) -> bool:
    """True se il segmento ha l'aspetto di un host (dominio, IP o host:porta)."""
    if not segment:
        return False
    if segment.startswith("["):  # IPv6 literal
        return "]" in segment
    host = segment.split(":", 1)[0]
    return "." in host or ":" in segment


def target_host(target: str) -> str:
    """Estrae l'host da un target normalizzato (stringa vuota se non applicabile)."""
    value = (target or "").strip()
    if "://" in value:
        return (urlparse(value).hostname or "").lower()
    if "\\" in value or value.startswith(("/", "./", "../")):
        return ""
    head = value.split("/", 1)[0]
    if not _looks_like_host(head):
        return ""
    if head.startswith("["):
        return head[1 : head.index("]")].lower()
    return head.split(":", 1)[0].lower()


def is_network_target(target: str) -> bool:
    """True se il target e' un bersaglio di rete (URL, dominio, host).

    I bersagli di rete sono autorizzati dalla **policy di scope** del
    progetto. I percorsi del filesystem sono autorizzati invece dalla
    *jail* del tool (root del progetto o root del laboratorio): non serve
    una regola di scope per analizzare il proprio codice.
    """
    value = (target or "").strip()
    if not value:
        return False
    if "://" in value:
        return True
    if "\\" in value or value.startswith(("/", "./", "../")):
        return False
    head = value.split("/", 1)[0]
    # Drive letter di Windows ("C:", "D:") = percorso, non host.
    if len(head) == 2 and head[1] == ":" and head[0].isalpha():
        return False
    return _looks_like_host(head)


def is_path_within(base: Path, candidate: Path) -> bool:
    """True se `candidate` e dentro `base` (prevenzione path traversal)."""
    try:
        base_resolved = base.resolve()
        candidate_resolved = candidate.resolve()
    except OSError:  # pragma: no cover
        return False
    try:
        candidate_resolved.relative_to(base_resolved)
        return True
    except ValueError:
        return False


def sanitize_text_for_display(text: str, max_length: int = 2000) -> str:
    """Rende un testo sicuro e limitato per la visualizzazione nella UI."""
    cleaned = redact(text)
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + f"\n...[truncated at {max_length} chars]"
    return cleaned
