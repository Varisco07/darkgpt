"""API dello Scope Manager: import policy, regole, asset e verifica dei target."""

from __future__ import annotations

from fastapi import APIRouter, status

from ...schemas.scope import (
    ScopeAssetRead,
    ScopeCheckRequest,
    ScopeCheckResponse,
    ScopePolicyImport,
    ScopePolicyRead,
    ScopeRuleCreate,
    ScopeRuleRead,
)
from ...services.scope import ScopeService
from ..deps import CurrentProject, DbSession

router = APIRouter(prefix="/projects/{project_id}/scope", tags=["scope"])


def _policy_read(service: ScopeService, project_id: int) -> ScopePolicyRead | None:
    policy = service.get_policy(project_id)
    if policy is None:
        return None
    rules = service.get_rules(project_id)
    assets = service.get_assets(project_id)
    return ScopePolicyRead(
        id=policy.id,
        project_id=policy.project_id,
        raw_text=policy.raw_text,
        notes=policy.notes,
        asset_count=policy.asset_count,
        prohibited_techniques=list(policy.prohibited_techniques or []),
        rules=[
            ScopeRuleRead(
                id=rule.id,
                kind=rule.kind,
                effect=rule.effect,
                pattern=rule.pattern,
                technique=rule.technique,
                notes=rule.notes,
            )
            for rule in rules
        ],
        assets=[
            ScopeAssetRead(
                id=asset.id,
                kind=asset.kind,
                value=asset.value,
                allowed=asset.allowed,
                technique=asset.technique,
                notes=asset.notes,
            )
            for asset in assets
        ],
        created_at=policy.created_at,
    )


@router.get(
    "",
    response_model=ScopePolicyRead | None,
    summary="Policy di scope del progetto",
)
def get_policy(project: CurrentProject, session: DbSession) -> ScopePolicyRead | None:
    return _policy_read(ScopeService(session), project.id)


@router.post(
    "/import",
    response_model=ScopePolicyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Importa (o sostituisce) la policy di scope da testo",
)
def import_policy(
    payload: ScopePolicyImport, project: CurrentProject, session: DbSession
) -> ScopePolicyRead:
    """Importa la policy.

    Il testo viene analizzato dal Scope Manager: le regole e gli asset sono
    derivati, non inseriti direttamente. Sostituisce integralmente la
    policy precedente.
    """
    service = ScopeService(session)
    service.import_policy(project.id, payload.text, payload.notes)
    session.flush()
    result = _policy_read(service, project.id)
    assert result is not None  # la policy e' stata appena creata
    return result


@router.post(
    "/rules",
    response_model=ScopeRuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Aggiunge una regola di scope puntuale",
)
def add_rule(
    payload: ScopeRuleCreate, project: CurrentProject, session: DbSession
) -> ScopeRuleRead:
    service = ScopeService(session)
    rule = service.add_rule(
        project.id,
        kind=payload.kind,
        effect=payload.effect,
        pattern=payload.pattern,
        technique=payload.technique,
        notes=payload.notes,
    )
    session.flush()
    return ScopeRuleRead(
        id=rule.id,
        kind=rule.kind,
        effect=rule.effect,
        pattern=rule.pattern,
        technique=rule.technique,
        notes=rule.notes,
    )


@router.post(
    "/check",
    response_model=ScopeCheckResponse,
    summary="Verifica se un target e' in scope",
)
def check_target(
    payload: ScopeCheckRequest, project: CurrentProject, session: DbSession
) -> ScopeCheckResponse:
    """Valuta un target senza eseguire nulla.

    La decisione e' deny-by-default: senza regole ALLOW il target e' fuori
    scope anche in modalita' AUTHORIZED_ASSESSMENT.
    """
    result = ScopeService(session).evaluate(project, payload.target, payload.technique)
    return ScopeCheckResponse(
        decision=result.decision.value,
        reason=result.reason,
        matched_rule_id=result.matched_rule_id,
        matched_pattern=result.matched_pattern,
        requires_confirmation=result.requires_confirmation,
        prohibited=list(result.prohibited),
    )
