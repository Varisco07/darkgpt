"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";
import type { Finding, FindingStatus } from "@/lib/types";

const STATUSES: FindingStatus[] = [
  "INFO",
  "POTENTIAL",
  "NEEDS_VALIDATION",
  "CONFIRMED",
  "FALSE_POSITIVE",
  "FIXED",
];

/**
 * Elenco dei finding con filtro per stato.
 *
 * Le transizioni passano dal backend, che applica la macchina a stati: la UI
 * non puo' saltare gli stati consentiti ne' confermare senza evidenze.
 */
export function FindingList({ projectId, findings }: { projectId: number; findings: Finding[] }) {
  const router = useRouter();
  const [filter, setFilter] = useState<FindingStatus | "ALL">("ALL");
  const [openId, setOpenId] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const visible = filter === "ALL" ? findings : findings.filter((f) => f.status === filter);

  async function transition(finding: Finding, status: FindingStatus) {
    setBusy(true);
    setMessage(null);
    try {
      await api.transitionFinding(projectId, finding.id, {
        status,
        reason: reason.trim() || `Transizione manuale a ${status}`,
        evidence: evidence.trim()
          ? [{ kind: "MANUAL_NOTE", payload: evidence.trim(), source: "dashboard" }]
          : [],
      });
      setMessage(`Finding #${finding.id}: stato aggiornato a ${status}.`);
      setReason("");
      setEvidence("");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Transizione non riuscita");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setFilter("ALL")}
          className={`rounded border px-2 py-1 text-xs ${
            filter === "ALL" ? "border-accent text-accent" : "border-edge text-slate-400"
          }`}
        >
          Tutti ({findings.length})
        </button>
        {STATUSES.map((status) => {
          const count = findings.filter((finding) => finding.status === status).length;
          if (count === 0) return null;
          return (
            <button
              key={status}
              type="button"
              onClick={() => setFilter(status)}
              className={`rounded border px-2 py-1 text-xs ${
                filter === status ? "border-accent text-accent" : "border-edge text-slate-400"
              }`}
            >
              {status} ({count})
            </button>
          );
        })}
      </div>

      {message ? <p className="text-xs text-slate-400">{message}</p> : null}

      <ul className="space-y-2">
        {visible.map((finding) => (
          <li key={finding.id} className="rounded border border-edge">
            <button
              type="button"
              onClick={() => setOpenId(openId === finding.id ? null : finding.id)}
              className="flex w-full flex-wrap items-center justify-between gap-2 px-3 py-2 text-left"
            >
              <span className="text-sm text-slate-200">
                #{finding.id} {finding.title}
              </span>
              <span className="flex items-center gap-2 text-xs text-slate-400">
                {finding.severity}
                <span className="rounded border border-edge px-1.5 py-0.5">{finding.status}</span>
              </span>
            </button>

            {openId === finding.id ? (
              <FindingDetail
                finding={finding}
                reason={reason}
                evidence={evidence}
                busy={busy}
                onReasonChange={setReason}
                onEvidenceChange={setEvidence}
                onTransition={(status) => transition(finding, status)}
              />
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Dettaglio espandibile di un finding: descrizione, evidenze, transizioni. */
function FindingDetail({
  finding,
  reason,
  evidence,
  busy,
  onReasonChange,
  onEvidenceChange,
  onTransition,
}: {
  finding: Finding;
  reason: string;
  evidence: string;
  busy: boolean;
  onReasonChange: (value: string) => void;
  onEvidenceChange: (value: string) => void;
  onTransition: (status: FindingStatus) => void;
}) {
  return (
    <div className="space-y-3 border-t border-edge px-3 py-3 text-sm">
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Ipotesi</p>
          <p className="mt-1 whitespace-pre-wrap text-slate-300">
            {finding.hypothesis || "non disponibile"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Impatto</p>
          <p className="mt-1 whitespace-pre-wrap text-slate-300">
            {finding.impact || "non disponibile"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Correzione</p>
          <p className="mt-1 whitespace-pre-wrap text-slate-300">
            {finding.remediation || "non disponibile"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Evidenze</p>
          {finding.evidences.length === 0 ? (
            <p className="mt-1 text-slate-500">
              Nessuna evidenza: la conferma non e' possibile.
            </p>
          ) : (
            <ul className="mt-1 space-y-1">
              {finding.evidences.map((item) => (
                <li key={item.id} className="rounded bg-base px-2 py-1 text-xs">
                  <span className="text-slate-500">{item.kind}</span>{" "}
                  <span className="font-mono text-slate-300">
                    {item.payload?.slice(0, 200)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="rounded border border-edge p-2">
        <p className="text-xs uppercase tracking-wide text-slate-500">
          Cambia stato (motivazione obbligatoria)
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <input
            value={reason}
            onChange={(event) => onReasonChange(event.target.value)}
            placeholder="motivazione della transizione"
            className="flex-1 rounded border border-edge bg-base px-2 py-1 text-xs text-slate-100"
          />
          <input
            value={evidence}
            onChange={(event) => onEvidenceChange(event.target.value)}
            placeholder="evidenza (opzionale)"
            className="flex-1 rounded border border-edge bg-base px-2 py-1 text-xs text-slate-100"
          />
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {STATUSES.filter((status) => status !== finding.status).map((status) => (
            <button
              key={status}
              type="button"
              disabled={busy}
              onClick={() => onTransition(status)}
              className="rounded border border-edge px-2 py-1 text-xs text-slate-300 disabled:opacity-50 hover:border-accent hover:text-accent"
            >
              → {status}
            </button>
          ))}
        </div>
      </div>

      {finding.state_changes.length > 0 ? (
        <details className="text-xs text-slate-400">
          <summary className="cursor-pointer">
            Cronologia delle transizioni ({finding.state_changes.length})
          </summary>
          <ul className="mt-1 space-y-1">
            {finding.state_changes.map((change) => (
              <li key={change.id} className="rounded bg-base px-2 py-1">
                {change.from_status} → {change.to_status}: {change.reason} ({change.actor})
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
