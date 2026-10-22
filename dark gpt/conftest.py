"""Fixture e import path condivisi fra backend e laboratorio.

Aggiunge alla `sys.path` la root di `backend` (per il pacchetto `app`) e la
root del repository (per il pacchetto `lab`), in modo che i test del
laboratorio e quelli del backend siano eseguibili con un unico comando.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = REPO_ROOT / "backend"

for path in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
