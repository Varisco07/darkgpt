import { ScopeManager } from "@/components/scope-manager";
import { Badge, Notice, Panel } from "@/components/ui";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Scope Manager: policy, regole, asset e verifica dei target. */
export default async function ScopePage({
  searchParams,
}: {
  searchParams: { project?: string };
}) {
  const projectId = Number(searchParams.project ?? 0);

  if (!projectId) {
    return (
      <Notice tone="info">
        Seleziona un progetto dalla barra in alto per gestirne lo scope.
      </Notice>
    );
  }

  let policy = null;
  let project = null;
  let error: string | null = null;
  try {
    policy = await api.getScope(projectId);
    project = await api.getProject(projectId);
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Errore sconosciuto";
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-100">Scope</h1>
        <p className="text-sm text-slate-400">
          {project ? `Progetto #${project.id} — ${project.name}` : "Scope del progetto"} · modalita'
          {project ? ` ${project.mode}` : ""}
        </p>
      </header>

      {error ? <Notice tone="danger">{error}</Notice> : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel
          title="Policy"
          description="Gli asset sono derivati dalle regole: non si inseriscono a mano."
        >
          <ScopeManager projectId={projectId} policy={policy} />
        </Panel>

        <div className="space-y-5">
          <Panel
            title="Regole"
            description="Le regole DENY prevalgono sempre sulle regole ALLOW."
          >
            {!policy || policy.rules.length === 0 ? (
              <p className="text-sm text-slate-500">Nessuna regola definita.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {policy.rules.map((rule) => (
                  <li
                    key={rule.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded border border-edge px-2 py-1"
                  >
                    <span className="font-mono text-xs text-slate-200">{rule.pattern}</span>
                    <span className="flex items-center gap-2">
                      <Badge tone="neutral">{rule.kind}</Badge>
                      <Badge tone={rule.effect === "ALLOW" ? "ok" : "danger"}>{rule.effect}</Badge>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Asset in scope" description="Derivati dalle regole ALLOW.">
            {!policy || policy.assets.length === 0 ? (
              <p className="text-sm text-slate-500">
                Nessun asset: il progetto opera in deny-by-default.
              </p>
            ) : (
              <ul className="space-y-1 text-sm">
                {policy.assets.map((asset) => (
                  <li
                    key={asset.id}
                    className="flex items-center justify-between rounded border border-edge px-2 py-1"
                  >
                    <span className="font-mono text-xs text-slate-200">{asset.value}</span>
                    <Badge tone="ok">{asset.kind}</Badge>
                  </li>
                ))}
              </ul>
            )}
            {policy && policy.prohibited_techniques.length > 0 ? (
              <div className="mt-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Tecniche vietate dalla policy
                </p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {policy.prohibited_techniques.map((item) => (
                    <Badge key={item} tone="danger">
                      {item}
                    </Badge>
                  ))}
                </div>
              </div>
            ) : null}
          </Panel>
        </div>
      </div>
    </div>
  );
}
