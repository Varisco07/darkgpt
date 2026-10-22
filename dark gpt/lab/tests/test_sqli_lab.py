"""Test del laboratorio SQL injection.

Verificano tre cose:
1. il bersaglio vulnerabile e' effettivamente iniettabile (in locale);
2. la versione corretta non lo e', a parita' di input legittimo;
3. l'analizzatore statico di DarkGPT segnala il codice vulnerabile e NON
   segnala quello corretto: e' il test di regressione della correzione.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
for path in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.tools.sast_sql import analyze_source  # noqa: E402
from lab.sqli_app import fixed, vulnerable  # noqa: E402

#: Payload iniettivo: chiude la stringa e rende la condizione sempre vera.
INJECTION_PAYLOAD = "' OR '1'='1"


@pytest.fixture()
def vulnerable_client():
    """Client HTTP del bersaglio vulnerabile."""
    with TestClient(vulnerable.app) as client:
        yield client


@pytest.fixture()
def fixed_client():
    """Client HTTP della versione corretta."""
    with TestClient(fixed.app) as client:
        yield client


# ---------------------------------------------------------------------------
# 1. Il bersaglio e' vulnerabile
# ---------------------------------------------------------------------------


def test_vulnerable_search_leaks_all_rows(vulnerable_client):
    """Con il payload iniettivo il filtro LIKE viene annullato."""
    baseline = vulnerable_client.get("/search", params={"q": "alice"}).json()
    assert baseline["count"] == 1

    injected = vulnerable_client.get(
        "/search", params={"q": INJECTION_PAYLOAD}
    ).json()

    assert injected["count"] == 5
    assert len(injected["rows"]) == 5
    assert INJECTION_PAYLOAD in injected["query"]


def test_vulnerable_item_accepts_non_numeric_input(vulnerable_client):
    """L'endpoint numerico accetta input non numerico: e' il sintomo del difetto."""
    response = vulnerable_client.get("/item", params={"id": "1 OR 1=1"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 5


def test_vulnerable_item_leaks_sql_errors(vulnerable_client):
    """Sintomo ulteriore: l'errore di SQL viene propagato al cliente.

    La concatenazione non validata trasforma l'input in un errore di sintassi
    che espone dettagli interni (il messaggio del driver SQLite). E' una
    disclosure di informazioni distinta dal bypass del filtro.
    """
    import sqlite3

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        vulnerable_client.get("/item", params={"id": "abc"})

    assert "no such column" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 2. La versione corretta non e' vulnerabile
# ---------------------------------------------------------------------------


def test_fixed_search_is_not_injectable(fixed_client):
    """La versione corretta restituisce zero righe per il payload."""
    baseline = fixed_client.get("/search", params={"q": "alice"}).json()
    assert baseline["count"] == 1

    injected = fixed_client.get("/search", params={"q": INJECTION_PAYLOAD}).json()
    assert injected["count"] == 0
    assert injected["rows"] == []


def test_fixed_search_behaves_identically_for_legitimate_input(fixed_client):
    """Il comportamento per l'input legittimo coincide con quello del bersaglio."""
    response = fixed_client.get("/search", params={"q": "ali"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["rows"][0]["name"] == "alice"


def test_fixed_item_rejects_non_numeric_input(fixed_client):
    """L'input non numerico e' rifiutato dalla validazione del tipo."""
    response = fixed_client.get("/item", params={"id": "1 OR 1=1"})
    assert response.status_code == 422


def test_fixed_item_returns_single_row(fixed_client):
    response = fixed_client.get("/item", params={"id": "2"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["rows"][0]["name"] == "bob"


def test_fixed_report_rejects_unknown_order_field(fixed_client):
    """L'ordinamento proviene da una lista chiusa."""
    response = fixed_client.get("/report", params={"name": "id; DROP TABLE orders"})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# 3. Test di regressione dell'analizzatore statico
# ---------------------------------------------------------------------------


def test_sast_flags_the_vulnerable_module():
    source = (REPO_ROOT / "lab" / "sqli_app" / "vulnerable.py").read_text(encoding="utf-8")
    findings = analyze_source("vulnerable.py", source)

    assert len(findings) >= 3
    functions = {finding.function for finding in findings}
    assert {"search", "item", "report"}.issubset(functions)
    assert all(finding.cwe == "CWE-89" for finding in findings)


def test_sast_does_not_flag_the_fixed_module():
    """Regressione: la correzione non deve piu' generare notifiche."""
    source = (REPO_ROOT / "lab" / "sqli_app" / "fixed.py").read_text(encoding="utf-8")
    findings = analyze_source("fixed.py", source)

    assert findings == []


def test_sast_scan_of_lab_reports_only_vulnerable_file():
    """La scansione della directory del laboratorio segnala solo il bersaglio."""
    from app.tools.sast_sql import scan_path

    report = scan_path(REPO_ROOT / "lab" / "sqli_app")
    flagged_files = {finding["file"] for finding in report["findings"]}

    assert "vulnerable.py" in flagged_files
    assert "fixed.py" not in flagged_files
    assert "db.py" not in flagged_files
