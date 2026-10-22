import type { ReactNode } from "react";

/** Badge colorato per stato o gravita'. */
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "ok" | "warn" | "danger" | "info";
}) {
  const tones: Record<string, string> = {
    neutral: "bg-slate-700/40 text-slate-300 border-slate-600",
    ok: "bg-emerald-500/15 text-emerald-300 border-emerald-600/50",
    warn: "bg-amber-500/15 text-amber-300 border-amber-600/50",
    danger: "bg-red-500/15 text-red-300 border-red-600/50",
    info: "bg-sky-500/15 text-sky-300 border-sky-600/50",
  };
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

/** Riquadro con titolo e contenuto. */
export function Panel({
  title,
  description,
  children,
  actions,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-edge bg-panel p-4">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-200">
            {title}
          </h2>
          {description ? (
            <p className="mt-1 text-xs text-slate-400">{description}</p>
          ) : null}
        </div>
        {actions}
      </header>
      {children}
    </section>
  );
}

/** Riquadro statistico. */
export function Stat({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "neutral" | "ok" | "warn" | "danger" | "info";
}) {
  const tones: Record<string, string> = {
    neutral: "text-slate-100",
    ok: "text-emerald-300",
    warn: "text-amber-300",
    danger: "text-red-300",
    info: "text-sky-300",
  };
  return (
    <div className="rounded-lg border border-edge bg-panel p-3">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${tones[tone]}`}>{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

/** Messaggio di stato (errore, avviso, informazione). */
export function Notice({
  tone = "info",
  children,
}: {
  tone?: "info" | "ok" | "warn" | "danger";
  children: ReactNode;
}) {
  const tones: Record<string, string> = {
    info: "border-sky-700/60 bg-sky-950/40 text-sky-200",
    ok: "border-emerald-700/60 bg-emerald-950/40 text-emerald-200",
    warn: "border-amber-700/60 bg-amber-950/40 text-amber-200",
    danger: "border-red-700/60 bg-red-950/40 text-red-200",
  };
  return (
    <div className={`rounded border px-3 py-2 text-sm ${tones[tone]}`}>{children}</div>
  );
}

/** Codice monospaziato. */
export function Code({ children }: { children: ReactNode }) {
  return (
    <pre className="overflow-x-auto rounded border border-edge bg-base p-3 font-mono text-xs text-slate-300">
      {children}
    </pre>
  );
}

/** Traduce lo stato di un finding in un tono visivo. */
export function statusTone(status: string): "neutral" | "ok" | "warn" | "danger" | "info" {
  switch (status) {
    case "CONFIRMED":
    case "SUCCESS":
      return "danger";
    case "FIXED":
    case "AVAILABLE":
      return "ok";
    case "POTENTIAL":
    case "NEEDS_VALIDATION":
    case "DEGRADED":
      return "warn";
    case "FALSE_POSITIVE":
      return "neutral";
    case "DENIED":
    case "UNAVAILABLE":
    case "FAILED":
    case "TIMEOUT":
    case "INVALID_INPUT":
      return "info";
    default:
      return "neutral";
  }
}

/** Traduce la gravita' in un tono visivo. */
export function severityTone(severity: string): "neutral" | "ok" | "warn" | "danger" | "info" {
  switch (severity) {
    case "CRITICAL":
    case "HIGH":
      return "danger";
    case "MEDIUM":
      return "warn";
    case "LOW":
      return "info";
    default:
      return "neutral";
  }
}
