"""Test del ciclo di vita dei finding e della macchina a stati."""

from __future__ import annotations

import pytest

from app.core.errors import ConflictError, ValidationError
from app.models.enums import EvidenceKind, FindingSeverity, FindingStatus
from app.services.findings import FindingService


def test_create_finding_starts_as_potential(session, project):
    service = FindingService(session)
    finding = service.create(project, title="SQL injection in search", category="SQLi")

    assert finding.status is FindingStatus.POTENTIAL
    assert finding.severity is FindingSeverity.MEDIUM
    assert len(finding.state_changes) == 1


def test_cannot_confirm_without_evidence(session, project):
    service = FindingService(session)
    finding = service.create(project, title="Da confermare")

    with pytest.raises(ValidationError):
        service.transition(finding, FindingStatus.CONFIRMED, "prova manuale")


def test_confirm_with_evidence_succeeds(session, project):
    service = FindingService(session)
    finding = service.create(
        project,
        title="SQL injection in search",
        evidence=[
            {
                "kind": EvidenceKind.HTTP_REQUEST,
                "payload": "GET /search?q=1' OR '1'='1",
                "observed": "risposta con 12 righe",
            }
        ],
    )
    service.transition(finding, FindingStatus.CONFIRMED, "payload riproducibile")

    assert finding.status is FindingStatus.CONFIRMED
    assert finding.state_changes[-1].to_status is FindingStatus.CONFIRMED


def test_invalid_transition_raises_conflict(session, project):
    service = FindingService(session)
    finding = service.create(project, title="Da confermare")

    with pytest.raises(ConflictError):
        service.transition(finding, FindingStatus.FIXED, "salto non consentito")


def test_transition_requires_reason(session, project):
    service = FindingService(session)
    finding = service.create(project, title="Da confermare")

    with pytest.raises(ValidationError):
        service.transition(finding, FindingStatus.FALSE_POSITIVE, "   ")


def test_same_status_transition_raises(session, project):
    service = FindingService(session)
    finding = service.create(project, title="Da confermare")

    with pytest.raises(ConflictError):
        service.transition(finding, FindingStatus.POTENTIAL, "nessun cambiamento")


def test_mark_fixed_requires_evidence(session, project):
    service = FindingService(session)
    finding = service.create(
        project,
        title="SQL injection in search",
        evidence=[{"kind": EvidenceKind.MANUAL_NOTE, "payload": "test di regressione"}],
    )
    service.transition(finding, FindingStatus.CONFIRMED, "riprodotto")
    service.mark_fixed(finding, "corretto e verificato con test di regressione")

    assert finding.status is FindingStatus.FIXED


def test_evidence_is_redacted(session, project):
    service = FindingService(session)
    finding = service.create(project, title="Con segreto")
    evidence = service.add_evidence(
        finding.id,
        kind=EvidenceKind.HTTP_REQUEST,
        payload="Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
    )

    assert "abcdefghijklmnopqrstuvwxyz" not in evidence.payload
    assert "REDACTED" in evidence.payload


def test_list_findings_filters_by_status(session, project):
    service = FindingService(session)
    first = service.create(project, title="Uno")
    second = service.create(project, title="Due")
    service.transition(
        second,
        FindingStatus.FALSE_POSITIVE,
        "analizzato: non e' sfruttabile",
    )

    potential = service.list_findings(project.id, status=FindingStatus.POTENTIAL)
    assert [item.id for item in potential] == [first.id]


def test_summary_counts(session, project):
    service = FindingService(session)
    service.create(project, title="Uno", severity=FindingSeverity.HIGH)
    service.create(project, title="Due", severity=FindingSeverity.LOW)

    summary = service.summary(project.id)
    assert summary["total"] == 2
    assert summary["by_severity"]["HIGH"] == 1
    assert summary["by_status"]["POTENTIAL"] == 2
