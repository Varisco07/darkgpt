"""Test del tool HTTP: scope, conferma, budget ed esecuzione reale.

Le richieste di test vengono inviate a un server di prova locale avviato
dallo stesso test: nessun traffico verso la rete esterna.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.core.errors import ScopeError
from app.models.enums import ProjectMode, ToolRunStatus
from app.services.scope import ScopeService
from app.tools.builtin import HTTP_REQUEST_SPEC
from app.tools.http_client import build_request, perform_requests, validate_url
from app.tools.registry import registry
from app.tools.runner import run_tool


class _Handler(BaseHTTPRequestHandler):
    """Server di prova: risponde 200 con un corpo noto."""

    def do_GET(self) -> None:  # noqa: N802 - firma di BaseHTTPRequestHandler
        body = b"lab-ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:  # noqa: ANN002 - silenzia i log
        return


@pytest.fixture()
def local_server():
    """Server HTTP locale su una porta libera."""
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


@pytest.fixture()
def lab_project(session, project):
    """Progetto in modalita' LAB: il loopback e' ammesso."""
    project.mode = ProjectMode.LAB
    session.flush()
    return project


# ---------------------------------------------------------------------------
# Validazione della richiesta
# ---------------------------------------------------------------------------


def test_validate_url_rejects_non_http_scheme():
    with pytest.raises(ValueError):
        validate_url("file:///etc/passwd")


def test_validate_url_rejects_embedded_credentials():
    with pytest.raises(ValueError):
        validate_url("http://user:pass@example.com/")


def test_build_request_rejects_forbidden_method():
    with pytest.raises(ValueError):
        build_request("http://127.0.0.1:8000/", "DELETE")


def test_build_request_strips_forwarding_headers():
    request = build_request(
        "http://127.0.0.1:8000/",
        headers={"X-Forwarded-For": "1.2.3.4", "Accept": "text/plain"},
    )
    assert "X-Forwarded-For" not in request["headers"]
    assert request["headers"]["Accept"] == "text/plain"


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


def test_perform_requests_denies_host_outside_scope(session, project, local_server):
    """Una URL fuori scope blocca l'intera sequenza, senza partire."""
    with pytest.raises(ScopeError):
        perform_requests(
            [build_request(f"{local_server}/x")],
            session=session,
            project=project,
        )


def test_perform_requests_allows_loopback_in_lab_mode(session, lab_project, local_server):
    result = perform_requests(
        [build_request(f"{local_server}/ok")],
        session=session,
        project=lab_project,
    )
    assert result["requests_sent"] == 1
    assert result["results"][0]["status_code"] == 200
    assert result["results"][0]["body"] == "lab-ok"


def test_budget_is_enforced(session, lab_project, local_server):
    requests = [build_request(f"{local_server}/{index}") for index in range(4)]
    with pytest.raises(ValueError) as excinfo:
        perform_requests(
            requests,
            session=session,
            project=lab_project,
            max_requests=2,
        )
    assert "budget" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def test_http_tool_requires_confirmation(session, lab_project, local_server):
    """Senza conferma esplicita la richiesta non parte."""
    result = run_tool(
        session,
        lab_project,
        "http.request",
        {"requests": [{"url": f"{local_server}/ok"}]},
        confirm=False,
    )
    assert result.status is ToolRunStatus.DENIED
    assert result.details.get("requires_confirmation") is True


def test_http_tool_executes_with_confirmation(session, lab_project, local_server):
    result = run_tool(
        session,
        lab_project,
        "http.request",
        {"requests": [{"url": f"{local_server}/ok"}]},
        confirm=True,
    )
    assert result.status is ToolRunStatus.SUCCESS
    assert result.output["requests_sent"] == 1
    assert result.output["results"][0]["status_code"] == 200


def test_http_tool_denied_outside_scope(session, project, local_server):
    """In modalita' PASSIVE il loopback non e' ammesso."""
    result = run_tool(
        session,
        project,
        "http.request",
        {"requests": [{"url": f"{local_server}/ok"}]},
        confirm=True,
    )
    assert result.status is ToolRunStatus.DENIED


def test_http_tool_rejects_invalid_input(session, lab_project):
    result = run_tool(
        session,
        lab_project,
        "http.request",
        {"requests": []},
        confirm=True,
    )
    assert result.status is ToolRunStatus.INVALID_INPUT


def test_http_tool_is_registered_and_available():
    assert registry.has(HTTP_REQUEST_SPEC.name)
    assert registry.availability(HTTP_REQUEST_SPEC.name).status == "available"


def test_run_is_persisted_for_audit(session, lab_project, local_server):
    from sqlalchemy import select

    from app.models.tool_run import ToolRun

    run_tool(
        session,
        lab_project,
        "http.request",
        {"requests": [{"url": f"{local_server}/ok"}]},
        confirm=True,
    )
    session.flush()
    runs = session.scalars(select(ToolRun).where(ToolRun.tool_name == "http.request")).all()
    assert len(runs) == 1
    assert runs[0].status is ToolRunStatus.SUCCESS
    assert runs[0].output_hash


def test_scope_service_denies_external_host(session, project):
    """Il Scope Manager nega un host esterno anche se il progetto ha regole."""
    ScopeService(session).import_policy(project.id, "in scope: example.com")
    result = ScopeService(session).evaluate(project, "http://evil.example.org/")
    assert result.allowed is False
