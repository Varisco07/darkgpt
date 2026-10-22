import { Badge, Notice, Panel, Stat } from "@/components/ui";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Tool Manager: catalogo, disponibilita' reale e requisiti. */
export default async function ToolsPage() {
  let tools: Awaited<ReturnType<typeof api.listTools>> = [];
  let error: string | null = null;
  try {
    tools = await api.listTools();
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Errore sconosciuto";
  }

  const available = tools.filter((tool) => tool.availability === "available");
  const unavailable = tools.filter((tool) => tool.availability !== "available");

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-100">Tool Manager</h1>
        <p className="text-sm text-slate-400">
          La disponibilita' e' verificata realmente: un tool assente e' dichiarato tale,
          con il comando di installazione.
        </p>
      </header>

      {error ? <Notice tone="danger">{error}</Notice> : null}

      <div className="grid grid-cols-3 gap-3">
        <Stat label="Totali" value={tools.length} />
        <Stat label="Disponibili" value={available.length} tone="ok" />
        <Stat label="Non disponibili" value={unavailable.length} tone={unavailable.length ? "warn" : "neutral"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {tools.map((tool) => (
          <Panel
            key={tool.name}
            title={tool.name}
            description={tool.description}
            actions={
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
            }
          >
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <dt className="text-slate-500">Categoria</dt>
              <dd className="text-slate-300">{tool.category}</dd>
              <dt className="text-slate-500">Tecnica</dt>
              <dd className="text-slate-300">{tool.technique || "n/d"}</dd>
              <dt className="text-slate-500">Richiede scope</dt>
              <dd className="text-slate-300">{tool.requires_scope ? "si" : "no"}</dd>
              <dt className="text-slate-500">Operazione mutante</dt>
              <dd className="text-slate-300">{tool.mutating ? "si (richiede conferma)" : "no"}</dd>
              <dt className="text-slate-500">Timeout</dt>
              <dd className="text-slate-300">{tool.timeout_seconds}s</dd>
              <dt className="text-slate-500">Versione</dt>
              <dd className="truncate font-mono text-slate-300">{tool.version || "n/d"}</dd>
            </dl>
            <p className="mt-2 text-xs text-slate-500">{tool.availability_reason}</p>
            {tool.install_hint ? (
              <p className="mt-2 rounded bg-base px-2 py-1 font-mono text-xs text-slate-400">
                {tool.install_hint}
              </p>
            ) : null}
            <details className="mt-2 text-xs">
              <summary className="cursor-pointer text-slate-500">Schema di input</summary>
              <pre className="mt-1 overflow-x-auto rounded bg-base p-2 font-mono text-slate-400">
                {JSON.stringify(tool.input_schema, null, 2)}
              </pre>
            </details>
          </Panel>
        ))}
      </div>
    </div>
  );
}
