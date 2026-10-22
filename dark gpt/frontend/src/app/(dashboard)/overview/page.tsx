import { Badge, Notice, Panel, Stat } from "@/components/ui";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Panoramica: stato del backend, dei tool e dei progetti. */
export default async function OverviewPage() {
  let health = null;
  let tools: Awaited<ReturnType<typeof api.listTools>> = [];
  let projects: Awaited<ReturnType<typeof api.listProjects>> = [];
  let error: string | null = null;

  try {
    health = await api.health();
    tools = await api.listTools();
    projects = await api.listProjects();
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Errore sconosciuto";
  }

  const available = tools.filter((tool) => tool.availability === "available");

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-100">Panoramica</h1>
        <p className="text-sm text-slate-400">
          Stato del backend, disponibilita' dei tool e riepilogo dei progetti.
        </p>
      </header>

      {error ? (
        <Notice tone="danger">
          Backend non raggiungibile: {error}. Verifica che il server sia avviato su
          <code className="mx-1 rounded bg-base px-1">127.0.0.1:8000</code>.
        </Notice>
      ) : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="Stato backend"
          value={health?.status ?? "n/d"}
          tone={health?.status === "ok" ? "ok" : "danger"}
          hint={health ? `v${health.version}` : undefined}
        />
        <Stat
          label="Database"
          value={health?.database ?? "n/d"}
          tone={health?.database === "ok" ? "ok" : "danger"}
        />
        <Stat
          label="Tool disponibili"
          value={`${available.length}/${tools.length}`}
          tone={available.length === tools.length ? "ok" : "warn"}
          hint="I tool assenti dichiarano la ragione"
        />
        <Stat
          label="Progetti"
          value={projects.length}
          hint={`${projects.filter((p) => p.mode !== "PASSIVE").length} in modalita' attiva`}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel
          title="Provider LLM"
          description="Il modello e' opzionale: senza provider le funzioni di analisi restano disponibili."
        >
          {health ? (
            <ul className="space-y-2 text-sm">
              <li className="flex items-center justify-between">
                <span className="text-slate-400">Provider</span>
                <Badge tone={health.llm_configured ? "ok" : "warn"}>
                  {health.llm_provider}
                </Badge>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-slate-400">Configurato</span>
                <Badge tone={health.llm_configured ? "ok" : "warn"}>
                  {health.llm_configured ? "si" : "no (modalita' mock dichiarata)"}
                </Badge>
              </li>
            </ul>
          ) : (
            <p className="text-sm text-slate-500">Backend non raggiungibile.</p>
          )}
        </Panel>

        <Panel title="Progetti" description="Seleziona un progetto per filtrare le sezioni.">
          {projects.length === 0 ? (
            <p className="text-sm text-slate-500">
              Nessun progetto. Creane uno dalla sezione Projects.
            </p>
          ) : (
            <ul className="space-y-2">
              {projects.map((project) => (
                <li
                  key={project.id}
                  className="flex items-center justify-between rounded border border-edge px-3 py-2"
                >
                  <span className="text-sm text-slate-200">
                    #{project.id} {project.name}
                  </span>
                  <Badge tone={project.mode === "PASSIVE" ? "neutral" : "info"}>
                    {project.mode}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel
        title="Tool"
        description="Lo stato e' verificato realmente: un tool non installato e' dichiarato tale."
      >
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {tools.map((tool) => (
            <div key={tool.name} className="rounded border border-edge px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-slate-200">{tool.name}</span>
                <Badge
                  tone={
                    tool.availability === "available"
                      ? "ok"
                      : tool.availability === "degraded"
                        ? "warn"
                        : "danger"
                  }
                >
                  {tool.availability}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-slate-500">{tool.availability_reason}</p>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
