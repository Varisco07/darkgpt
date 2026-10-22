import { ChatPanel } from "@/components/chat-panel";
import { Notice, Panel } from "@/components/ui";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/** AI Research: chat tecnica con contesto di progetto. */
export default async function ChatPage({
  searchParams,
}: {
  searchParams: { project?: string };
}) {
  const projectId = Number(searchParams.project ?? 0);

  if (!projectId) {
    return (
      <Notice tone="info">
        Seleziona un progetto dalla barra in alto per usare la chat.
      </Notice>
    );
  }

  let history = null;
  let error: string | null = null;
  try {
    history = await api.chatHistory(projectId);
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Errore sconosciuto";
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-100">AI Research</h1>
        <p className="text-sm text-slate-400">
          Chat tecnica: il contesto inviato al provider e' composed dai dati gia'
          raccolti nel progetto.
        </p>
      </header>

      {error ? <Notice tone="danger">{error}</Notice> : null}

      <Panel title="Conversazione">
        {history ? (
          <ChatPanel
            projectId={projectId}
            messages={history.messages}
            providerConfigured={history.provider_configured}
          />
        ) : (
          <p className="text-sm text-slate-500">Cronologia non disponibile.</p>
        )}
      </Panel>
    </div>
  );
}
