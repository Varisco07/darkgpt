"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";
import type { ProjectMode } from "@/lib/types";

const MODES: { value: ProjectMode; label: string; hint: string }[] = [
  {
    value: "PASSIVE",
    label: "Passive",
    hint: "Solo analisi offline: nessun test attivo.",
  },
  {
    value: "LAB",
    label: "Lab",
    hint: "Test attivi ammessi solo sui target locali del laboratorio.",
  },
  {
    value: "AUTHORIZED_ASSESSMENT",
    label: "Authorized assessment",
    hint: "Richiede uno scope importato con almeno una regola ALLOW.",
  },
];

/** Form di creazione di un progetto. */
export function ProjectForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<ProjectMode>("PASSIVE");
  const [rootPath, setRootPath] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const project = await api.createProject({
        name,
        description,
        mode,
        root_path: rootPath,
        stack: [],
      });
      setMessage(`Progetto #${project.id} creato.`);
      setName("");
      setDescription("");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Errore durante la creazione");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="text-xs uppercase tracking-wide text-slate-400">Nome</span>
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-1 w-full rounded border border-edge bg-base px-2 py-1.5 text-sm text-slate-100"
            placeholder="Es. Portale cliente"
          />
        </label>
        <label className="block text-sm">
          <span className="text-xs uppercase tracking-wide text-slate-400">
            Root dei sorgenti (opzionale)
          </span>
          <input
            value={rootPath}
            onChange={(event) => setRootPath(event.target.value)}
            className="mt-1 w-full rounded border border-edge bg-base px-2 py-1.5 font-mono text-xs text-slate-100"
            placeholder="C:\\progetti\\portal"
          />
        </label>
      </div>

      <label className="block text-sm">
        <span className="text-xs uppercase tracking-wide text-slate-400">Descrizione</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={2}
          className="mt-1 w-full rounded border border-edge bg-base px-2 py-1.5 text-sm text-slate-100"
        />
      </label>

      <fieldset className="text-sm">
        <legend className="text-xs uppercase tracking-wide text-slate-400">
          Modalita' operativa
        </legend>
        <div className="mt-2 space-y-1">
          {MODES.map((item) => (
            <label key={item.value} className="flex items-start gap-2">
              <input
                type="radio"
                name="mode"
                value={item.value}
                checked={mode === item.value}
                onChange={() => setMode(item.value)}
                className="mt-1"
              />
              <span>
                <span className="text-slate-200">{item.label}</span>
                <span className="block text-xs text-slate-500">{item.hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-base disabled:opacity-50"
        >
          {busy ? "Creazione…" : "Crea progetto"}
        </button>
        {message ? <span className="text-xs text-slate-400">{message}</span> : null}
      </div>
    </form>
  );
}
