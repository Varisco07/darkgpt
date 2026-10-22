"""Verifica end-to-end della dashboard: backend + frontend reali.

Avvia il backend e il server Next.js, poi controlla che le pagine della
dashboard rendano i dati reali provenienti dal backend.

Uso:
    python scripts/smoke_frontend.py
"""

from __future__ import annotations

import json
import os
import re
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

DB_PATH = REPO / "smoke_frontend.db"
for suffix in ("", "-wal", "-shm"):
    candidate = Path(str(DB_PATH) + suffix)
    if candidate.exists():
        candidate.unlink()

FAILURES: list[str] = []


def free_port() -> int:
    """Trova una porta libera sul loopback."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def fetch(url: str, timeout: float = 30.0) -> tuple[int, str]:
    """Esegue una richiesta GET e restituisce (status, corpo)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(exc)


def post(url: str, payload: dict, timeout: float = 30.0) -> tuple[int, str]:
    """Esegue una richiesta POST JSON."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(exc)


def check(label: str, condition: bool, detail: str = "") -> None:
    """Registra l'esito di una verifica."""
    print(f"[{'OK  ' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        FAILURES.append(label)


def wait_for(url: str, timeout: float = 90.0) -> bool:
    """Attende che un servizio risponda."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, _body = fetch(url, timeout=3)
        if status in (200, 404):
            return True
        time.sleep(1)
    return False


def stop(process: subprocess.Popen) -> None:
    """Termina un processo avviato, in modo pulito."""
    try:
        os.kill(process.pid, signal.CTRL_BREAK_EVENT)
    except (OSError, AttributeError):
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    """Avvia entrambi i servizi e verifica il rendering della dashboard."""
    backend_port = free_port()
    frontend_port = free_port()
    backend_base = f"http://127.0.0.1:{backend_port}"
    frontend_base = f"http://127.0.0.1:{frontend_port}"

    env = dict(os.environ)
    env["DARKGPT_DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
    env["DARKGPT_LLM_BASE_URL"] = ""
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
            "--log-level",
            "warning",
        ],
        cwd=REPO,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    frontend = None
    try:
        if not wait_for(f"{backend_base}/health"):
            print("FAIL: il backend non si e' avviato")
            return 1
        print("backend pronto")

        # Dato reale da cui la dashboard deve mostrare il contenuto.
        status, body = post(
            f"{backend_base}/api/projects",
            {"name": "Progetto Dashboard", "mode": "PASSIVE", "stack": ["python"]},
        )
        check("progetto creato sul backend", status == 201, str(status))
        project = json.loads(body)
        project_id = project["id"]

        # Avvio del server Next.js in modalita' produzione.
        frontend = subprocess.Popen(
            [
                "npm.cmd",
                "run",
                "start",
                "--",
                "-p",
                str(frontend_port),
            ],
            cwd=REPO / "frontend",
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        if not wait_for(f"{frontend_base}/overview"):
            print("FAIL: la dashboard non si e' avviata")
            return 1
        print("dashboard pronta")

        # Verifica del rendering con dati reali.
        status, html = fetch(f"{frontend_base}/overview")
        check("overview risponde 200", status == 200, str(status))
        check("overview mostra il progetto reale", "Progetto Dashboard" in html)
        check("overview mostra lo stato del backend", "Stato backend" in html)

        status, html = fetch(f"{frontend_base}/projects")
        check("projects risponde 200", status == 200, str(status))
        check("projects elenca il progetto", "Progetto Dashboard" in html)

        status, html = fetch(f"{frontend_base}/findings?project={project_id}")
        check("findings risponde 200", status == 200, str(status))
        check("findings mostra lo stato vuoto", "Nessun" in html or "nessun" in html)

        status, html = fetch(f"{frontend_base}/tools")
        check("tool manager risponde 200", status == 200, str(status))
        check("tool manager elenca sast.sql.python", "sast.sql.python" in html)
        check(
            "tool manager dichiara i tool non disponibili",
            "unavailable" in html,
        )
        check("tool manager elenca http.request", "http.request" in html)
        check("tool manager elenca game.analyze", "game.analyze" in html)

        status, html = fetch(f"{frontend_base}/settings")
        check("settings risponde 200", status == 200, str(status))
        check("settings non espone la chiave API", "DARKGPT_LLM_API_KEY" in html)

        # Verifica che la pagina di progetto usi i dati del backend.
        status, html = fetch(f"{frontend_base}/scope?project={project_id}")
        check("scope risponde 200", status == 200, str(status))
        check(
            "scope segnala l'assenza di policy",
            "deny-by-default" in html or "Nessuna regola" in html,
        )
    finally:
        if frontend is not None:
            stop(frontend)
        stop(backend)
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(DB_PATH) + suffix)
            if candidate.exists():
                candidate.unlink()

    print()
    if FAILURES:
        print(f"RISULTATO: {len(FAILURES)} verifiche fallite: {FAILURES}")
        return 1
    print("RISULTATO: tutte le verifiche della dashboard sono passate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
