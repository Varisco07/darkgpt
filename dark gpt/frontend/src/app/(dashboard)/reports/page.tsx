import { ReportGenerator } from "@/components/report-generator";
import { Badge, Notice, Panel } from "@/components/ui";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Reports: generazione ed esportazione. */
export default async function ReportsPage({
  searchParams,
}: {
  searchParams: { project?: string };
}) {
  const projectId = Number(searchParams.project ?? 0);

  if (!projectId) {
    return (
      <Notice tone="info">
        Seleziona un progetto dalla barra in alto per generare un report.
      </Notice>
    );
  }

  let reports: Awaited<ReturnType<typeof api.listReports>> = [];
  let error: string | null = null;
  try {
    reports = await api.listReports(projectId);
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Errore sconosciuto";
  }

  const latest = reports[0];

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-100">Reports</h1>
        <p className="text-sm text-slate-400">
          I report contengono solo i dati registrati: dove un dato manca, e' scritto
          esplicitamente.
        </p>
      </header>

      {error ? <Notice tone="danger">{error}</Notice> : null}

      <Panel title="Genera un report">
        <ReportGenerator projectId={projectId} />
      </Panel>

      {latest ? (
        <Panel
          title={`Report #${latest.id} (${latest.format})`}
          description={`Generato il ${new Date(latest.created_at).toLocaleString("it-IT")}`}
          actions={
            <a
              href={`/api/projects/${projectId}/reports/${latest.id}/download`}
              className="rounded border border-edge px-2 py-1 text-xs text-slate-300 hover:border-accent hover:text-accent"
            >
              Scarica
            </a>
          }
        >
          <pre className="max-h-96 overflow-auto rounded border border-edge bg-base p-3 font-mono text-xs whitespace-pre-wrap text-slate-300">
            {latest.content}
          </pre>
        </Panel>
      ) : null}

      <Panel title="Report precedenti">
        {reports.length === 0 ? (
          <p className="text-sm text-slate-500">Nessun report generato.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {reports.map((report) => (
              <li
                key={report.id}
                className="flex items-center justify-between rounded border border-edge px-2 py-1"
              >
                <span className="text-slate-300">
                  #{report.id} · {new Date(report.created_at).toLocaleString("it-IT")}
                </span>
                <Badge tone="info">{report.format}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
