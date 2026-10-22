"""API dei report: generazione, elenco e download."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select

from ...models.enums import ReportFormat
from ...models.project import Report
from ...schemas.project import ReportRead
from ...services.reports import build_report_data, render
from ..deps import CurrentProject, DbSession

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])

#: Content type per formato di report.
CONTENT_TYPES = {
    ReportFormat.MARKDOWN: "text/markdown; charset=utf-8",
    ReportFormat.HTML: "text/html; charset=utf-8",
    ReportFormat.JSON: "application/json; charset=utf-8",
}

#: Estensione del file per formato di report.
FILE_EXTENSIONS = {
    ReportFormat.MARKDOWN: "md",
    ReportFormat.HTML: "html",
    ReportFormat.JSON: "json",
}


@router.get("", response_model=list[ReportRead], summary="Elenco dei report")
def list_reports(project: CurrentProject, session: DbSession) -> list[ReportRead]:
    reports = session.scalars(
        select(Report)
        .where(Report.project_id == project.id)
        .order_by(Report.id.desc())
    ).all()
    return [ReportRead.model_validate(report, from_attributes=True) for report in reports]


@router.post(
    "",
    response_model=ReportRead,
    status_code=status.HTTP_201_CREATED,
    summary="Genera un report per il progetto",
)
def create_report(
    project: CurrentProject,
    session: DbSession,
    report_format: ReportFormat = Query(
        default=ReportFormat.MARKDOWN, alias="format"
    ),
) -> ReportRead:
    """Genera un report a partire dai finding registrati.

    Il report non contiene nulla che non sia gia' presente in database.
    """
    data = build_report_data(project, session)
    content = render(report_format, data)
    report = Report(
        project_id=project.id,
        format=report_format,
        content=content,
    )
    session.add(report)
    session.flush()
    return ReportRead.model_validate(report, from_attributes=True)


@router.get(
    "/{report_id}/download",
    summary="Scarica il contenuto di un report",
    response_class=Response,
)
def download_report(
    project: CurrentProject, session: DbSession, report_id: int
) -> Response:
    report = session.get(Report, report_id)
    if report is None or report.project_id != project.id:
        from ...core.errors import NotFoundError

        raise NotFoundError(
            f"report {report_id} non trovato nel progetto {project.id}",
            details={"project_id": project.id, "report_id": report_id},
        )
    filename = f"darkgpt-report-{project.id}-{report.id}.{FILE_EXTENSIONS[report.format]}"
    return Response(
        content=report.content,
        media_type=CONTENT_TYPES[report.format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
