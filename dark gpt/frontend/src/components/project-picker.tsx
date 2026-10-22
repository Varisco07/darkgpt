"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import type { Project } from "@/lib/types";

/**
 * Selettore del progetto corrente.
 *
 * Il progetto scelto viaggia nel parametro `?project=<id>`: ogni sezione
 * della dashboard resta cosi' indirizzabile e ricaricabile.
 */
export function ProjectPicker({ projects }: { projects: Project[] }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const current = searchParams.get("project");

  function select(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set("project", value);
    } else {
      params.delete("project");
    }
    startTransition(() => {
      router.replace(`?${params.toString()}`);
      router.refresh();
    });
  }

  return (
    <label className="flex items-center gap-2 text-xs text-slate-400">
      <span className="uppercase tracking-wide">Progetto</span>
      <select
        aria-label="Progetto corrente"
        className="rounded border border-edge bg-base px-2 py-1 text-sm text-slate-200 disabled:opacity-50"
        value={current ?? ""}
        disabled={isPending}
        onChange={(event) => select(event.target.value)}
      >
        <option value="">— nessuno —</option>
        {projects.map((project) => (
          <option key={project.id} value={project.id}>
            #{project.id} {project.name} ({project.mode})
          </option>
        ))}
      </select>
    </label>
  );
}
