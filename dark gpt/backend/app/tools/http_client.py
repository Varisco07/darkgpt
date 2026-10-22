"""Client HTTP per test autorizzati.

Non e' un proxy e non tenta di mascherarsi: le richieste sono esplicite,
limitate nel numero e soggette al controllo di scope. Il rischio di
enumerazione e' gestito dal budget di richieste per run.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import httpx

from ..core.config import get_settings
from ..core.errors import ScopeError
from ..core.security import redact
from ..core.security import is_loopback_host

#: Metodi HTTP consentiti al tool di test.
ALLOWED_METHODS = frozenset({"GET", "HEAD", "POST", "OPTIONS"})

#: Header non consentiti (evitano l'uso come proxy o il fingerprinting).
FORBIDDEN_HEADERS = frozenset({"host", "proxy-authorization", "x-forwarded-for"})


def validate_url(url: str) -> str:
    """Valida la URL: schema http/https e assenza di credenziali embedded."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"schema non consentito: {parsed.scheme!r} (usare http o https)")
    if not parsed.hostname:
        raise ValueError("URL priva di host")
    if parsed.username or parsed.password:
        raise ValueError("credenziali non ammesse nella URL")
    return url


def build_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    """Costruisce la descrizione di una richiesta HTTP, validando i parametri."""
    method = method.upper()
    if method not in ALLOWED_METHODS:
        raise ValueError(
            f"metodo non consentito: {method}. Ammessi: {sorted(ALLOWED_METHODS)}"
        )
    validate_url(url)
    clean_headers: dict[str, str] = {}
    for key, value in (headers or {}).items():
        lowered = key.lower()
        if lowered in FORBIDDEN_HEADERS:
            continue
        clean_headers[key] = str(value)
    return {
        "method": method,
        "url": url,
        "headers": clean_headers,
        "body": body,
    }


def perform_request(
    request: dict[str, Any],
    *,
    timeout: float | None = None,
    max_bytes: int = 500_000,
) -> dict[str, Any]:
    """Esegue una richiesta HTTP e restituisce una descrizione strutturata.

    Non solleva eccezioni di rete: gli errori di trasporto sono riportati
    nel campo `error`, cosi' l'operatore vede cosa e' realmente successo.
    """
    settings = get_settings()
    timeout = timeout if timeout is not None else settings.http_timeout
    started = time.perf_counter()
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            verify=True,
            trust_env=False,
        ) as client:
            response = client.request(
                request["method"],
                request["url"],
                headers=request.get("headers") or {},
                content=request.get("body"),
            )
    except httpx.HTTPError as exc:
        return {
            "method": request["method"],
            "url": request["url"],
            "error": f"{type(exc).__name__}: {exc}",
            "status_code": None,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

    body_text = response.text[:max_bytes]
    return {
        "method": request["method"],
        "url": request["url"],
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": redact(body_text),
        "body_truncated": len(response.text) > max_bytes,
        "content_length": len(response.content),
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }


def require_loopback_or_scope(url: str, allowed_hosts: set[str]) -> None:
    """Verifica che l'host sia in scope o sia loopback.

    Usata come difesa in profondita' dal client HTTP: anche se il controllo di
    scope del progetto fallisce, la richiesta non esce verso la rete.
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        raise ScopeError("URL priva di host")
    if is_loopback_host(host):
        return
    if host in allowed_hosts:
        return
    raise ScopeError(
        f"host '{host}' non e' in scope",
        details={"host": host, "allowed": sorted(allowed_hosts)},
    )


def check_scope_for_url(
    session: Any,
    project: Any,
    url: str,
    technique: str = "active_testing",
) -> dict[str, Any]:
    """Verifica lo scope di una singola URL usando il Scope Manager.

    Solleva :class:`ScopeError` se il bersaglio non e' ammesso. La decisione
    e' sempre deny-by-default: senza regole ALLOW la richiesta non parte.
    """
    from ..services.scope import ScopeService

    if session is None or project is None:
        raise ScopeError(
            "nessun progetto associato: impossibile verificare lo scope",
            details={"url": url},
        )
    result = ScopeService(session).require_allowed(project, url, technique)
    return {
        "decision": result.decision.value,
        "reason": result.reason,
        "matched_pattern": result.matched_pattern,
        "requires_confirmation": result.requires_confirmation,
    }


def perform_requests(
    requests: list[dict[str, Any]],
    *,
    session: Any = None,
    project: Any = None,
    timeout: float | None = None,
    max_bytes: int = 500_000,
    max_requests: int | None = None,
    technique: str = "active_testing",
) -> dict[str, Any]:
    """Esegue una sequenza di richieste HTTP, verificando lo scope per ognuna.

    Ogni richiesta e' controllata **prima** di partire: se una sola URL non e'
    in scope, l'intera sequenza si ferma e l'errore viene propagato.

    Il numero di richieste e' limitato dal budget (`max_requests`): il
    limite serve a contenere il rischio di enumerazione.
    """
    settings = get_settings()
    limit = max_requests if max_requests is not None else settings.http_max_requests_per_run
    if len(requests) > limit:
        raise ValueError(
            f"budget superato: {len(requests)} richieste richieste, massimo {limit}"
        )

    results: list[dict[str, Any]] = []
    for request in requests:
        scope_info = check_scope_for_url(session, project, request["url"], technique)
        outcome = perform_request(request, timeout=timeout, max_bytes=max_bytes)
        outcome["scope"] = scope_info
        results.append(outcome)

    return {
        "requests_sent": len(results),
        "budget": limit,
        "results": results,
    }
