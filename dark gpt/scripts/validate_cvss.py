"""Validazione incrociata esaustiva del calcolatore CVSS v3.1 di DarkGPT.

Confronta l'implementazione in `app.services.cvss` con la libreria di
riferimento `cvss` (v3.6) su TUTTE le combinazioni delle metriche base
(4*2*3*2*2*3*3*3 = 2592 vettori).

Uso:
    python scripts/validate_cvss.py
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.services.cvss import CvssMetrics, compute_base_score  # noqa: E402

try:
    from cvss import CVSS3
except ImportError:  # pragma: no cover
    print("ERRORE: la libreria di riferimento 'cvss' non e' installata.")
    print("Installala in un ambiente separato con: pip install cvss")
    raise SystemExit(2) from None

AV = ["N", "A", "L", "P"]
AC = ["L", "H"]
PR = ["N", "L", "H"]
UI = ["N", "R"]
SCOPE = ["U", "C"]
CIA = ["N", "L", "H"]


def main() -> int:
    total = 0
    mismatches: list[tuple[str, float, float]] = []

    for av, ac, pr, ui, scope, c, i, a in itertools.product(AV, AC, PR, UI, SCOPE, CIA, CIA, CIA):
        metrics = CvssMetrics(
            attack_vector=av,
            attack_complexity=ac,
            privileges_required=pr,
            user_interaction=ui,
            scope=scope,
            confidentiality=c,
            integrity=i,
            availability=a,
        )
        vector = metrics.vector()
        mine = compute_base_score(metrics)
        reference = float(CVSS3(vector).base_score)
        total += 1
        if abs(mine - reference) > 1e-9:
            mismatches.append((vector, mine, reference))

    print(f"vettori verificati: {total}")
    print(f"discrepanze: {len(mismatches)}")
    for vector, mine, reference in mismatches[:15]:
        print(f"  MISMATCH {vector}  darkgpt={mine}  reference={reference}")

    if mismatches:
        return 1
    print("RISULTATO: implementazione DarkGPT allineata alla libreria di riferimento")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
