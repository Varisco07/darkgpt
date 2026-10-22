"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";
import type { ToolDescribe, ToolRunResult } from "@/lib/types";

/**
 * Avvio di una scansione.
 *
 * Le operazioni che richiedono conferma mostrano un riepilogo e non partono
 * finche' l'operatore non conferma esplicitamente.
 */
export function Scanner({ projectId, tools }: { projectId: number; tools: ToolDescribe[] }) {
  const router = useRouter();
  const [toolName, setToolName] = useState(
    tools.find((tool) => tool.availability === "available")?.name ?? tools[0]?.name ?? "",
  );
  const [path, setPath] = useState(".");
  const [advancedInput, setAdvancedInput] = useState("");
  const [result, setResult] = useState<ToolRunResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const tool = tools.find((item) => item.name === toolName);

  /** Compone l'input del tool: il JSON avanzato ha la precedenza sul path. */
  function buildInput(): Record<string, unknown> {
    const trimmed = advancedInput.trim();
    if (trimmed) {
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          return parsed as Record<string, unknown>;
        }
        setMessage("L'input JSON deve essere un oggetto.");
        return {};
      } catch {
        setMessage("L'input JSON non e' valido.");
        return {};
      }
    }
    return { path };
  }

  async function run(confirm: boolean) {
    setBusy(true);
    setMessage(null);
    try {
      const outcome = await api.runTool(projectId, {
        tool: toolName,
        input: buildInput(),
        confirm,
      });
      setResult(outcome);
      setMessage(
        outcome.status === "SUCCESS"
          ? "Scansione completata."
          : `Scansione terminata con stato ${outcome.status}.`,
      );
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Errore durante la scansione");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="text-xs uppercase tracking-wide text-slate-400">Tool</span>
          <select
            value={toolName}
            onChange={(event) => setToolName(event.target.value)}
            className="mt-1 w-full rounded border border-edge bg-base px-2 py-1.5 text-sm text-slate-100"
          >
            {tools.map((item) => (
              <option key={item.name} value={item.name}>
                {item.name} — {item.availability}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="text-xs uppercase tracking-wide text-slate-400">
            Percorso da analizzare (tool semplici)
          </span>
          <input
            value={path}
            onChange={(event) => setPath(event.target.value)}
            className="mt-1 w-full rounded border border-edge bg-base px-2 py-1.5 font-mono text-xs text-slate-100"
          />
        </label>
      </div>

      <label className="block text-sm">
        <span className="text-xs uppercase tracking-wide text-slate-400">
          Input JSON avanzato (ha la precedenza sul percorso)
        </span>
        <textarea
          value={advancedInput}
          onChange={(event) => setAdvancedInput(event.target.value)}
          rows={4}
          placeholder='{"requests": [{"url": "http://127.0.0.1:8100/search?q=alice"}]}'
          className="mt-1 w-full rounded border border-edge bg-base px-2 py-1.5 font-mono text-xs text-slate-100"
        />
      </label>

      {tool ? (
        <div className="rounded border border-edge p-3 text-xs text-slate-400">
          <p>{tool.description}</p>
          <p className="mt-1">
            {tool.requires_scope ? "Richiede un asset in scope. " : "Non richiede scope. "}
            {tool.mutating ? "Operazione mutante: richiede conferma. " : ""}
            Timeout {tool.timeout_seconds}s.
          </p>
          <p className="mt-1 text-slate-500">{tool.availability_reason}</p>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => run(false)}
          disabled={busy || !toolName}
          className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-base disabled:opacity-50"
        >
          {busy ? "Esecuzione…" : "Avvia scansione"}
        </button>
        {tool?.mutating ? (
          <button
            type="button"
            onClick={() => run(true)}
            disabled={busy || !toolName}
            className="rounded border border-warn/60 px-3 py-1.5 text-sm text-warn disabled:opacity-50"
          >
            Avvia con conferma esplicita
          </button>
        ) : null}
        {message ? <span className="text-xs text-slate-400">{message}</span> : null}
      </div>

      {result ? (
        <div className="space-y-2">
          <p className="text-xs text-slate-400">
            Stato: <span className="font-mono text-slate-200">{result.status}</span> ·{" "}
            {result.duration_ms} ms
            {result.error ? ` · ${result.error}` : ""}
          </p>
          <pre className="max-h-96 overflow-auto rounded border border-edge bg-base p-3 font-mono text-xs text-slate-300">
            {result.output_text || "(nessun output)"}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
