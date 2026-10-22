"""Elenca i file del repository esclusi gli artefatti e le dipendenze."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    "node_modules",
    ".venv",
    ".venv-ref",
    ".next",
    "__pycache__",
    ".git",
    ".pytest_cache",
}
EXCLUDED_FILES = {"test-report.txt", "test-report.xml", "diag_output.txt"}


def main() -> None:
    """Stampa l'albero dei file del repository."""
    for path in sorted(REPO.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(REPO)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if relative.name in EXCLUDED_FILES or relative.suffix == ".pyc":
            continue
        print(f"{relative.as_posix():<62} {path.stat().st_size:>8} byte")


if __name__ == "__main__":
    main()
