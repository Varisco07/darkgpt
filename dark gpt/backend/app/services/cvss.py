"""Calcolo del CVSS v3.1 base score, con spiegazione delle metriche.

Implementazione autonoma: nessuna dipendenza esterna, cosi' il risultato e'
verificabile e testabile. Il vettore prodotto include la versione 3.1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

# Pesi ufficiali CVSS v3.1.
AV_WEIGHTS = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
AC_WEIGHTS = {"L": 0.77, "H": 0.44}
PR_WEIGHTS_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
PR_WEIGHTS_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.50}
UI_WEIGHTS = {"N": 0.85, "R": 0.62}
C_I_A_WEIGHTS = {"H": 0.56, "L": 0.22, "N": 0.0}

#: Impatto ambientale dichiarato (non impatta il base score).
ENVIRONMENTAL = ("CR", "IR", "AR", "MAV", "MPR", "MUI", "MS", "MC", "MI", "MA")


@dataclass(frozen=True)
class CvssMetrics:
    """Metriche base del CVSS v3.1."""

    attack_vector: Literal["N", "A", "L", "P"] = "N"
    attack_complexity: Literal["L", "H"] = "L"
    privileges_required: Literal["N", "L", "H"] = "N"
    user_interaction: Literal["N", "R"] = "N"
    scope: Literal["U", "C"] = "U"
    confidentiality: Literal["H", "L", "N"] = "N"
    integrity: Literal["H", "L", "N"] = "N"
    availability: Literal["H", "L", "N"] = "N"

    def vector(self) -> str:
        """Vettore completo in notazione CVSS v3.1."""
        return (
            f"CVSS:3.1/AV:{self.attack_vector}/AC:{self.attack_complexity}/"
            f"PR:{self.privileges_required}/UI:{self.user_interaction}/"
            f"S:{self.scope}/C:{self.confidentiality}/I:{self.integrity}/"
            f"A:{self.availability}"
        )


def _roundup(value: float) -> float:
    """Arrotondamento all'alto di CVSS 3.1 (1 decimal).

    La specifica prescrive: smallest number, specified to one decimal, that is
    equal to or higher than its input. Si implementa via ceil su scala 10^-1
    con epsilon per evitare errori floating point.
    """
    scaled = int(round(value * 100000))
    if scaled % 10000 == 0:
        return scaled / 100000.0
    return (math.floor(scaled / 10000) + 1) / 10.0


def compute_base_score(metrics: CvssMetrics) -> float:
    """Calcola il base score CVSS v3.1."""
    iss = 1 - (
        (1 - C_I_A_WEIGHTS[metrics.confidentiality])
        * (1 - C_I_A_WEIGHTS[metrics.integrity])
        * (1 - C_I_A_WEIGHTS[metrics.availability])
    )

    if metrics.scope == "U":
        impact = 6.42 * iss
        pr_weights = PR_WEIGHTS_UNCHANGED
    else:
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
        pr_weights = PR_WEIGHTS_CHANGED

    exploitability = (
        8.22
        * AV_WEIGHTS[metrics.attack_vector]
        * AC_WEIGHTS[metrics.attack_complexity]
        * pr_weights[metrics.privileges_required]
        * UI_WEIGHTS[metrics.user_interaction]
    )

    if impact <= 0:
        return 0.0
    if metrics.scope == "U":
        raw = min(impact + exploitability, 10)
    else:
        raw = min(1.08 * (impact + exploitability), 10)
    return _roundup(raw)


def severity_from_score(score: float) -> str:
    """Classificazione qualitativa prevista da CVSS v3.1."""
    if score == 0:
        return "NONE"
    if score <= 3.9:
        return "LOW"
    if score <= 6.9:
        return "MEDIUM"
    if score <= 8.9:
        return "HIGH"
    return "CRITICAL"


def explain_metrics(metrics: CvssMetrics) -> dict[str, str]:
    """Spiega in italiano la scelta di ogni metrica.

    Serve a rendere il report verificabile: il lettore deve poter valutare se
    le metriche scelte corrispondono alla vulnerabilita' reale.
    """
    return {
        "AV": f"Attack Vector = {metrics.attack_vector}: "
        + {
            "N": "rete, l'attaccante raggiunge il componente da remoto",
            "A": "adiacente, richiede un passaggio di rete o un account sulla stessa rete",
            "L": "locale, richiede accesso al sistema",
            "P": "fisico, richiede accesso fisico al dispositivo",
        }[metrics.attack_vector],
        "AC": f"Attack Complexity = {metrics.attack_complexity}: "
        + {
            "L": "bassa, nessuna condizione speciale e nessuna competenza avanzata",
            "H": "alta, richiede condizioni specifiche e competenze non banali",
        }[metrics.attack_complexity],
        "PR": f"Privileges Required = {metrics.privileges_required}: "
        + {
            "N": "nessun privilegio, attaccante anonimo",
            "L": "privilegi minimi, utente autenticato con permessi limitati",
            "H": "privilegi elevati, utente con permessi significativi",
        }[metrics.privileges_required],
        "UI": f"User Interaction = {metrics.user_interaction}: "
        + {
            "N": "nessuna interazione richiesta alle vittime",
            "R": "richiede l'intervento di un utente (clic, conferma, invio)",
        }[metrics.user_interaction],
        "S": f"Scope = {metrics.scope}: "
        + {
            "U": "impatto limitato all' componente vulnerabile",
            "C": "impatto oltre i confini di sicurezza del componente (altro sistema)",
        }[metrics.scope],
        "C": f"Confidentiality = {metrics.confidentiality}: impatto sulla riservatezza.",
        "I": f"Integrity = {metrics.integrity}: impatto sull'integrita'.",
        "A": f"Availability = {metrics.availability}: impatto sulla disponibilita'.",
    }
