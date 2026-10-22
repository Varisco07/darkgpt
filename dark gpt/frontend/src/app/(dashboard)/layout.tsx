import { Suspense } from "react";

import { NavLinks } from "@/components/nav-links";
import { ProjectPicker } from "@/components/project-picker";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";

/** Sezioni della dashboard. */
const SECTIONS = [
  { href: "/overview", label: "Overview" },
  { href: "/projects", label: "Projects" },
  { href: "/scope", label: "Scope" },
  { href: "/scanner", label: "Scanner" },
  { href: "/findings", label: "Findings" },
  { href: "/chat", label: "AI Research" },
  { href: "/tools", label: "Tool Manager" },
  { href: "/reports", label: "Reports" },
  { href: "/lab", label: "Lab" },
  { href: "/settings", label: "Settings" },
];

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let projects: Project[] = [];
  let backendError: string | null = null;
  try {
    projects = await api.listProjects();
  } catch (error) {
    backendError =
      error instanceof Error
        ? error.message
        : "Impossibile contattare il backend DarkGPT";
  }

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-56 shrink-0 border-r border-edge bg-panel/60 p-4 md:block">
        <div className="mb-6">
          <p className="text-lg font-bold tracking-tight text-slate-100">DarkGPT</p>
          <p className="text-xs text-slate-500">Security Research Platform</p>
        </div>
        <Suspense fallback={<span className="text-xs text-slate-500">caricamento…</span>}>
          <NavLinks sections={SECTIONS} />
        </Suspense>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-edge bg-panel/40 px-5 py-3">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-slate-200 md:hidden">DarkGPT</span>
            <Suspense fallback={<span className="text-xs text-slate-500">caricamento…</span>}>
              <ProjectPicker projects={projects} />
            </Suspense>
          </div>
          <Suspense fallback={null}>
            <div className="md:hidden">
              <NavLinks sections={SECTIONS} orientation="horizontal" />
            </div>
          </Suspense>
          {backendError ? (
            <p className="rounded border border-red-700/60 bg-red-950/40 px-2 py-1 text-xs text-red-200">
              Backend non raggiungibile: {backendError}
            </p>
          ) : null}
        </header>

        <main className="min-w-0 flex-1 p-5">{children}</main>
      </div>
    </div>
  );
}
