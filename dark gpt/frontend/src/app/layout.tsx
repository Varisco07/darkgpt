import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "DarkGPT",
  description:
    "Piattaforma di sicurezza applicativa: scope manager, analisi statica, gestione dei finding, report e ricerca assistita da LLM.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
