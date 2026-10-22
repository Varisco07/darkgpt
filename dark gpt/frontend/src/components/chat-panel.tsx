"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

/**
 * Chat tecnica con il contesto del progetto.
 *
 * Le risposte simulate (provider non configurato) sono marcate: la UI non
 * presenta come reale un output prodotto dal provider di fallback.
 */
export function ChatPanel({
  projectId,
  messages,
  providerConfigured,
}: {
  projectId: number;
  messages: ChatMessage[];
  providerConfigured: boolean;
}) {
  const [text, setText] = useState("");
  const [history, setHistory] = useState<ChatMessage[]>(messages);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    if (!text.trim()) return;
    const outgoing = text.trim();
    setText("");
    setBusy(true);
    setError(null);
    setHistory((current) => [
      ...current,
      {
        id: -Date.now(),
        project_id: projectId,
        role: "user",
        content: outgoing,
        tool_calls: {},
        simulated: false,
        created_at: new Date().toISOString(),
      },
    ]);
    try {
      const answer = await api.sendChat(projectId, outgoing);
      setHistory((current) => [...current, answer]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Errore durante l'invio");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <p className="rounded border border-edge px-3 py-2 text-xs text-slate-400">
        {providerConfigured
          ? "Le risposte sono prodotte dal provider configurato e usano il contesto del progetto (scope, finding, esecuzioni)."
          : "Provider LLM non configurato: le risposte provengono dal provider di fallback dichiarato e sono marcate come simulate."}
      </p>

      <div className="max-h-[28rem] space-y-2 overflow-y-auto rounded border border-edge p-3">
        {history.length === 0 ? (
          <p className="text-sm text-slate-500">Nessun messaggio: inizia con una domanda.</p>
        ) : (
          history.map((message) => (
            <div
              key={message.id}
              className={`rounded px-3 py-2 text-sm ${
                message.role === "user"
                  ? "bg-edge/40 text-slate-100"
                  : "bg-base text-slate-300"
              }`}
            >
              <p className="mb-1 text-[10px] uppercase tracking-wide text-slate-500">
                {message.role}
                {message.simulated ? " · risposta simulata" : ""}
              </p>
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
          ))
        )}
        {busy ? <p className="text-xs text-slate-500">elaborazione…</p> : null}
      </div>

      {error ? <p className="text-xs text-red-300">{error}</p> : null}

      <div className="flex gap-2">
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void send();
            }
          }}
          rows={3}
          placeholder="Analizza il codice, proponi un test di verifica, prepara una sezione di report…"
          className="flex-1 rounded border border-edge bg-base px-2 py-1.5 text-sm text-slate-100"
        />
        <button
          type="button"
          onClick={() => void send()}
          disabled={busy || !text.trim()}
          className="self-end rounded bg-accent px-3 py-1.5 text-sm font-medium text-base disabled:opacity-50"
        >
          Invia
        </button>
      </div>
    </div>
  );
}
