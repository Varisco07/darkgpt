"""API dei finding: elenco, creazione, evidenze e transizioni di stato."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from ...models.enums import FindingSeverity, FindingStatus
from ...schemas.finding import (
    EvidenceCreate,
    EvidenceRead,
    FindingCreate,
    FindingRead,
    FindingTransitionRequest,
    FindingUpdate,
    StateChangeRead,
)
from ...services.findings import FindingService
from ..deps import CurrentProject, DbSession

router = APIRouter(prefix="/projects/{project_id}/findings", tags=["findings"])


def _to_read(finding) -> FindingRead:  # noqa: ANN001 - modello SQLAlchemy
    return FindingRead(
        id=finding.id,
        project_id=finding.project_id,
        title=finding.title,
        category=finding.category,
        component=finding.component,
        status=finding.status,
        severity=finding.severity,
        confidence=finding.confidence,
        cvss_score=finding.cvss_score,
        cvss_vector=finding.cvss_vector,
        hypothesis=finding.hypothesis,
        impact=finding.impact,
        remediation=finding.remediation,
        location=finding.location,
        cwe=finding.cwe,
        owasp=finding.owasp,
        created_at=finding.created_at,
        updated_at=finding.updated_at,
        evidences=[
            EvidenceRead(
                id=item.id,
                finding_id=item.finding_id,
                kind=item.kind,
                payload=item.payload,
                observed=item.observed,
                source=item.source,
                created_at=item.created_at,
            )
            for item in finding.evidences
        ],
        state_changes=[
            StateChangeRead(
                id=item.id,
                finding_id=item.finding_id,
                from_status=item.from_status,
                to_status=item.to_status,
                reason=item.reason,
                actor=item.actor,
                created_at=item.created_at,
            )
            for item in finding.state_changes
        ],
    )


@router.get("", response_model=list[FindingRead], summary="Elenco dei finding")
def list_findings(
    project: CurrentProject,
    session: DbSession,
    status_filter: FindingStatus | None = Query(default=None, alias="status"),
    severity: FindingSeverity | None = None,
    category: str | None = None,
) -> list[FindingRead]:
    findings = FindingService(session).list_findings(
        project.id, status=status_filter, severity=severity, category=category
    )
    return [_to_read(finding) for finding in findings]


@router.post(
    "",
    response_model=FindingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un finding",
)
def create_finding(
    payload: FindingCreate, project: CurrentProject, session: DbSession
) -> FindingRead:
    """Crea un finding.

    I finding nati dall'analisi statica sono POTENTIAL: la conferma richiede
    evidenze e una transizione esplicita.
    """
    service = FindingService(session)
    finding = service.create(
        project,
        title=payload.title,
        category=payload.category,
        component=payload.component,
        severity=payload.severity,
        confidence=payload.confidence,
        hypothesis=payload.hypothesis,
        impact=payload.impact,
        remediation=payload.remediation,
        location=payload.location,
        cwe=payload.cwe,
        owasp=payload.owasp,
        evidence=[item.model_dump() for item in payload.evidence],
    )
    session.flush()
    return _to_read(finding)


@router.get(
    "/{finding_id}", response_model=FindingRead, summary="Dettaglio di un finding"
)
def get_finding(
    project: CurrentProject, session: DbSession, finding_id: int
) -> FindingRead:
    service = FindingService(session)
    return _to_read(service.get(project.id, finding_id))


@router.patch(
    "/{finding_id}", response_model=FindingRead, summary="Modifica un finding"
)
def update_finding(
    payload: FindingUpdate,
    project: CurrentProject,
    session: DbSession,
    finding_id: int,
) -> FindingRead:
    """Modifica i campi descrittivi. Lo stato cambia solo via transizione."""
    service = FindingService(session)
    finding = service.get(project.id, finding_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(finding, field, value)
    session.flush()
    return _to_read(finding)


@router.post(
    "/{finding_id}/evidence",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Aggiunge un'evidenza a un finding",
)
def add_evidence(
    payload: EvidenceCreate,
    project: CurrentProject,
    session: DbSession,
    finding_id: int,
) -> EvidenceRead:
    service = FindingService(session)
    finding = service.get(project.id, finding_id)
    evidence = service.add_evidence(finding.id, **payload.model_dump())
    session.flush()
    return EvidenceRead(
        id=evidence.id,
        finding_id=evidence.finding_id,
        kind=evidence.kind,
        payload=evidence.payload,
        observed=evidence.observed,
        source=evidence.source,
        created_at=evidence.created_at,
    )


@router.post(
    "/{finding_id}/transition",
    response_model=FindingRead,
    summary="Cambia lo stato di un finding",
)
def transition_finding(
    payload: FindingTransitionRequest,
    project: CurrentProject,
    session: DbSession,
    finding_id: int,
) -> FindingRead:
    """Esegue una transizione di stato validata dalla macchina a stati.

    Le transizioni non previste restituiscono 409. La conferma a CONFIRMED
    senza evidenze restituisce 422.
    """
    service = FindingService(session)
    finding = service.get(project.id, finding_id)
    if payload.evidence:
        for item in payload.evidence:
            service.add_evidence(finding.id, **item.model_dump())
        session.flush()
    finding = service.transition(
        finding, payload.status, payload.reason, payload.actor
    )
    session.flush()
    return _to_read(finding)
