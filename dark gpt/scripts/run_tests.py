"""Esegue la suite di test completa (backend + laboratorio) e salva il report.

Uso:
    python scripts/run_tests.py [pytest args...]

La suite viene eseguita dalla root del repository, dove `pytest.ini` include
sia `backend/tests` sia `lab/tests`. Il report completo e' scritto in
`test-report.txt`; il JUnit XML in `test-report.xml`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "test-report.txt"

command = [
    sys.executable,
    "-m",
    "pytest",
    *sys.argv[1:],
    f"--junit-xml={REPORT.with_suffix('.xml')}",
]

completed = subprocess.run(
    command,
    cwd=REPO,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)

output = (completed.stdout or "") + (completed.stderr or "")
REPORT.write_text(output, encoding="utf-8")

summary = [
    line
    for line in output.splitlines()
    if line.startswith(("=", "-")) or " passed" in line or " failed" in line
]
print("\n".join(summary[-20:]) if summary else output[-2000:])
print(f"\ncodice di uscita: {completed.returncode}")
print(f"report completo: {REPORT}")
sys.exit(completed.returncode)
