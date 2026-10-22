"""Verifica di avvio a freddo: replica i comandi del README, da zero.

Fa esattamente quello che farebbe un utente che apre la cartella per la
prima volta:

1. rimuove il database (se presente) e verifica che venga ricreato;
2. avvia il backend con il comando documentato;
3. avvia la dashboard con `npm run dev` (modalita' sviluppo, non build);
4. percorre un flusso reale: progetto -> scope -> scansione -> finding ->
   report, e verifica che la dashboard mostri i dati.

Uso:
    python scripts/cold_start.py
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

DB_PATH = REPO / "darkgpt.db"
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """Registra l'esito di una verifica."""
    print(f"[{'OK  ' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        FAILURES.append(label)


def free_port() -> int:
    """Trova una porta libera sul loopback."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def get(url: str, timeout: float = 20.0) -> tuple[int, str]:
    """GET HTTP."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(exc)


def post(url: str, payload: dict | None = None, timeout: float = 30.0) -> tuple[int, object]:
    """POST JSON (payload opzionale)."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else b""
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(exc)


def wait_for(url: str, timeout: float = 120.0) -> bool:
    """Attende che un servizio risponda."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, _ = get(url, timeout=3)
        if status in (200, 404):
            return True
        time.sleep(1)
    return False


def stop(process: subprocess.Popen) -> None:
    """Termina un processo avviato."""
    try:
        os.kill(process.pid, signal.CTRL_BREAK_EVENT)
    except (OSError, AttributeError):
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    """Esegue l'avvio a freddo con i comandi documentati."""
    print("=== Stato iniziale ===")
    check(
        "virtualenv presente",
        (REPO / ".venv" / "Scripts" / "python.exe").exists(),
        str(REPO / ".venv"),
    )
    check(
        "dipendenze frontend presenti",
        (REPO / "frontend" / "node_modules" / "next").exists(),
    )

    # 1. Database assente: deve essere ricreato dal backend.
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(DB_PATH) + suffix)
        if candidate.exists():
            candidate.unlink()
    check("database rimosso (avvio a freddo)", not DB_PATH.exists())

    backend_port = free_port()
    frontend_port = free_port()
    backend_base = f"http://127.0.0.1:{backend_port}"
    frontend_base = f"http://127.0.0.1:{frontend_port}"

    env = dict(os.environ)
    env["DARKGPT_DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
    env.pop("DARKGPT_LLM_BASE_URL", None)
    env["DARKGPT_API_URL"] = backend_base

    backend = subprocess.Popen(
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
            str(backend_port),
        ],
        cwd=REPO,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    frontend = None
    try:
        # 2. Backend.
        if not wait_for(f"{backend_base}/health"):
            print("FAIL: il backend non si e' avviato")
            return 1
        print("backend avviato")
        check("database ricreato automaticamente", DB_PATH.exists(), str(DB_PATH.name))

        status, health = get(f"{backend_base}/health")
        check("health risponde 200", status == 200, str(status))
        payload = json.loads(health)
        check("database operativo", payload.get("database") == "ok")
        check("nessun provider LLM: fallback dichiarato", payload.get("llm_provider") == "mock")

        # 3. Flusso reale completo.
        status, project = post(
            f"{backend_base}/api/projects",
            {
                "name": "Avvio a freddo",
                "mode": "PASSIVE",
                "root_path": str(REPO / "lab" / "sqli_app"),
            },
        )
        check("progetto creato", status == 201, str(status))
        project_id = project["id"]

        status, _policy = post(
            f"{backend_base}/api/projects/{project_id}/scope/import",
            {"text": "in scope: 127.0.0.1\nin scope: localhost"},
        )
        check("scope importato", status == 201, str(status))

        status, scan = post(
            f"{backend_base}/api/projects/{project_id}/scans",
            {
                "tool": "sast.sql.python",
                "input": {"path": str(REPO / "lab" / "sqli_app")},
            },
        )
        check(
            "scansione completata",
            isinstance(scan, dict) and scan.get("status") == "SUCCESS",
            str(scan.get("status") if isinstance(scan, dict) else scan),
        )

        status, finding = post(
            f"{backend_base}/api/projects/{project_id}/findings",
            {"title": "Finding di avvio", "severity": "HIGH"},
        )
        check("finding creato", status == 201, str(status))

        status, report = post(
            f"{backend_base}/api/projects/{project_id}/reports?format=MARKDOWN"
        )
        check(
            "report generato",
            status == 201 and "Finding di avvio" in report.get("content", ""),
            str(status),
        )

        # 4. Dashboard in modalita' sviluppo.
        frontend = subprocess.Popen(
            ["npm.cmd", "run", "dev", "--", "-p", str(frontend_port)],
            cwd=REPO / "frontend",
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        if not wait_for(f"{frontend_base}/overview", timeout=180):
            print("FAIL: la dashboard non si e' avviata")
            return 1
        print("dashboard avviata (npm run dev)")

        status, html = get(f"{frontend_base}/overview")
        check("overview risponde 200", status == 200, str(status))
        check("la dashboard mostra il progetto reale", "Avvio a freddo" in html)
        check("la dashboard mostra i tool", "sast.sql.python" in html)

        status, html = get(f"{frontend_base}/findings?project={project_id}")
        check("findings mostra il finding reale", "Finding di avvio" in html)

        status, html = get(f"{frontend_base}/scanner?project={project_id}")
        check("scanner mostra l'input JSON avanzato", "JSON avanzato" in html)
    finally:
        if frontend is not None:
            stop(frontend)
        stop(backend)

    print()
    if FAILURES:
        print(f"RISULTATO: {len(FAILURES)} verifiche fallite: {FAILURES}")
        return 1
    print("RISULTATO: avvio a freddo completato, tutto funziona")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
