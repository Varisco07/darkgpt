"""API dei progetti: CRUD, riepilogo, modalita' operativa e memoria dei file."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import func, select

from ...core.errors import ScopeRequiredError
from ...models.enums import ProjectMode
from ...models.finding import Finding
from ...models.project import FileRecord, Project
from ...models.scope import ScopePolicy
from ...models.tool_run import ToolRun
from ...schemas.project import (
    FileRecordRead,
    ProjectCreate,
    ProjectModeUpdate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
)
from ..deps import CurrentProject, DbSession

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_read(project: Project) -> ProjectRead:
    return ProjectRead.model_validate(project, from_attributes=True)


@router.get("", response_model=list[ProjectRead], summary="Elenco dei progetti")
def list_projects(session: DbSession) -> list[ProjectRead]:
    projects = session.scalars(select(Project).order_by(Project.id.desc())).all()
    return [_to_read(project) for project in projects]


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un progetto",
)
def create_project(payload: ProjectCreate, session: DbSession) -> ProjectRead:
    project = Project(
        name=payload.name,
        description=payload.description,
        mode=payload.mode,
        stack=list(payload.stack),
        root_path=payload.root_path,
    )
    session.add(project)
    session.flush()
    return _to_read(project)


@router.get("/{project_id}", response_model=ProjectRead, summary="Dettaglio progetto")
def get_project(project: CurrentProject) -> ProjectRead:
    return _to_read(project)


@router.patch(
    "/{project_id}", response_model=ProjectRead, summary="Modifica un progetto"
)
def update_project(
    payload: ProjectUpdate, project: CurrentProject, session: DbSession
) -> ProjectRead:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(project, field, value)
    session.flush()
    return _to_read(project)


@router.patch(
    "/{project_id}/mode",
    response_model=ProjectRead,
    summary="Cambia la modalita' operativa del progetto",
)
def update_mode(
    payload: ProjectModeUpdate, project: CurrentProject, session: DbSession
) -> ProjectRead:
    """Cambia la modalita' operativa.

    L'upgrade a AUTHORIZED_ASSESSMENT richiede uno scope gia' definito:
    il controllo e' effettuato dal backend, non dalla UI.
    """
    if payload.mode is ProjectMode.AUTHORIZED_ASSESSMENT:
        policy = session.scalar(
            select(ScopePolicy).where(ScopePolicy.project_id == project.id)
        )
        if policy is None or policy.asset_count == 0:
            raise ScopeRequiredError(
                "modalita' AUTHORIZED_ASSESSMENT richiede almeno una regola ALLOW "
                "in scope: importa prima una policy.",
                details={"project_id": project.id},
            )
    project.mode = payload.mode
    session.flush()
    return _to_read(project)


@router.get(
    "/{project_id}/summary",
    response_model=ProjectSummary,
    summary="Riepilogo quantitativo del progetto",
)
def project_summary(project: CurrentProject, session: DbSession) -> ProjectSummary:
    findings_total = session.scalar(
        select(func.count()).select_from(Finding).where(Finding.project_id == project.id)
    )
    findings_confirmed = session.scalar(
        select(func.count())
        .select_from(Finding)
        .where(Finding.project_id == project.id, Finding.status == "CONFIRMED")
    )
    tool_runs = session.scalar(
        select(func.count())
        .select_from(ToolRun)
        .where(ToolRun.project_id == project.id)
    )
    policy = session.scalar(
        select(ScopePolicy).where(ScopePolicy.project_id == project.id)
    )
    assets_in_scope = policy.asset_count if policy else 0
    return ProjectSummary(
        project=_to_read(project),
        findings_total=findings_total or 0,
        findings_confirmed=findings_confirmed or 0,
        findings_open=(findings_total or 0) - (findings_confirmed or 0),
        assets_in_scope=assets_in_scope,
        tool_runs=tool_runs or 0,
    )


@router.get(
    "/{project_id}/files",
    response_model=list[FileRecordRead],
    summary="File analizzati registrati per il progetto",
)
def list_files(project: CurrentProject, session: DbSession) -> list[FileRecordRead]:
    records = session.scalars(
        select(FileRecord)
        .where(FileRecord.project_id == project.id)
        .order_by(FileRecord.id.desc())
    ).all()
    return [FileRecordRead.model_validate(record, from_attributes=True) for record in records]
