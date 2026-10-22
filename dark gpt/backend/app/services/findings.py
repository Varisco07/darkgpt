"""Servizio dei finding: creazione, evidenze, transizioni di stato.

Regola fondamentale: un finding non puo' passare a CONFIRMED senza
evidenze. Ogni transizione e' motivata e registrata.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..core.security import redact
from ..models.enums import (
    ALLOWED_TRANSITIONS,
    EvidenceKind,
    FindingSeverity,
    FindingStatus,
)
from ..models.finding import Finding, FindingEvidence, StateChange
from ..models.project import Project


class FindingService:
    """Operazioni sul ciclo di vita dei finding di un progetto."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- lettura ---------------------------------------------------------
    def list_findings(
        self,
        project_id: int,
        status: FindingStatus | None = None,
        severity: FindingSeverity | None = None,
        category: str | None = None,
    ) -> list[Finding]:
        stmt = select(Finding).where(Finding.project_id == project_id)
        if status is not None:
            stmt = stmt.where(Finding.status == status)
        if severity is not None:
            stmt = stmt.where(Finding.severity == severity)
        if category:
            stmt = stmt.where(Finding.category == category)
        return list(self.session.scalars(stmt.order_by(Finding.id.desc())))

    def get(self, project_id: int, finding_id: int) -> Finding:
        finding = self.session.get(Finding, finding_id)
        if finding is None or finding.project_id != project_id:
            raise NotFoundError(
                f"finding {finding_id} non trovato nel progetto {project_id}",
                details={"project_id": project_id, "finding_id": finding_id},
            )
        return finding

    # -- creazione -------------------------------------------------------
    def create(
        self,
        project: Project,
        *,
        title: str,
        category: str = "",
        component: str = "",
        severity: FindingSeverity = FindingSeverity.MEDIUM,
        hypothesis: str = "",
        impact: str = "",
        remediation: str = "",
        location: str = "",
        cwe: str = "",
        owasp: str = "",
        status: FindingStatus = FindingStatus.POTENTIAL,
        confidence: float = 0.5,
        evidence: list[dict] | None = None,
        actor: str = "operator",
    ) -> Finding:
        """Crea un finding. I finding nascono POTENTIAL salvo indicazione contraria."""
        if not title.strip():
            raise ValidationError("il titolo del finding e' obbligatorio")
        if status is FindingStatus.CONFIRMED and not evidence:
            raise ValidationError(
                "non si puo' creare un finding CONFIRMED senza evidenze a supporto"
            )
        finding = Finding(
            project_id=project.id,
            title=title.strip(),
            category=category,
            component=component,
            status=status,
            severity=severity,
            confidence=max(0.0, min(1.0, confidence)),
            hypothesis=hypothesis,
            impact=impact,
            remediation=remediation,
            location=location,
            cwe=cwe,
            owasp=owasp,
        )
        self.session.add(finding)
        self.session.flush()
        self.session.add(
            StateChange(
                finding_id=finding.id,
                from_status=FindingStatus.INFO,
                to_status=status,
                reason="creazione del finding",
                actor=actor,
            )
        )
        for item in evidence or []:
            self.add_evidence(finding.id, **item)
        self.session.flush()
        return finding

    def add_evidence(
        self,
        finding_id: int,
        *,
        kind: EvidenceKind = EvidenceKind.MANUAL_NOTE,
        payload: str = "",
        observed: str = "",
        source: str = "",
    ) -> FindingEvidence:
        """Aggiunge un'evidenza. I segreti vengono redatti prima di salvare."""
        evidence = FindingEvidence(
            finding_id=finding_id,
            kind=kind,
            payload=redact(str(payload)),
            observed=redact(str(observed)),
            source=redact(str(source))[:300],
        )
        self.session.add(evidence)
        self.session.flush()
        return evidence

    # -- transizioni -----------------------------------------------------
    def transition(
        self,
        finding: Finding,
        new_status: FindingStatus,
        reason: str,
        actor: str = "operator",
    ) -> Finding:
        """Cambia lo stato di un finding, validando la transizione.

        Solleva :class:`ConflictError` se la transizione non e' consentita o se
        mancano le evidenze necessarie a confermare.
        """
        current = finding.status
        if new_status == current:
            raise ConflictError(
                f"il finding e' gia' in stato {current.value}",
                details={"status": current.value},
            )
        allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
        if new_status not in allowed:
            raise ConflictError(
                f"transizione non consentita: {current.value} -> {new_status.value}",
                details={
                    "from": current.value,
                    "to": new_status.value,
                    "allowed": sorted(s.value for s in allowed),
                },
            )
        if not reason.strip():
            raise ValidationError("ogni transizione di stato deve essere motivata")
        if new_status is FindingStatus.CONFIRMED and not finding.evidences:
            raise ValidationError(
                "per confermare un finding servono almeno un'evidenza registrata"
            )
        if new_status is FindingStatus.FIXED and not finding.evidences:
            raise ValidationError(
                "per dichiarare un finding FIXED serve un test di regressione come evidenza"
            )

        finding.status = new_status
        self.session.add(
            StateChange(
                finding_id=finding.id,
                from_status=current,
                to_status=new_status,
                reason=reason.strip(),
                actor=actor,
            )
        )
        self.session.flush()
        return finding

    def confirm(
        self,
        finding: Finding,
        evidence_items: list[dict],
        reason: str,
        actor: str = "operator",
    ) -> Finding:
        """Conferma un finding allegando le evidenze raccolte."""
        for item in evidence_items:
            self.add_evidence(finding.id, **item)
        self.session.flush()
        return self.transition(finding, FindingStatus.CONFIRMED, reason, actor)

    def mark_fixed(self, finding: Finding, reason: str, actor: str = "operator") -> Finding:
        """Dichiara un finding corretto e verificato da test di regressione."""
        return self.transition(finding, FindingStatus.FIXED, reason, actor)

    def summary(self, project_id: int) -> dict:
        """Riepilogo quantitativo per la dashboard."""
        findings = self.list_findings(project_id)
        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for finding in findings:
            by_status[finding.status.value] = by_status.get(finding.status.value, 0) + 1
            by_severity[finding.severity.value] = by_severity.get(finding.severity.value, 0) + 1
        confirmed = by_status.get(FindingStatus.CONFIRMED.value, 0)
        return {
            "total": len(findings),
            "by_status": by_status,
            "by_severity": by_severity,
            "confirmed": confirmed,
            "open": len(findings) - confirmed,
        }
