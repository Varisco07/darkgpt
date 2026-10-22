"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";
import type { ScopePolicy } from "@/lib/types";

const SAMPLE = `in scope: example.com
in scope: *.example.com
in scope: https://api.example.com/v1
out of scope: admin.example.com
do not perform denial of service`;

/**
 * Gestione dello scope di un progetto.
 *
 * L'importazione sostituisce integralmente la policy precedente: le regole
 * e gli asset sono ricalcolati dal backend, non scritti a mano.
 */
export function ScopeManager({ projectId, policy }: { projectId: number; policy: ScopePolicy | null }) {
  const router = useRouter();
  const [text, setText] = useState(policy?.raw_text ?? "");
  const [target, setTarget] = useState("");
  const [technique, setTechnique] = useState("");
  const [checkResult, setCheckResult] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function importPolicy() {
    setBusy(true);
    setMessage(null);
    try {
      const updated = await api.importScope(projectId, text);
      setMessage(
        `Policy importata: ${updated.rules.length} regole, ${updated.asset_count} asset in scope.`,
      );
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Errore durante l'importazione");
    } finally {
      setBusy(false);
    }
  }

  async function checkTarget() {
    setBusy(true);
    setCheckResult(null);
    try {
      const result = await api.checkScope(projectId, target, technique);
      setCheckResult(`${result.decision} — ${result.reason}`);
    } catch (error) {
      setCheckResult(error instanceof Error ? error.message : "Errore durante la verifica");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="text-xs uppercase tracking-wide text-slate-400">
          Policy (testo libero)
        </label>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={8}
          className="mt-1 w-full rounded border border-edge bg-base px-2 py-1.5 font-mono text-xs text-slate-100"
          placeholder={SAMPLE}
        />
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={importPolicy}
            disabled={busy || text.trim().length === 0}
            className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-base disabled:opacity-50"
          >
            Importa policy
          </button>
          <button
            type="button"
            onClick={() => setText(SAMPLE)}
            className="rounded border border-edge px-3 py-1.5 text-sm text-slate-300"
          >
            Carica esempio
          </button>
          {message ? <span className="text-xs text-slate-400">{message}</span> : null}
        </div>
      </div>

      <div className="rounded border border-edge p-3">
        <p className="text-xs uppercase tracking-wide text-slate-400">
          Verifica un target (nessuna richiesta viene eseguita)
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <input
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            placeholder="https://api.example.com/v1/users"
            className="flex-1 rounded border border-edge bg-base px-2 py-1.5 font-mono text-xs text-slate-100"
          />
          <input
            value={technique}
            onChange={(event) => setTechnique(event.target.value)}
            placeholder="tecnica (opzionale)"
            className="w-48 rounded border border-edge bg-base px-2 py-1.5 text-xs text-slate-100"
          />
          <button
            type="button"
            onClick={checkTarget}
            disabled={busy || target.trim().length === 0}
            className="rounded border border-edge px-3 py-1.5 text-sm text-slate-200 disabled:opacity-50"
          >
            Verifica
          </button>
        </div>
        {checkResult ? (
          <p className="mt-2 rounded bg-base px-2 py-1 font-mono text-xs text-slate-300">
            {checkResult}
          </p>
        ) : null}
      </div>
    </div>
  );
}
