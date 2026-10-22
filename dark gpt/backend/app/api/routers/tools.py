"""API dei tool: catalogo, stato di disponibilita' ed esecuzione controllata."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from ...models.tool_run import ToolRun
from ...schemas.tool import ScanRequest, ToolDescribe, ToolRunRead, ToolRunResult
from ...tools.registry import registry
from ...tools.runner import run_tool
from ..deps import CurrentProject, DbSession

router = APIRouter(tags=["tools"])


@router.get(
    "/tools", response_model=list[ToolDescribe], summary="Catalogo dei tool"
)
def list_tools() -> list[ToolDescribe]:
    """Elenco dei tool con la loro disponibilita' reale.

    Un tool non installato e' comunque elencato, con `availability` valorizzata
    come `unavailable` e il motivo della mancanza: la UI puo' cosi' dire
    cosa installare invece di fingere che il tool esista.
    """
    return [ToolDescribe(**item) for item in registry.describe()]


@router.get(
    "/tools/{tool_name}", response_model=ToolDescribe, summary="Dettaglio di un tool"
)
def get_tool(tool_name: str) -> ToolDescribe:
    spec = registry.get(tool_name)
    described = next(item for item in registry.describe() if item["name"] == spec.name)
    return ToolDescribe(**described)


@router.post(
    "/projects/{project_id}/scans",
    response_model=ToolRunResult,
    summary="Esegue un tool del catalogo",
)
def run_scan(
    payload: ScanRequest, project: CurrentProject, session: DbSession
) -> ToolRunResult:
    """Esegue un tool applicando l'intera catena di controlli.

    Il tool viene validato, il target viene verificato contro lo scope, le
    operazioni mutanti richiedono conferma esplicita e l'esecuzione viene
    registrata in `tool_runs`.
    """
    result = run_tool(
        session,
        project,
        payload.tool,
        payload.input,
        confirm=payload.confirm,
        target=payload.target,
        technique=payload.technique,
    )
    return ToolRunResult(**result.to_dict())


@router.get(
    "/projects/{project_id}/tool-runs",
    response_model=list[ToolRunRead],
    summary="Cronologia delle esecuzioni di tool del progetto",
)
def list_tool_runs(project: CurrentProject, session: DbSession) -> list[ToolRunRead]:
    runs = session.scalars(
        select(ToolRun)
        .where(ToolRun.project_id == project.id)
        .order_by(ToolRun.id.desc())
        .limit(200)
    ).all()
    return [ToolRunRead.model_validate(run, from_attributes=True) for run in runs]
