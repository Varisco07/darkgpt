import { Badge, Notice, Panel } from "@/components/ui";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Settings: stato del provider LLM, limiti operativi e log. */
export default async function SettingsPage() {
  let llm = null;
  let limits: Record<string, number | string> | null = null;
  let logs: unknown[] = [];
  let error: string | null = null;

  try {
    llm = await api.llmStatus();
    limits = await api.limits();
    logs = await api.logs(50);
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Errore sconosciuto";
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-100">Settings</h1>
        <p className="text-sm text-slate-400">
          Configurazione del provider, limiti operativi in vigore e log recenti.
        </p>
      </header>

      {error ? <Notice tone="danger">{error}</Notice> : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel
          title="Provider LLM"
          description="La chiave API non viene mai mostrata: e' indicata solo la presenza."
        >
          {llm ? (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <dt className="text-slate-500">Provider</dt>
              <dd className="text-slate-200">{llm.provider}</dd>
              <dt className="text-slate-500">Endpoint</dt>
              <dd className="truncate font-mono text-xs text-slate-300">{llm.base_url}</dd>
              <dt className="text-slate-500">Modello</dt>
              <dd className="text-slate-200">{llm.model}</dd>
              <dt className="text-slate-500">Chiave API impostata</dt>
              <dd>
                <Badge tone={llm.api_key_set ? "ok" : "neutral"}>
                  {llm.api_key_set ? "si" : "no"}
                </Badge>
              </dd>
              <dt className="text-slate-500">Configurato</dt>
              <dd>
                <Badge tone={llm.configured ? "ok" : "warn"}>
                  {llm.configured ? "si" : "no (modalita' mock dichiarata)"}
                </Badge>
              </dd>
              <dt className="text-slate-500">Temperatura</dt>
              <dd className="text-slate-200">{llm.temperature}</dd>
              <dt className="text-slate-500">Token massimi</dt>
              <dd className="text-slate-200">{llm.max_tokens}</dd>
              <dt className="text-slate-500">Timeout</dt>
              <dd className="text-slate-200">{llm.timeout}s</dd>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">Stato non disponibile.</p>
          )}
          <p className="mt-3 rounded bg-base px-2 py-1 font-mono text-xs text-slate-400">
            DARKGPT_LLM_BASE_URL, DARKGPT_LLM_API_KEY, DARKGPT_LLM_MODEL
          </p>
        </Panel>

        <Panel title="Limiti operativi" description="Valori in vigore nel backend.">
          {limits ? (
            <ul className="space-y-1 text-sm">
              {Object.entries(limits).map(([key, value]) => (
                <li key={key} className="flex justify-between gap-4">
                  <span className="font-mono text-xs text-slate-400">{key}</span>
                  <span className="text-slate-200">{String(value)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">Limiti non disponibili.</p>
          )}
        </Panel>
      </div>

      <Panel
        title="Log recenti"
        description="Buffer in memoria: volatile, non e' un archivio di audit. La fonte autorevole e' la tabella tool_runs."
      >
        {logs.length === 0 ? (
          <p className="text-sm text-slate-500">Nessun log in memoria.</p>
        ) : (
          <ul className="max-h-80 space-y-1 overflow-y-auto text-xs">
            {logs.map((entry, index) => {
              const item = entry as {
                ts?: string;
                level?: string;
                event?: string;
                logger?: string;
              };
              return (
                <li key={index} className="rounded bg-base px-2 py-1 font-mono text-slate-400">
                  <span className="text-slate-500">{item.ts}</span>{" "}
                  <span className="text-slate-300">{item.level}</span> {item.event}
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
