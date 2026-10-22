import { Scanner } from "@/components/scanner";
import { Badge, Notice, Panel } from "@/components/ui";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Scanner: avvio e monitoraggio delle analisi consentite. */
export default async function ScannerPage({
  searchParams,
}: {
  searchParams: { project?: string };
}) {
  const projectId = Number(searchParams.project ?? 0);

  if (!projectId) {
    return (
      <Notice tone="info">
        Seleziona un progetto dalla barra in alto per avviare una scansione.
      </Notice>
    );
  }

  let tools: Awaited<ReturnType<typeof api.listTools>> = [];
  let runs: Awaited<ReturnType<typeof api.listToolRuns>> = [];
  let error: string | null = null;
  try {
    tools = await api.listTools();
    runs = await api.listToolRuns(projectId);
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Errore sconosciuto";
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-100">Scanner</h1>
        <p className="text-sm text-slate-400">
          Le esecuzioni sono registrate in <code>tool_runs</code>: e' la fonte autorevole
          per l'audit.
        </p>
      </header>

      {error ? <Notice tone="danger">{error}</Notice> : null}

      <Panel title="Nuova esecuzione">
        <Scanner projectId={projectId} tools={tools} />
      </Panel>

      <Panel title="Cronologia esecuzioni">
        {runs.length === 0 ? (
          <p className="text-sm text-slate-500">Nessuna esecuzione registrata.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="py-2 pr-3">#</th>
                  <th className="py-2 pr-3">Tool</th>
                  <th className="py-2 pr-3">Stato</th>
                  <th className="py-2 pr-3">Durata</th>
                  <th className="py-2 pr-3">Hash output</th>
                  <th className="py-2 pr-3">Errore</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="border-t border-edge align-top">
                    <td className="py-2 pr-3 font-mono text-xs text-slate-400">{run.id}</td>
                    <td className="py-2 pr-3 font-mono text-xs text-slate-200">{run.tool_name}</td>
                    <td className="py-2 pr-3">
                      <Badge
                        tone={
                          run.status === "SUCCESS"
                            ? "ok"
                            : run.status === "DENIED" || run.status === "UNAVAILABLE"
                              ? "warn"
                              : "danger"
                        }
                      >
                        {run.status}
                      </Badge>
                    </td>
                    <td className="py-2 pr-3 text-slate-300">{run.duration_ms} ms</td>
                    <td className="py-2 pr-3 font-mono text-xs text-slate-500">
                      {run.output_hash.slice(0, 12)}…
                    </td>
                    <td className="py-2 pr-3 text-xs text-slate-400">{run.error_text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
