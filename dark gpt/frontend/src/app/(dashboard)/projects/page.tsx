import { ProjectForm } from "@/components/project-form";
import { Badge, Notice, Panel, Stat } from "@/components/ui";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Gestione dei progetti di sicurezza. */
export default async function ProjectsPage() {
  let projects: Awaited<ReturnType<typeof api.listProjects>> = [];
  let error: string | null = null;

  try {
    projects = await api.listProjects();
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Errore sconosciuto";
  }

  const summaries = await Promise.all(
    projects.map(async (project) => {
      try {
        return await api.projectSummary(project.id);
      } catch {
        return null;
      }
    }),
  );

  const totalFindings = summaries.reduce((sum, item) => sum + (item?.findings_total ?? 0), 0);
  const totalConfirmed = summaries.reduce((sum, item) => sum + (item?.findings_confirmed ?? 0), 0);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-100">Projects</h1>
        <p className="text-sm text-slate-400">
          Ogni progetto raccoglie scope, finding, analisi e report.
        </p>
      </header>

      {error ? <Notice tone="danger">{error}</Notice> : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Progetti" value={projects.length} />
        <Stat label="Finding totali" value={totalFindings} />
        <Stat label="Finding confermati" value={totalConfirmed} tone={totalConfirmed ? "danger" : "neutral"} />
        <Stat
          label="Asset in scope"
          value={summaries.reduce((sum, item) => sum + (item?.assets_in_scope ?? 0), 0)}
        />
      </div>

      <Panel title="Nuovo progetto">
        <ProjectForm />
      </Panel>

      <Panel title="Progetti esistenti">
        {projects.length === 0 ? (
          <p className="text-sm text-slate-500">Nessun progetto registrato.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="py-2 pr-3">#</th>
                  <th className="py-2 pr-3">Nome</th>
                  <th className="py-2 pr-3">Modalita'</th>
                  <th className="py-2 pr-3">Finding</th>
                  <th className="py-2 pr-3">Confermati</th>
                  <th className="py-2 pr-3">Asset</th>
                  <th className="py-2 pr-3">Tool run</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project, index) => {
                  const summary = summaries[index];
                  return (
                    <tr key={project.id} className="border-t border-edge">
                      <td className="py-2 pr-3 font-mono text-xs text-slate-400">{project.id}</td>
                      <td className="py-2 pr-3 text-slate-200">{project.name}</td>
                      <td className="py-2 pr-3">
                        <Badge tone={project.mode === "PASSIVE" ? "neutral" : "info"}>
                          {project.mode}
                        </Badge>
                      </td>
                      <td className="py-2 pr-3 text-slate-300">{summary?.findings_total ?? 0}</td>
                      <td className="py-2 pr-3 text-slate-300">
                        {summary?.findings_confirmed ?? 0}
                      </td>
                      <td className="py-2 pr-3 text-slate-300">{summary?.assets_in_scope ?? 0}</td>
                      <td className="py-2 pr-3 text-slate-300">{summary?.tool_runs ?? 0}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
