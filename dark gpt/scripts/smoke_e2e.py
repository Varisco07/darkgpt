"""Verifica end-to-end: avvia il backend, esercita il flusso reale, lo arresta.

Lo script esegue un percorso completo sull'API reale (non mock):
creazione progetto -> import scope -> scansione SAST -> creazione finding ->
conferma con evidenze -> generazione report -> verifica del report.

Uso:
    python scripts/smoke_e2e.py
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = REPO / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

#: Database temporaneo: lo smoke test non tocca il database dell'utente.
DB_PATH = REPO / "smoke_e2e.db"
for suffix in ("", "-wal", "-shm"):
    candidate = Path(str(DB_PATH) + suffix)
    if candidate.exists():
        candidate.unlink()

os.environ["DARKGPT_DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
os.environ["DARKGPT_LLM_BASE_URL"] = ""

FAILURES: list[str] = []


def free_port() -> int:
    """Trova una porta libera sul loopback."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def call(
    method: str,
    url: str,
    payload: dict | None = None,
    timeout: float = 30.0,
) -> tuple[int, object]:
    """Esegue una richiesta HTTP e restituisce (status, corpo decodificato)."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        status = exc.code
    try:
        return status, json.loads(body) if body else None
    except json.JSONDecodeError:
        return status, body


def check(label: str, condition: bool, detail: str = "") -> None:
    """Registra l'esito di una verifica."""
    print(f"[{'OK  ' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        FAILURES.append(label)


def run_flow(base: str) -> None:
    """Esegue il percorso completo sull'API reale."""
    # 1. Health
    status, health = call("GET", f"{base}/health")
    check("health risponde 200", status == 200, str(status))
    check(
        "database operativo",
        isinstance(health, dict) and health.get("database") == "ok",
    )

    # 2. Catalogo dei tool
    status, tools = call("GET", f"{base}/api/tools")
    names = {tool["name"] for tool in tools} if isinstance(tools, list) else set()
    check("catalogo dei tool popolato", "sast.sql.python" in names, ", ".join(sorted(names)))
    if isinstance(tools, list):
        unavailable = [t["name"] for t in tools if t["availability"] != "available"]
        print(f"       tool non disponibili (dichiarati): {unavailable or 'nessuno'}")

    # 3. Progetto
    status, project = call(
        "POST",
        f"{base}/api/projects",
        {
            "name": "Smoke test",
            "description": "verifica end-to-end",
            "mode": "PASSIVE",
            "stack": ["python"],
            "root_path": str(REPO / "lab" / "sqli_app"),
        },
    )
    check("creazione progetto", status == 201, str(status))
    project_id = project["id"] if isinstance(project, dict) else 0

    # 4. Scope
    status, policy = call(
        "POST",
        f"{base}/api/projects/{project_id}/scope/import",
        {"text": "in scope: 127.0.0.1\nin scope: localhost"},
    )
    check("import policy", status == 201, str(status))
    check(
        "asset derivati dalla policy",
        isinstance(policy, dict) and policy.get("asset_count", 0) >= 1,
        f"asset_count={policy.get('asset_count') if isinstance(policy, dict) else 'n/d'}",
    )

    status, check_result = call(
        "POST",
        f"{base}/api/projects/{project_id}/scope/check",
        {"target": "http://127.0.0.1:8100/search"},
    )
    check(
        "verifica target in scope",
        isinstance(check_result, dict) and check_result.get("decision") == "ALLOWED",
        str(check_result.get("decision") if isinstance(check_result, dict) else check_result),
    )

    # 5. Scansione SAST reale sul laboratorio
    status, scan = call(
        "POST",
        f"{base}/api/projects/{project_id}/scans",
        {
            "tool": "sast.sql.python",
            "input": {"path": str(REPO / "lab" / "sqli_app")},
        },
    )
    check("scansione eseguita", status == 200, str(status))
    scan_status = scan.get("status") if isinstance(scan, dict) else None
    check("scansione completata", scan_status == "SUCCESS", str(scan_status))
    detected = 0
    if isinstance(scan, dict) and isinstance(scan.get("output"), dict):
        detected = scan["output"].get("summary", {}).get("total", 0)
    check("SAST rileva il bersaglio vulnerabile", detected >= 3, f"{detected} finding")

    # 6. Tool run persistito
    status, runs = call("GET", f"{base}/api/projects/{project_id}/tool-runs")
    run_count = len(runs) if isinstance(runs, list) else 0
    check("esecuzione registrata in tool_runs", run_count >= 1, f"{run_count} run")
    if isinstance(runs, list) and runs:
        check("output della run ha un hash", bool(runs[0].get("output_hash")))

    # 7. Creazione finding e conferma
    status, finding = call(
        "POST",
        f"{base}/api/projects/{project_id}/findings",
        {
            "title": "SQL injection in /search",
            "category": "SQLi",
            "severity": "HIGH",
            "hypothesis": "Il termine di ricerca e' concatenato nella query SQL.",
        },
    )
    check("creazione finding", status == 201, str(status))
    finding_id = finding["id"] if isinstance(finding, dict) else 0
    check(
        "finding nasce POTENTIAL",
        isinstance(finding, dict) and finding.get("status") == "POTENTIAL",
    )

    status, _refused = call(
        "POST",
        f"{base}/api/projects/{project_id}/findings/{finding_id}/transition",
        {"status": "CONFIRMED", "reason": "senza evidenze"},
    )
    check("conferma senza evidenze rifiutata", status == 422, str(status))

    status, confirmed = call(
        "POST",
        f"{base}/api/projects/{project_id}/findings/{finding_id}/transition",
        {
            "status": "CONFIRMED",
            "reason": "payload riproducibile sul bersaglio di laboratorio",
            "evidence": [
                {
                    "kind": "HTTP_REQUEST",
                    "payload": "GET /search?q=%27%20OR%20%271%27=%271",
                    "observed": "5 righe invece di 1",
                    "source": "lab/sqli_app",
                }
            ],
        },
    )
    check(
        "conferma con evidenze accettata",
        status == 200
        and isinstance(confirmed, dict)
        and confirmed.get("status") == "CONFIRMED",
        str(status),
    )

    # 8. Report
    status, report = call(
        "POST", f"{base}/api/projects/{project_id}/reports?format=MARKDOWN"
    )
    check("generazione report", status == 201, str(status))
    content = report.get("content", "") if isinstance(report, dict) else ""
    check("report contiene il finding", "SQL injection in /search" in content)
    check("report dichiara i limiti", "Limiti dell'analisi" in content)

    # 9. Segreti non esposti
    status, settings = call("GET", f"{base}/api/settings/llm")
    check(
        "la chiave API non e' esposta",
        isinstance(settings, dict) and "api_key" not in settings,
    )

    # 10. Chat con provider non configurato
    status, message = call(
        "POST",
        f"{base}/api/projects/{project_id}/chat",
        {"message": "Analizza il finding #1", "role": "analysis"},
    )
    check(
        "chat risponde in modalita' dichiarata",
        status == 200 and isinstance(message, dict) and message.get("simulated") is True,
        str(status),
    )

    # 11. Tool HTTP: fuori scope -> negato
    status, http_out = call(
        "POST",
        f"{base}/api/projects/{project_id}/scans",
        {
            "tool": "http.request",
            "input": {"requests": [{"url": "http://example.org/"}]},
            "confirm": True,
        },
    )
    check(
        "tool HTTP negato fuori scope",
        isinstance(http_out, dict) and http_out.get("status") == "DENIED",
        str(http_out.get("status") if isinstance(http_out, dict) else http_out),
    )

    # 12. Tool HTTP: senza conferma -> negato
    status, http_unconfirmed = call(
        "POST",
        f"{base}/api/projects/{project_id}/scans",
        {
            "tool": "http.request",
            "input": {"requests": [{"url": "http://127.0.0.1:9/"}]},
            "confirm": False,
        },
    )
    check(
        "tool HTTP senza conferma negato",
        isinstance(http_unconfirmed, dict)
        and http_unconfirmed.get("status") == "DENIED",
        str(
            http_unconfirmed.get("status")
            if isinstance(http_unconfirmed, dict)
            else http_unconfirmed
        ),
    )

    # 13. Tool game: analisi statica di una cartella
    status, game = call(
        "POST",
        f"{base}/api/projects/{project_id}/scans",
        {
            "tool": "game.analyze",
            "input": {"path": str(REPO / "lab" / "sqli_app")},
        },
    )
    check(
        "tool game analizza la cartella",
        isinstance(game, dict) and game.get("status") == "SUCCESS",
        str(game.get("status") if isinstance(game, dict) else game),
    )
    check(
        "tool game dichiara il motore",
        isinstance(game, dict)
        and isinstance(game.get("output"), dict)
        and "engine" in game["output"],
    )


def main() -> int:
    """Avvia il backend, esegue il flusso e lo arresta."""
    port = free_port()
    base = f"http://127.0.0.1:{port}"

    process = subprocess.Popen(
        [
            str(PYTHON),
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            str(REPO / "backend"),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    try:
        ready = False
        for _ in range(60):
            try:
                status, _body = call("GET", f"{base}/health", timeout=2)
                if status == 200:
                    ready = True
                    break
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        if not ready:
            print("FAIL: il backend non si e' avviato")
            output = process.stdout.read() if process.stdout else ""
            print(output[-3000:])
            return 1

        run_flow(base)
    finally:
        try:
            os.kill(process.pid, signal.CTRL_BREAK_EVENT)
        except (OSError, AttributeError):
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(DB_PATH) + suffix)
            if candidate.exists():
                candidate.unlink()

    print()
    if FAILURES:
        print(f"RISULTATO: {len(FAILURES)} verifiche fallite: {FAILURES}")
        return 1
    print("RISULTATO: tutte le verifiche end-to-end sono passate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
