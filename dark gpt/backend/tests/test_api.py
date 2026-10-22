"""Test dell'API REST: progetti, scope, finding, tool, report."""

from __future__ import annotations

from app.models.enums import ProjectMode


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["tools_total"] >= 1


def test_create_and_list_projects(client):
    response = client.post(
        "/api/projects",
        json={"name": "Progetto API", "description": "creato via test"},
    )
    assert response.status_code == 201
    project = response.json()
    assert project["name"] == "Progetto API"
    assert project["mode"] == ProjectMode.PASSIVE.value

    listing = client.get("/api/projects")
    assert listing.status_code == 200
    assert any(item["id"] == project["id"] for item in listing.json())


def test_create_project_rejects_unknown_field(client):
    response = client.post(
        "/api/projects", json={"name": "X", "campo_inesistente": 1}
    )
    assert response.status_code == 422


def test_get_missing_project_returns_404(client):
    response = client.get("/api/projects/9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_upgrade_to_authorized_requires_scope(client):
    project = client.post("/api/projects", json={"name": "Senza scope"}).json()

    response = client.patch(
        f"/api/projects/{project['id']}/mode",
        json={"mode": "AUTHORIZED_ASSESSMENT"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "scope_required"


def test_upgrade_to_authorized_after_scope_import(client):
    project = client.post("/api/projects", json={"name": "Con scope"}).json()
    client.post(
        f"/api/projects/{project['id']}/scope/import",
        json={"text": "in scope: example.com"},
    )

    response = client.patch(
        f"/api/projects/{project['id']}/mode",
        json={"mode": "AUTHORIZED_ASSESSMENT"},
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "AUTHORIZED_ASSESSMENT"


def test_scope_import_and_check(client):
    project = client.post("/api/projects", json={"name": "Scope"}).json()
    policy = client.post(
        f"/api/projects/{project['id']}/scope/import",
        json={"text": "in scope: example.com\nout of scope: admin.example.com"},
    )
    assert policy.status_code == 201
    assert policy.json()["asset_count"] == 1

    allowed = client.post(
        f"/api/projects/{project['id']}/scope/check",
        json={"target": "example.com"},
    )
    assert allowed.json()["decision"] == "ALLOWED"

    denied = client.post(
        f"/api/projects/{project['id']}/scope/check",
        json={"target": "admin.example.com"},
    )
    assert denied.json()["decision"] == "DENIED"


def test_finding_lifecycle_through_api(client):
    project = client.post("/api/projects", json={"name": "Findings"}).json()
    created = client.post(
        f"/api/projects/{project['id']}/findings",
        json={"title": "SQL injection", "category": "SQLi", "severity": "HIGH"},
    )
    assert created.status_code == 201
    finding = created.json()
    assert finding["status"] == "POTENTIAL"

    # La conferma senza evidenze deve fallire.
    invalid = client.post(
        f"/api/projects/{project['id']}/findings/{finding['id']}/transition",
        json={"status": "CONFIRMED", "reason": "tentativo senza prove"},
    )
    assert invalid.status_code == 422

    confirmed = client.post(
        f"/api/projects/{project['id']}/findings/{finding['id']}/transition",
        json={
            "status": "CONFIRMED",
            "reason": "payload riproducibile in laboratorio",
            "evidence": [
                {
                    "kind": "HTTP_REQUEST",
                    "payload": "GET /search?q=1' OR '1'='1",
                    "observed": "12 righe restituite",
                }
            ],
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"
    assert len(confirmed.json()["evidences"]) == 1


def test_finding_transition_not_allowed_returns_409(client):
    project = client.post("/api/projects", json={"name": "Transizioni"}).json()
    finding = client.post(
        f"/api/projects/{project['id']}/findings", json={"title": "Da confermare"}
    ).json()

    response = client.post(
        f"/api/projects/{project['id']}/findings/{finding['id']}/transition",
        json={"status": "FIXED", "reason": "salto non consentito"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_tools_catalog_lists_availability(client):
    response = client.get("/api/tools")
    assert response.status_code == 200
    tools = response.json()
    names = {item["name"] for item in tools}
    assert "sast.sql.python" in names
    for item in tools:
        assert item["availability"] in ("available", "unavailable", "degraded")


def test_unknown_tool_returns_404(client):
    response = client.get("/api/tools/strumento.inesistente")
    assert response.status_code == 404


def test_scan_outside_scope_is_denied(client):
    """Una scansione su un percorso fuori dai confini viene negata."""
    project = client.post("/api/projects", json={"name": "Scan"}).json()
    response = client.post(
        f"/api/projects/{project['id']}/scans",
        json={"tool": "sast.sql.python", "input": {"path": "."}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "DENIED"


def test_report_generation(client):
    project = client.post("/api/projects", json={"name": "Report"}).json()
    client.post(
        f"/api/projects/{project['id']}/findings",
        json={"title": "Finding da report", "severity": "MEDIUM"},
    )
    response = client.post(
        f"/api/projects/{project['id']}/reports", params={"format": "MARKDOWN"}
    )
    assert response.status_code == 201
    content = response.json()["content"]
    assert "Finding da report" in content
    assert "Limiti dell'analisi" in content


def test_settings_do_not_expose_api_key(client):
    response = client.get("/api/settings/llm")
    assert response.status_code == 200
    body = response.json()
    assert "api_key" not in body
    assert body["api_key_set"] is False
