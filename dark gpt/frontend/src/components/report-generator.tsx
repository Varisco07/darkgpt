"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";

/** Generazione di un report a partire dai finding registrati. */
export function ReportGenerator({ projectId }: { projectId: number }) {
  const router = useRouter();
  const [format, setFormat] = useState<"MARKDOWN" | "HTML" | "JSON">("MARKDOWN");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function generate() {
    setBusy(true);
    setMessage(null);
    try {
      const report = await api.createReport(projectId, format);
      setMessage(`Report #${report.id} generato (${report.format}).`);
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Generazione non riuscita");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <select
        value={format}
        onChange={(event) => setFormat(event.target.value as typeof format)}
        className="rounded border border-edge bg-base px-2 py-1.5 text-sm text-slate-100"
      >
        <option value="MARKDOWN">Markdown</option>
        <option value="HTML">HTML</option>
        <option value="JSON">JSON</option>
      </select>
      <button
        type="button"
        onClick={generate}
        disabled={busy}
        className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-base disabled:opacity-50"
      >
        {busy ? "Generazione…" : "Genera report"}
      </button>
      {message ? <span className="text-xs text-slate-400">{message}</span> : null}
    </div>
  );
}
