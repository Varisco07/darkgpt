"""Tool concreti registrati nel registry.

Ogni tool dichiara la propria realta' di disponibilita'. I tool che dipendono
da un binario esterno vengono marcati `unavailable` se il binario non esiste:
il backend dichiara cosa manca, non simula un risultato.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..core.config import get_settings
from .registry import Availability, ToolContext, ToolSpec, registry
from .sast_sql import scan_path

#: Radice del repository: serve al modulo game, che vive fuori da `backend/`.
REPO_ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Tool in-process: analisi statica SQL
# ---------------------------------------------------------------------------

SAST_SQL_SPEC = ToolSpec(
    name="sast.sql.python",
    category="sast",
    description=(
        "Analisi statica del codice Python per individuare query SQL costruite "
        "tramite interpolazione (f-string, %, .format, concatenazione)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Percorso della directory o del file da analizzare. "
                    "Deve essere interno alla root del progetto o al laboratorio."
                ),
                "minLength": 1,
                "maxLength": 1024,
            },
            "max_files": {
                "type": "integer",
                "description": "Numero massimo di file da analizzare.",
                "minimum": 1,
                "maximum": 20000,
                "default": 2000,
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "root": {"type": "string"},
            "files_scanned": {"type": "integer"},
            "files": {"type": "array", "items": {"type": "string"}},
            "findings": {"type": "array"},
            "skipped": {"type": "array"},
            "summary": {"type": "object"},
        },
        "required": ["root", "files_scanned", "findings", "summary"],
    },
    requires_scope=True,
    mutating=False,
    timeout_seconds=300,
    technique="static_analysis",
    install_hint="Non richiede installazione: e' implementato nativamente in Python.",
    in_process=True,
)


def _resolve_target(path: str, context: ToolContext) -> Path:
    """Risolve il percorso e verifica che resti dentro i confini consentiti.

    I confini sono: la root del progetto e la root del laboratorio. Un
    percorso che esce da entrambi e' rifiutato (path traversal).
    """
    settings = get_settings()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(context.project_root) / candidate

    resolved = candidate.resolve()
    project_root = Path(context.project_root).resolve() if context.project_root else None
    lab_root = settings.lab_root.resolve()

    for allowed_root in (project_root, lab_root):
        if allowed_root is None:
            continue
        try:
            resolved.relative_to(allowed_root)
            return resolved
        except ValueError:
            continue

    raise PermissionError(
        f"percorso fuori dai confini consentiti: {resolved}. "
        f"Consentiti: {project_root} oppure {lab_root}"
    )


def sast_sql_handler(tool_input: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Handler del tool di analisi statica SQL."""
    settings = get_settings()
    target = _resolve_target(tool_input["path"], context)
    return scan_path(
        target,
        max_files=int(tool_input.get("max_files", settings.scan_max_files)),
        max_file_bytes=settings.scan_max_file_bytes,
    )


# ---------------------------------------------------------------------------
# Tool esterni opzionali
# ---------------------------------------------------------------------------

BANDIT_SPEC = ToolSpec(
    name="sast.bandit",
    category="sast",
    description="SAST Python con Bandit (dipendenze esterne, regole mature).",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "minLength": 1, "maxLength": 1024},
            "format": {"type": "string", "enum": ["json", "txt"], "default": "json"},
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    output_schema={"type": "object"},
    requires_scope=True,
    mutating=False,
    timeout_seconds=300,
    technique="static_analysis",
    install_hint="pip install bandit",
)

PIP_AUDIT_SPEC = ToolSpec(
    name="sca.pip_audit",
    category="sca",
    description="Analisi delle dipendenze Python per vulnerabilita' note (SCA).",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "minLength": 1, "maxLength": 1024},
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    output_schema={"type": "object"},
    requires_scope=False,
    mutating=False,
    timeout_seconds=300,
    technique="dependency_analysis",
    install_hint="pip install pip-audit",
)

GIT_SPEC = ToolSpec(
    name="scm.git",
    category="scm",
    description=(
        "Analisi del repository Git locale: log, branch remoti e file tracciati. "
        "Operazione di sola lettura."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "minLength": 1, "maxLength": 1024},
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Sottocomando git da eseguire (log, remote, ls-files).",
                "default": ["log", "--oneline", "-n", "50"],
                "maxItems": 10,
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    output_schema={"type": "object"},
    requires_scope=True,
    mutating=False,
    timeout_seconds=60,
    technique="repository_analysis",
    install_hint="Installa Git per Windows: https://git-scm.com/download/win",
)

#: Sottocomandi git consentiti: solo lettura, nessuna modifica allo storico.
ALLOWED_GIT_SUBCOMMANDS = frozenset(
    {"log", "remote", "ls-files", "status", "branch", "show", "diff", "rev-parse", "shortlog"}
)


# ---------------------------------------------------------------------------
# Tool HTTP: richieste attive verso bersagli in scope
# ---------------------------------------------------------------------------

#: Metodi HTTP consentiti al tool.
ALLOWED_HTTP_METHODS = ("GET", "HEAD", "POST", "OPTIONS")

HTTP_REQUEST_SPEC = ToolSpec(
    name="http.request",
    category="http",
    description=(
        "Esegue una o piu' richieste HTTP verso un bersaglio in scope. "
        "Ogni richiesta viene verificata contro lo scope del progetto prima "
        "di partire: una URL fuori scope blocca l'intera sequenza. "
        "Il numero di richieste e' limitato dal budget configurato."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "requests": {
                "type": "array",
                "description": "Sequenza di richieste da eseguire in ordine.",
                "minItems": 1,
                "maxItems": 50,
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 2048,
                            "description": "URL completo del bersaglio.",
                        },
                        "method": {
                            "type": "string",
                            "enum": list(ALLOWED_HTTP_METHODS),
                            "default": "GET",
                        },
                        "headers": {
                            "type": "object",
                            "description": "Header della richiesta.",
                            "additionalProperties": {"type": "string"},
                            "default": {},
                        },
                        "body": {
                            "type": "string",
                            "maxLength": 100_000,
                            "description": "Corpo della richiesta.",
                            "default": "",
                        },
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
            },
            "technique": {
                "type": "string",
                "maxLength": 128,
                "description": (
                    "Tecnica usata (es. 'active_testing', 'payload_injection'). "
                    "Consente o nega la richiesta in base alla policy."
                ),
                "default": "active_testing",
            },
        },
        "required": ["requests"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "requests_sent": {"type": "integer"},
            "budget": {"type": "integer"},
            "results": {"type": "array"},
        },
        "required": ["requests_sent", "budget", "results"],
    },
    requires_scope=True,
    # Operazione attiva: richiede sempre la conferma esplicita dell'operatore.
    mutating=True,
    timeout_seconds=120,
    technique="active_testing",
    install_hint="Non richiede installazione: usa httpx.",
    in_process=True,
    # Non e' esposto al provider LLM: i test attivi sono sotto il controllo
    # diretto dell'operatore, non del modello.
    model_callable=False,
)


def http_request_handler(tool_input: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Handler del tool HTTP: costruisce, verifica lo scope ed esegue."""
    from .http_client import build_request, perform_requests

    requests = [
        build_request(
            url=item["url"],
            method=item.get("method", "GET"),
            headers=item.get("headers") or {},
            body=item.get("body") or None,
        )
        for item in tool_input["requests"]
    ]
    technique = tool_input.get("technique") or "active_testing"
    return perform_requests(
        requests,
        session=context.session,
        project=context.project,
        technique=technique,
    )


# ---------------------------------------------------------------------------
# Tool Game Security: analisi statica e scaffolding di mod
# ---------------------------------------------------------------------------

GAME_ANALYZE_SPEC = ToolSpec(
    name="game.analyze",
    category="game",
    description=(
        "Analizza staticamente una cartella di gioco: riconosce il motore, "
        "i framework di modding presenti, i file di configurazione e di "
        "salvataggio. Non esegue il gioco e non modifica nulla."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1024,
                "description": "Cartella del gioco da analizzare.",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "engine": {"type": "string"},
            "modding_feasibility": {"type": "string"},
            "notes": {"type": "array"},
        },
        "required": ["engine", "modding_feasibility", "notes"],
    },
    requires_scope=True,
    mutating=False,
    timeout_seconds=120,
    technique="static_analysis",
    install_hint="Non richiede installazione.",
    in_process=True,
)

GAME_MOD_SCAFFOLD_SPEC = ToolSpec(
    name="game.mod_scaffold",
    category="game",
    description=(
        "Genera lo scaffolding di un mod (BepInEx, UE4SS, Godot, Python) in "
        "una cartella di destinazione. Scrive file: richiede conferma. I file "
        "esistenti non vengono sovrascritti."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "output_dir": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1024,
                "description": "Cartella in cui generare il mod.",
            },
            "name": {"type": "string", "minLength": 1, "maxLength": 100},
            "author": {"type": "string", "maxLength": 100, "default": "anonymous"},
            "version": {"type": "string", "maxLength": 40, "default": "0.1.0"},
            "description": {"type": "string", "maxLength": 1000, "default": ""},
            "target": {
                "type": "string",
                "enum": ["bepinex", "ue4ss", "godot", "python"],
                "default": "bepinex",
            },
        },
        "required": ["output_dir", "name"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "created": {"type": "array"},
            "instructions": {"type": "string"},
        },
        "required": ["created", "instructions"],
    },
    requires_scope=True,
    # Scrive file sul disco: richiede la conferma esplicita dell'operatore.
    mutating=True,
    timeout_seconds=60,
    technique="code_generation",
    install_hint="Non richiede installazione.",
    in_process=True,
    model_callable=False,
)


def game_analyze_handler(tool_input: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Handler del tool di analisi del gioco."""
    import sys

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from game.analyzer import analyze_directory, suggest_tools

    target = _resolve_target(tool_input["path"], context)
    info = analyze_directory(target)
    payload = info.to_dict()
    payload["suggested_tools"] = suggest_tools(info)
    return payload


def game_mod_scaffold_handler(
    tool_input: dict[str, Any], context: ToolContext
) -> dict[str, Any]:
    """Handler del tool di generazione dello scaffolding di un mod."""
    import sys

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from game.mod_creator import ModSpec, generate_mod, install_instructions

    output_dir = _resolve_target(tool_input["output_dir"], context)
    spec = ModSpec(
        name=tool_input["name"],
        author=tool_input.get("author", "anonymous"),
        version=tool_input.get("version", "0.1.0"),
        description=tool_input.get("description", ""),
        target=tool_input.get("target", "bepinex"),
    )
    created = generate_mod(spec, output_dir)
    return {
        "created": [str(path) for path in created],
        "instructions": install_instructions(spec, output_dir),
    }

def git_handler(tool_input: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Handler del tool Git: esegue solo sottocomandi in sola lettura."""
    target = _resolve_target(tool_input["path"], context)
    args = list(tool_input.get("args") or ["log", "--oneline", "-n", "50"])
    if not args or args[0] not in ALLOWED_GIT_SUBCOMMANDS:
        raise ValueError(
            "sottocomando git non consentito: "
            f"{args[0] if args else '(vuoto)'}. "
            f"Ammessi: {sorted(ALLOWED_GIT_SUBCOMMANDS)}"
        )
    completed = subprocess.run(  # noqa: S603 - argv costruito, shell=False
        ["git", "-C", str(target), *args],
        capture_output=True,
        text=True,
        timeout=context.timeout,
        shell=False,
        check=False,
    )
    return {
        "command": "git " + " ".join(args),
        "exit_code": completed.returncode,
        "stdout": completed.stdout[:200_000],
        "stderr": completed.stderr[:20_000],
    }


def bandit_handler(tool_input: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Handler del tool Bandit."""
    target = _resolve_target(tool_input["path"], context)
    output_format = tool_input.get("format", "json")
    completed = subprocess.run(  # noqa: S603 - argv statico, shell=False
        [sys.executable, "-m", "bandit", "-f", output_format, "-r", str(target)],
        capture_output=True,
        text=True,
        timeout=context.timeout,
        shell=False,
        check=False,
    )
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout[:500_000],
        "stderr": completed.stderr[:50_000],
    }


def pip_audit_handler(tool_input: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Handler del tool pip-audit."""
    target = _resolve_target(tool_input["path"], context)
    completed = subprocess.run(  # noqa: S603 - argv statico, shell=False
        [sys.executable, "-m", "pip_audit", "--format", "json", "-r", str(target)],
        capture_output=True,
        text=True,
        timeout=context.timeout,
        shell=False,
        check=False,
    )
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout[:500_000],
        "stderr": completed.stderr[:50_000],
    }


def _module_available(module_name: str) -> str:
    """Verifica se un modulo Python e' importabile; restituisce il percorso."""
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ValueError):
        return ""
    return spec.origin or "" if spec else ""


def register_builtin_tools() -> None:
    """Registra i tool built-in e ne verifica la disponibilita' reale."""
    registry.register(SAST_SQL_SPEC, sast_sql_handler)
    # Il tool SAST e' implementato in-process: sempre disponibile.
    registry.set_availability(
        SAST_SQL_SPEC.name,
        Availability(status="available", reason="implementazione nativa in-process"),
    )

    registry.register(BANDIT_SPEC, bandit_handler)
    bandit_path = shutil.which("bandit") or _module_available("bandit")
    registry.set_availability(
        BANDIT_SPEC.name,
        Availability(
            status="available" if bandit_path else "unavailable",
            reason=(
                "bandit installato"
                if bandit_path
                else "bandit non installato (pip install bandit)"
            ),
            version=bandit_path or "",
        ),
    )

    registry.register(PIP_AUDIT_SPEC, pip_audit_handler)
    pip_audit_path = shutil.which("pip-audit") or _module_available("pip_audit")
    registry.set_availability(
        PIP_AUDIT_SPEC.name,
        Availability(
            status="available" if pip_audit_path else "unavailable",
            reason=(
                "pip-audit installato"
                if pip_audit_path
                else "pip-audit non installato (pip install pip-audit)"
            ),
            version=pip_audit_path or "",
        ),
    )

    registry.register(GIT_SPEC, git_handler)
    git_path = shutil.which("git")
    registry.set_availability(
        GIT_SPEC.name,
        Availability(
            status="available" if git_path else "unavailable",
            reason="git installato" if git_path else "git non trovato nel PATH",
            version=git_path or "",
        ),
    )

    # Tool HTTP: implementato in-process, sempre disponibile. Le richieste
    # reali sono comunque vincolate dallo scope e dalla conferma.
    registry.register(HTTP_REQUEST_SPEC, http_request_handler)
    registry.set_availability(
        HTTP_REQUEST_SPEC.name,
        Availability(status="available", reason="implementazione nativa in-process"),
    )

    # Tool Game Security: analisi statica e scaffolding di mod.
    registry.register(GAME_ANALYZE_SPEC, game_analyze_handler)
    registry.set_availability(
        GAME_ANALYZE_SPEC.name,
        Availability(status="available", reason="implementazione nativa in-process"),
    )
    registry.register(GAME_MOD_SCAFFOLD_SPEC, game_mod_scaffold_handler)
    registry.set_availability(
        GAME_MOD_SCAFFOLD_SPEC.name,
        Availability(status="available", reason="implementazione nativa in-process"),
    )
