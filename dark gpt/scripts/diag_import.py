"""Utility di diagnostica: scrive un traceback leggibile su file UTF-8.

Uso: python scripts/diag_import.py <modulo>
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

target = sys.argv[1] if len(sys.argv) > 1 else "app.core.db"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / "diag_output.txt"

try:
    __import__(target)
    out.write_text(f"IMPORT OK: {target}\n", encoding="utf-8")
except Exception:
    out.write_text(
        f"IMPORT FAILED: {target}\n\n" + traceback.format_exc(), encoding="utf-8"
    )
print(f"scritto in {out}")
