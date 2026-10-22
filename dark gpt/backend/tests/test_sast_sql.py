"""Test dell'analizzatore statico per SQL injection."""

from __future__ import annotations

from app.tools.sast_sql import analyze_source, scan_path

VULNERABLE_FSTRING = '''
import sqlite3

def search_users(conn, term):
    cursor = conn.cursor()
    cursor.execute(f"SELECT id, name FROM users WHERE name LIKE '%{term}%'")
    return cursor.fetchall()
'''

VULNERABLE_CONCAT = '''
def find_user(conn, user_id):
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(query)
    return cursor.fetchall()
'''

VULNERABLE_PERCENT = '''
def find_user(conn, user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)
    return cursor.fetchall()
'''

SAFE_PARAMETRIC = '''
def find_user(conn, user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchall()
'''

SAFE_CONSTANT = '''
def all_users(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()
'''

NOT_SQL = '''
def greet(name):
    return "ciao " + name
'''


def test_detects_fstring_query():
    findings = analyze_source("vuln.py", VULNERABLE_FSTRING)
    assert len(findings) == 1
    finding = findings[0]
    assert "f-string" in finding.message
    assert finding.severity in ("HIGH", "MEDIUM")
    assert finding.cwe == "CWE-89"


def test_detects_concatenation():
    findings = analyze_source("vuln.py", VULNERABLE_CONCAT)
    assert len(findings) == 1
    assert "concatenazione" in findings[0].message


def test_detects_percent_formatting():
    findings = analyze_source("vuln.py", VULNERABLE_PERCENT)
    assert len(findings) == 1
    assert "formato %" in findings[0].message


def test_ignores_parametrized_query():
    assert analyze_source("safe.py", SAFE_PARAMETRIC) == []


def test_ignores_constant_query():
    assert analyze_source("safe.py", SAFE_CONSTANT) == []


def test_ignores_non_sql_concatenation():
    assert analyze_source("safe.py", NOT_SQL) == []


def test_reports_function_name():
    findings = analyze_source("vuln.py", VULNERABLE_FSTRING)
    assert findings[0].function == "search_users"


def test_reports_line_number():
    findings = analyze_source("vuln.py", VULNERABLE_FSTRING)
    # Il sorgente di test inizia con una riga vuota: la chiamata execute e'
    # alla riga 6.
    assert findings[0].line == 6


def test_reports_sink_line_not_assignment_line():
    """Il finding e' ancorato al sink (execute), non all'assegnazione."""
    findings = analyze_source("vuln.py", VULNERABLE_CONCAT)
    assert findings[0].line == 5
    assert "SELECT * FROM users" in findings[0].snippet


def test_syntax_error_is_reported_not_raised():
    findings = analyze_source("broken.py", "def (:\n")
    assert len(findings) == 1
    assert findings[0].severity == "INFO"


def test_scan_path_reports_files_and_findings(tmp_path):
    (tmp_path / "vuln.py").write_text(VULNERABLE_FSTRING, encoding="utf-8")
    (tmp_path / "safe.py").write_text(SAFE_PARAMETRIC, encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.py").write_text(VULNERABLE_CONCAT, encoding="utf-8")

    report = scan_path(tmp_path)

    assert report["files_scanned"] == 3
    assert report["summary"]["total"] == 2
    assert "vuln.py" in report["files"]
    assert "sub/nested.py" in report["files"] or "sub\\nested.py" in report["files"]


def test_scan_path_on_missing_directory(tmp_path):
    report = scan_path(tmp_path / "inesistente")
    assert report["files_scanned"] == 0
    assert report["skipped"][0]["reason"] == "percorso inesistente"


def test_scan_path_excludes_virtualenv(tmp_path):
    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "bad.py").write_text(VULNERABLE_FSTRING, encoding="utf-8")

    report = scan_path(tmp_path)
    assert report["files_scanned"] == 0
