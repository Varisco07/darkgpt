"""Test del calcolo CVSS v3.1.

I valori attesi sono quelli pubblicati dal FIRST per i vettori indicati.
Una validazione esaustiva su tutti i 2592 vettori base e' eseguita da
`scripts/validate_cvss.py` (richiede la libreria di riferimento `cvss`).
"""

from __future__ import annotations

import pytest

from app.services.cvss import (
    CvssMetrics,
    compute_base_score,
    explain_metrics,
    severity_from_score,
)


@pytest.mark.parametrize(
    ("vector", "expected"),
    [
        ("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
        ("AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H", 7.5),
        ("AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H", 7.8),
        ("AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1),
        ("AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0),
        ("AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:N/A:H", 5.9),
        ("AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N", 6.5),
        ("AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0),
    ],
)
def test_base_score_matches_published_values(vector: str, expected: float):
    metrics = _metrics_from_vector(vector)
    assert compute_base_score(metrics) == expected


def test_privileges_required_changes_with_scope():
    """Con Scope Changed i pesi di PR cambiano: 0.27 -> 0.50 per High."""
    unchanged = CvssMetrics(
        attack_vector="L",
        attack_complexity="H",
        privileges_required="H",
        user_interaction="R",
        scope="U",
        confidentiality="L",
        integrity="L",
        availability="L",
    )
    changed = CvssMetrics(
        attack_vector="L",
        attack_complexity="H",
        privileges_required="H",
        user_interaction="R",
        scope="C",
        confidentiality="L",
        integrity="L",
        availability="L",
    )
    assert compute_base_score(changed) > compute_base_score(unchanged)


def test_vector_string_format():
    metrics = CvssMetrics(
        attack_vector="N",
        attack_complexity="L",
        privileges_required="N",
        user_interaction="N",
        scope="U",
        confidentiality="H",
        integrity="H",
        availability="H",
    )
    assert metrics.vector() == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


@pytest.mark.parametrize(
    ("score", "severity"),
    [
        (0.0, "NONE"),
        (3.9, "LOW"),
        (4.0, "MEDIUM"),
        (6.9, "MEDIUM"),
        (7.0, "HIGH"),
        (8.9, "HIGH"),
        (9.0, "CRITICAL"),
        (10.0, "CRITICAL"),
    ],
)
def test_severity_thresholds(score: float, severity: str):
    assert severity_from_score(score) == severity


def test_explain_metrics_covers_every_metric():
    metrics = CvssMetrics()
    explanation = explain_metrics(metrics)
    for key in ("AV", "AC", "PR", "UI", "S", "C", "I", "A"):
        assert key in explanation
        assert len(explanation[key]) > 10


def _metrics_from_vector(vector: str) -> CvssMetrics:
    """Costruisce le metriche da una stringa vettore senza il prefisso."""
    parts = dict(item.split(":", 1) for item in vector.split("/"))
    return CvssMetrics(
        attack_vector=parts["AV"],
        attack_complexity=parts["AC"],
        privileges_required=parts["PR"],
        user_interaction=parts["UI"],
        scope=parts["S"],
        confidentiality=parts["C"],
        integrity=parts["I"],
        availability=parts["A"],
    )
