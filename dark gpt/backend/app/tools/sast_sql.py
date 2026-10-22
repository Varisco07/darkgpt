"""Analizzatore statico per SQL Injection in codice Python.

L'analisi e' basata sull'AST di Python (`ast`), non su regex: riduce i falsi
positivi e distingue query costruite dinamicamente da query costruite in modo
sicuro.

Rileva:
- `cursor.execute(<query non letterale>)` con query costruita da f-string,
  `%`, `.format()` o concatenazione `+`
- query SQL che contengono parole chiave e vengono concatenate con variabili
- uso di `text()` / `raw()` con interpolazione

Non distingue da solo la provenienza del dato (input utente vs costante): un
finding e' sempre `POTENTIAL` e la conferma richiede verifica dinamica.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

#: Metodi/funzioni che eseguono una query SQL.
SQL_EXEC_METHODS = frozenset(
    {"execute", "executemany", "executescript", "exec_driver_sql", "raw"}
)

#: Nomi di funzioni che costruiscono SQL in modo parametricamente non sicuro.
SQL_BUILDER_CALLS = frozenset({"text", "raw", "sql"})

#: Parole chiave SQL che indicano una query.
SQL_KEYWORDS = frozenset(
    {
        "select",
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "create",
        "truncate",
        "merge",
        "union",
        "grant",
        "revoke",
        "exec",
        "execute",
        "pragma",
        "attach",
        "vacuum",
    }
)

#: Sorgenti di input considerate non fidabili (tasso di rilevamento piu' alto).
TAINTED_SOURCES = frozenset(
    {
        "request",
        "flask",
        "fastapi",
        "django",
        "input",
        "argv",
        "environ",
        "getenv",
        "params",
        "args",
        "form",
        "json",
        "cookies",
        "headers",
        "body",
        "query_string",
    }
)


@dataclass
class SastFinding:
    """Un sospetto di SQL injection individuato nel codice."""

    file: str
    line: int
    column: int
    function: str
    snippet: str
    category: str
    severity: str
    confidence: float
    message: str
    taint_sources: list[str] = field(default_factory=list)
    remediation: str = ""
    cwe: str = "CWE-89"
    owasp: str = "A03:2021 - Injection"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "function": self.function,
            "snippet": self.snippet,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "message": self.message,
            "taint_sources": self.taint_sources,
            "remediation": self.remediation,
            "cwe": self.cwe,
            "owasp": self.owasp,
        }


def _is_sql_literal(text: str) -> bool:
    """True se la stringa contiene parole chiave SQL."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in SQL_KEYWORDS)


def _taint_sources(node: ast.AST) -> list[str]:
    """Individua le fonti di input non fidabile raggiungibili da un nodo.

    Analisi semplice, in profondita' limitata: si cercano riferimenti a
    funzioni e attributi tipici di framework web o di input utente.
    """
    sources: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name.lower() in TAINTED_SOURCES:
                sources.append(name)
        elif isinstance(child, ast.Attribute):
            if child.attr.lower() in TAINTED_SOURCES:
                sources.append(child.attr)
        elif isinstance(child, ast.Name):
            if child.id.lower() in TAINTED_SOURCES:
                sources.append(child.id)
    return sorted(set(sources))


def _dynamic_query_evidence(node: ast.AST) -> list[str]:
    """Elenca i costrutti dinamici che rendono la query non sicura."""
    evidence: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.JoinedStr):
            evidence.append("f-string")
        elif isinstance(child, ast.BinOp) and isinstance(child.op, ast.Mod):
            evidence.append("formato %")
        elif isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if child.func.attr == "format":
                evidence.append("str.format")
        elif isinstance(child, ast.BinOp) and isinstance(child.op, ast.Add):
            evidence.append("concatenazione")
    return sorted(set(evidence))


def _contains_sql_keyword(node: ast.AST) -> bool:
    """Verifica se l'espressione contiene una stringa SQL o un marker di query."""
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if _is_sql_literal(child.value):
                return True
        elif isinstance(child, ast.JoinedStr):
            for part in child.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    if _is_sql_literal(part.value):
                        return True
    return False


class SqlInjectionAnalyzer(ast.NodeVisitor):
    """Analizzatore AST per SQL injection su codice Python."""

    def __init__(self, filename: str, source: str) -> None:
        self.filename = filename
        self.source = source
        self.findings: list[SastFinding] = []
        self._function_stack: list[str] = []
        #: Variabili assegnate a una query SQL dinamica, per funzione.
        self._sql_vars: dict[str, ast.AST] = {}

    # -- visitatori ------------------------------------------------------
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._function_stack.append(node.name)
        previous = self._sql_vars
        self._sql_vars = {}
        self.generic_visit(node)
        self._sql_vars = previous
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._function_stack.append(node.name)
        previous = self._sql_vars
        self._sql_vars = {}
        self.generic_visit(node)
        self._sql_vars = previous
        self._function_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        """Registra le variabili assegnate a una query SQL dinamica."""
        self.generic_visit(node)
        value = node.value
        if not _dynamic_query_evidence(value):
            return
        if not _contains_sql_keyword(value):
            return
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._sql_vars[target.id] = value

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        """Registro delle assegnazioni annotate (`query: str = "..."`)."""
        self.generic_visit(node)
        value = node.value
        if value is None:
            return
        if not _dynamic_query_evidence(value) or not _contains_sql_keyword(value):
            return
        if isinstance(node.target, ast.Name):
            self._sql_vars[node.target.id] = value

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        self.generic_visit(node)
        self._check_call(node)

    # -- logica ----------------------------------------------------------
    def _current_function(self) -> str:
        return self._function_stack[-1] if self._function_stack else "<module>"

    def _check_call(self, node: ast.Call) -> None:
        func = node.func
        name = ""
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id

        if name in SQL_EXEC_METHODS and node.args:
            self._check_execute(node, node.args[0])
        elif name in SQL_BUILDER_CALLS and node.args:
            self._check_builder(node, node.args[0])

    def _resolve_query(self, node: ast.AST) -> tuple[ast.AST, ast.AST]:
        """Risolve una variabile che contiene la query SQL.

        Restituisce la coppia (espressione analizzata, nodo del sink): se la
        query e' stata assegnata a una variabile, l'analisi guarda
        l'espressione assegnata ma il finding e' ancorato al sink.
        """
        if isinstance(node, ast.Name) and node.id in self._sql_vars:
            return self._sql_vars[node.id], node
        return node, node

    def _check_execute(self, node: ast.Call, query_arg: ast.AST) -> None:
        """Analizza il primo argomento di una chiamata `execute`."""
        query_node, sink = self._resolve_query(query_arg)
        dynamic = _dynamic_query_evidence(query_node)
        if not dynamic:
            return  # query letterale: sicura per costruzione
        if not _contains_sql_keyword(query_node):
            return  # non e' chiaramente SQL: non si segnala

        taint = _taint_sources(query_node)
        severity = "HIGH" if taint else "MEDIUM"
        confidence = 0.9 if taint else 0.6
        message = (
            "Query SQL eseguita con argomenti costruiti dinamicamente "
            f"({', '.join(dynamic)})."
        )
        if taint:
            message += f" L'input proviene da: {', '.join(taint)}."
        else:
            message += (
                " La provenienza del valore non e' determinabile staticamente: "
                "verificare con test in laboratorio."
            )
        self._add_finding(
            sink, query_node, message, severity, confidence, taint,
            "SQL injection potenziale",
        )

    def _check_builder(self, node: ast.Call, query_node: ast.AST) -> None:
        """Analizza `text()` / `raw()` costruiti dinamicamente."""
        dynamic = _dynamic_query_evidence(query_node)
        if not dynamic or not _contains_sql_keyword(query_node):
            return
        taint = _taint_sources(query_node)
        severity = "HIGH" if taint else "MEDIUM"
        confidence = 0.9 if taint else 0.6
        self._add_finding(
            node,
            query_node,
            "Query SQL costruita con interpolazione: i parametri vanno passati "
            "separatamente al driver, non inseriti nella stringa.",
            severity,
            confidence,
            taint,
            "SQL injection potenziale",
        )

    def _add_finding(
        self,
        node: ast.AST,
        query_node: ast.AST,
        message: str,
        severity: str,
        confidence: float,
        taint: list[str],
        category: str,
    ) -> None:
        """Registra un finding.

        `node` e' il sink (la chiamata che esegue la query): e' il punto
        ancorato nel codice. `query_node` e' l'espressione della query: da
        essa proviene lo snippet mostrato.
        """
        line = getattr(node, "lineno", 0)
        column = getattr(node, "col_offset", 0)
        self.findings.append(
            SastFinding(
                file=self.filename,
                line=line,
                column=column,
                function=self._current_function(),
                snippet=self._snippet(query_node),
                category=category,
                severity=severity,
                confidence=confidence,
                message=message,
                taint_sources=taint,
                remediation=(
                    "Usare query parametrizzate: `cursor.execute(\"SELECT ... WHERE id = ?\", "
                    "(value,))` oppure, con SQLAlchemy, `session.execute("
                    "text(\"SELECT ... WHERE id = :id\"), {\"id\": value})`. "
                    "Non concatenare mai l'input nella stringa SQL."
                ),
            )
        )

    def _snippet(self, node: ast.AST) -> str:
        """Estratto di codice che evidenzia il problema (max 240 caratteri)."""
        try:
            segment = ast.get_source_segment(self.source, node) or ""
        except (ValueError, TypeError):  # pragma: no cover
            segment = ""
        segment = segment.strip()
        if len(segment) > 240:
            segment = segment[:240] + "..."
        return segment


#: Directory da escludere dalla scansione.
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        "site-packages",
    }
)

#: Estensioni dei file analizzati.
PYTHON_SUFFIXES = frozenset({".py"})


def analyze_source(filename: str, source: str) -> list[SastFinding]:
    """Analizza un sorgente Python e restituisce i sospetti trovati."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return [
            SastFinding(
                file=filename,
                line=exc.lineno or 0,
                column=exc.offset or 0,
                function="<parse>",
                snippet="",
                category="Errore di analisi",
                severity="INFO",
                confidence=1.0,
                message=f"impossibile analizzare il file: {exc.msg}",
            )
        ]
    analyzer = SqlInjectionAnalyzer(filename, source)
    analyzer.visit(tree)
    return analyzer.findings


def iter_python_files(root: Path, max_files: int = 2000) -> list[Path]:
    """Elenca i file Python sotto `root`, escludendo le directory escluse."""
    collected: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        collected.append(path)
        if len(collected) >= max_files:
            break
    return collected


def scan_path(
    root: Path,
    max_files: int = 2000,
    max_file_bytes: int = 5_000_000,
) -> dict[str, Any]:
    """Esegue la scansione di una directory e restituisce un report JSON.

    Il report contiene solo dati realmente osservati nel codice: nessun
    risultato e' inventato.
    """
    root = root.resolve()
    findings: list[SastFinding] = []
    scanned_files: list[str] = []
    skipped: list[dict[str, str]] = []

    if not root.exists():
        return {
            "root": str(root),
            "files_scanned": 0,
            "files": [],
            "findings": [],
            "skipped": [{"path": str(root), "reason": "percorso inesistente"}],
            "summary": {"total": 0, "by_severity": {}},
        }

    for file_path in iter_python_files(root, max_files=max_files):
        try:
            size = file_path.stat().st_size
        except OSError as exc:
            skipped.append({"path": str(file_path), "reason": f"stat non riuscito: {exc}"})
            continue
        if size > max_file_bytes:
            skipped.append(
                {"path": str(file_path), "reason": f"file troppo grande ({size} byte)"}
            )
            continue
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            skipped.append({"path": str(file_path), "reason": f"lettura non riuscita: {exc}"})
            continue
        relative = str(file_path.relative_to(root)).replace("\\", "/")
        scanned_files.append(relative)
        findings.extend(analyze_source(relative, source))

    by_severity: dict[str, int] = {}
    for finding in findings:
        by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1

    return {
        "root": str(root),
        "files_scanned": len(scanned_files),
        "files": scanned_files,
        "findings": [finding.to_dict() for finding in findings],
        "skipped": skipped,
        "summary": {"total": len(findings), "by_severity": by_severity},
    }
