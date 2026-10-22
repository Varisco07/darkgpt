"""Generazione dei report: Markdown, HTML e JSON.

I report contengono solo dati realmente presenti nel database. Dove un
dato non e' disponibile viene scritto esplicitamente "non disponibile",
mai riempito con supposizioni.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.enums import FindingStatus, ReportFormat
from ..models.finding import Finding
from ..models.project import Project
from ..models.scope import ScopePolicy
from .findings import FindingService

NOT_AVAILABLE = "non disponibile"


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Serializza un finding e le sue evidenze in una struttura JSON."""
    return {
        "id": finding.id,
        "title": finding.title,
        "category": finding.category or NOT_AVAILABLE,
        "component": finding.component or NOT_AVAILABLE,
        "status": finding.status.value,
        "severity": finding.severity.value,
        "confidence": finding.confidence,
        "cvss_score": finding.cvss_score,
        "cvss_vector": finding.cvss_vector or NOT_AVAILABLE,
        "cwe": finding.cwe or NOT_AVAILABLE,
        "owasp": finding.owasp or NOT_AVAILABLE,
        "location": finding.location or NOT_AVAILABLE,
        "hypothesis": finding.hypothesis or NOT_AVAILABLE,
        "impact": finding.impact or NOT_AVAILABLE,
        "remediation": finding.remediation or NOT_AVAILABLE,
        "evidences": [
            {
                "kind": evidence.kind.value,
                "payload": evidence.payload or NOT_AVAILABLE,
                "observed": evidence.observed or NOT_AVAILABLE,
                "source": evidence.source or NOT_AVAILABLE,
                "created_at": evidence.created_at.isoformat(),
            }
            for evidence in finding.evidences
        ],
        "state_changes": [
            {
                "from": change.from_status.value,
                "to": change.to_status.value,
                "reason": change.reason,
                "actor": change.actor,
                "created_at": change.created_at.isoformat(),
            }
            for change in finding.state_changes
        ],
    }


def build_report_data(project: Project, session: Session) -> dict[str, Any]:
    """Costruisce la struttura dati comune a tutti i formati di report."""
    findings = FindingService(session).list_findings(project.id)
    policy = session.scalar(
        select(ScopePolicy).where(ScopePolicy.project_id == project.id)
    )
    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for finding in findings:
        by_severity[finding.severity.value] = (
            by_severity.get(finding.severity.value, 0) + 1
        )
        by_status[finding.status.value] = by_status.get(finding.status.value, 0) + 1
    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description or NOT_AVAILABLE,
            "mode": project.mode.value,
            "stack": project.stack or [],
            "root_path": project.root_path or NOT_AVAILABLE,
            "created_at": project.created_at.isoformat(),
        },
        "scope": {
            "policy_present": policy is not None,
            "asset_count": policy.asset_count if policy else 0,
            "assets": [
                {"kind": asset.kind.value, "value": asset.value, "allowed": asset.allowed}
                for asset in (policy.assets if policy else [])
            ],
            "prohibited_techniques": list(policy.prohibited_techniques or [])
            if policy
            else [],
        },
        "summary": {
            "total_findings": len(findings),
            "by_severity": by_severity,
            "by_status": by_status,
        },
        "findings": [_finding_to_dict(finding) for finding in findings],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Il report riflette esclusivamente i dati raccolti e registrati in DarkGPT.",
            "I finding in stato POTENTIAL o NEEDS_VALIDATION non sono confermati.",
            "Nessuna prova, richiesta HTTP o screenshot e' stato inventato: "
            "le evidenze elencate sono quelle effettivamente registrate.",
        ],
    }


def render_markdown(data: dict[str, Any]) -> str:
    """Renderizza il report in Markdown."""
    project = data["project"]
    summary = data["summary"]
    lines: list[str] = []

    lines.append(f"# Report di sicurezza — {project['name']}")
    lines.append("")
    lines.append(f"**Generato il:** {data['generated_at']}")
    lines.append(f"**Modalita' operativa:** {project['mode']}")
    lines.append(f"**Asset in scope:** {data['scope']['asset_count']}")
    lines.append("")
    lines.append("## Riepilogo esecutivo")
    lines.append("")
    lines.append(
        f"Il progetto ha **{summary['total_findings']}** finding registrati. "
        "La distribuzione per gravita' e':"
    )
    lines.append("")
    if summary["by_severity"]:
        lines.append("| Gravita' | Numero |")
        lines.append("|---|---|")
        for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            if severity in summary["by_severity"]:
                lines.append(f"| {severity} | {summary['by_severity'][severity]} |")
    else:
        lines.append("Nessun finding registrato.")
    lines.append("")
    lines.append("Distribuzione per stato:")
    lines.append("")
    if summary["by_status"]:
        lines.append("| Stato | Numero |")
        lines.append("|---|---|")
        for status_value in FindingStatus:
            if status_value.value in summary["by_status"]:
                lines.append(
                    f"| {status_value.value} | {summary['by_status'][status_value.value]} |"
                )
    lines.append("")

    for index, finding in enumerate(data["findings"], start=1):
        lines.append(f"## {index}. {finding['title']}")
        lines.append("")
        lines.append(f"- **Stato:** {finding['status']}")
        lines.append(f"- **Gravita':** {finding['severity']}")
        lines.append(f"- **Categoria:** {finding['category']}")
        lines.append(f"- **Componente:** {finding['component']}")
        lines.append(f"- **CWE:** {finding['cwe']}")
        lines.append(f"- **OWASP:** {finding['owasp']}")
        lines.append(f"- **Ubicazione:** {finding['location']}")
        score = finding["cvss_score"]
        lines.append(
            f"- **CVSS:** {score if score is not None else NOT_AVAILABLE} "
            f"({finding['cvss_vector']})"
        )
        lines.append("")
        lines.append("### Descrizione tecnica")
        lines.append("")
        lines.append(finding["hypothesis"])
        lines.append("")
        lines.append("### Impatto")
        lines.append("")
        lines.append(finding["impact"])
        lines.append("")
        lines.append("### Correzione suggerita")
        lines.append("")
        lines.append(finding["remediation"])
        lines.append("")
        lines.append("### Evidenze")
        lines.append("")
        if finding["evidences"]:
            for evidence in finding["evidences"]:
                lines.append(f"- **{evidence['kind']}** — `{evidence['source']}`")
                if evidence["payload"]:
                    lines.append("")
                    lines.append("```")
                    lines.append(evidence["payload"][:4000])
                    lines.append("```")
        else:
            lines.append("Nessuna evidenza registrata.")
        lines.append("")

    lines.append("## Limiti dell'analisi")
    lines.append("")
    for limitation in data["limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def render_html(data: dict[str, Any]) -> str:
    """Renderizza il report in HTML autonomo (nessuno script esterno)."""
    project = data["project"]
    summary = data["summary"]

    def esc(value: Any) -> str:
        return html.escape(str(value))

    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="it"><head><meta charset="utf-8">',
        f"<title>Report di sicurezza — {esc(project['name'])}</title>",
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;max-width:60rem;"
        "line-height:1.6;color:#1a1a1a}table{border-collapse:collapse;margin:1rem 0}"
        "th,td{border:1px solid #ccc;padding:.4rem .7rem;text-align:left}"
        "th{background:#f4f4f4}h1{border-bottom:2px solid #333;padding-bottom:.3rem}"
        "h2{margin-top:2rem}h3{margin-bottom:.3rem}"
        "pre{background:#f6f6f6;padding:.8rem;overflow-x:auto;border-radius:4px}"
        ".meta{color:#555;font-size:.95rem}</style></head><body>",
        f"<h1>Report di sicurezza — {esc(project['name'])}</h1>",
        f'<p class="meta">Generato il {esc(data["generated_at"])} · '
        f"Modalita' {esc(project['mode'])} · "
        f'Asset in scope: {esc(data["scope"]["asset_count"])}</p>',
        "<h2>Riepilogo esecutivo</h2>",
        f"<p>Finding registrati: <strong>{esc(summary['total_findings'])}</strong></p>",
    ]

    if summary["by_severity"]:
        parts.append("<table><tr><th>Gravita'</th><th>Numero</th></tr>")
        for severity, count in summary["by_severity"].items():
            parts.append(f"<tr><td>{esc(severity)}</td><td>{esc(count)}</td></tr>")
        parts.append("</table>")

    for index, finding in enumerate(data["findings"], start=1):
        parts.append(f"<h2>{index}. {esc(finding['title'])}</h2>")
        parts.append(
            "<table><tr><th>Stato</th><th>Gravita'</th><th>Categoria</th>"
            "<th>CWE</th><th>CVSS</th></tr><tr>"
            f"<td>{esc(finding['status'])}</td><td>{esc(finding['severity'])}</td>"
            f"<td>{esc(finding['category'])}</td><td>{esc(finding['cwe'])}</td>"
            f"<td>{esc(finding['cvss_vector'])}</td></tr></table>"
        )
        parts.append("<h3>Descrizione tecnica</h3>")
        parts.append(f"<p>{esc(finding['hypothesis'])}</p>")
        parts.append("<h3>Impatto</h3>")
        parts.append(f"<p>{esc(finding['impact'])}</p>")
        parts.append("<h3>Correzione suggerita</h3>")
        parts.append(f"<p>{esc(finding['remediation'])}</p>")
        parts.append("<h3>Evidenze</h3>")
        if finding["evidences"]:
            for evidence in finding["evidences"]:
                parts.append(
                    f"<p><strong>{esc(evidence['kind'])}</strong> "
                    f"<em>{esc(evidence['source'])}</em></p>"
                )
                if evidence["payload"]:
                    parts.append(f"<pre>{esc(evidence['payload'][:4000])}</pre>")
        else:
            parts.append("<p>Nessuna evidenza registrata.</p>")

    parts.append("<h2>Limiti dell'analisi</h2><ul>")
    for limitation in data["limitations"]:
        parts.append(f"<li>{esc(limitation)}</li>")
    parts.append("</ul></body></html>")
    return "".join(parts)


def render_json(data: dict[str, Any]) -> str:
    """Renderizza il report in JSON."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def render(report_format: ReportFormat, data: dict[str, Any]) -> str:
    """Renderizza il report nel formato richiesto."""
    if report_format is ReportFormat.MARKDOWN:
        return render_markdown(data)
    if report_format is ReportFormat.HTML:
        return render_html(data)
    return render_json(data)
