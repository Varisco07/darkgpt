"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

export interface NavSection {
  href: string;
  label: string;
}

/**
 * Navigazione laterale che preserva il progetto selezionato.
 *
 * Il progetto corrente vive in `?project=<id>`: ogni link lo mantiene, cosi'
 * l'utente non perde il contesto passando da una sezione all'altra.
 */
export function NavLinks({
  sections,
  orientation = "vertical",
}: {
  sections: NavSection[];
  orientation?: "vertical" | "horizontal";
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const project = searchParams.get("project") ?? "";

  const base = orientation === "vertical" ? "flex flex-col gap-1" : "flex flex-wrap gap-2";

  return (
    <nav className={base}>
      {sections.map((section) => {
        const query = project ? `?project=${project}` : "";
        const active = pathname === section.href;
        return (
          <Link
            key={section.href}
            href={`${section.href}${query}`}
            aria-current={active ? "page" : undefined}
            className={
              orientation === "vertical"
                ? `rounded px-3 py-1.5 text-sm transition ${
                    active
                      ? "bg-edge text-slate-100"
                      : "text-slate-300 hover:bg-edge/60 hover:text-slate-100"
                  }`
                : `rounded px-2 py-1 text-xs transition ${
                    active
                      ? "bg-edge text-slate-100"
                      : "text-slate-400 hover:bg-edge/60 hover:text-slate-200"
                  }`
            }
          >
            {section.label}
          </Link>
        );
      })}
    </nav>
  );
}
