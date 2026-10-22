import { FindingList } from "@/components/finding-list";
import { Notice, Panel, Stat } from "@/components/ui";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Findings con filtri per gravita' e stato. */
export default async function FindingsPage({
  searchParams,
}: {
  searchParams: { project?: string };
}) {
  const projectId = Number(searchParams.project ?? 0);

  if (!projectId) {
    return (
      <Notice tone="info">
        Seleziona un progetto dalla barra in alto per visualizzarne i finding.
      </Notice>
    );
  }

  let findings: Awaited<ReturnType<typeof api.listFindings>> = [];
  let error: string | null = null;
  try {
    findings = await api.listFindings(projectId);
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Errore sconosciuto";
  }

  const confirmed = findings.filter((f) => f.status === "CONFIRMED").length;
  const potential = findings.filter(
    (f) => f.status === "POTENTIAL" || f.status === "NEEDS_VALIDATION",
  ).length;
  const high = findings.filter((f) => f.severity === "HIGH" || f.severity === "CRITICAL").length;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-100">Findings</h1>
        <p className="text-sm text-slate-400">
          Un finding diventa CONFIRMED solo con evidenze registrate: la conferma non e'
          un passaggio automatico.
        </p>
      </header>

      {error ? <Notice tone="danger">{error}</Notice> : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Totali" value={findings.length} />
        <Stat label="Confermati" value={confirmed} tone={confirmed ? "danger" : "neutral"} />
        <Stat label="Da validare" value={potential} tone={potential ? "warn" : "neutral"} />
        <Stat label="Gravita' alta" value={high} tone={high ? "danger" : "neutral"} />
      </div>

      <Panel title="Elenco" description="Filtra per stato; apri un finding per gestire evidenze e transizioni.">
        <FindingList projectId={projectId} findings={findings} />
      </Panel>
    </div>
  );
}
