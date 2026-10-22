import { Notice, Panel } from "@/components/ui";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * Lab: bersagli locali intenzionalmente vulnerabili.
 *
 * Le pagine del laboratorio non sono esposte dal backend: si avviano
 * direttamente dal proprio ambiente, in locale.
 */
export default async function LabPage() {
  let llm = null;
  try {
    llm = await api.llmStatus();
  } catch {
    llm = null;
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-100">Lab</h1>
        <p className="text-sm text-slate-400">
          Ambiente di laboratorio isolato: bersagli locali con vulnerabilita' intenzionali,
          usati per validare l'analisi e produrre test di regressione.
        </p>
      </header>

      <Notice tone="warn">
        Le applicazioni del laboratorio sono <strong>vulnerabili per design</strong>.
        Devono essere eseguite solo in locale, con dati fittizi, e mai esposte su una
        rete.
      </Notice>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel
          title="SQL injection lab"
          description="Bersaglio vulnerabile e versione corretta, affiancate."
        >
          <ul className="space-y-2 text-sm text-slate-300">
            <li>
              <code className="rounded bg-base px-1.5 py-0.5 font-mono text-xs">
                lab/sqli_app/vulnerable.py
              </code>
              <span className="block text-xs text-slate-500">
                Query concatenate: f-string in /search, /item e /report.
              </span>
            </li>
            <li>
              <code className="rounded bg-base px-1.5 py-0.5 font-mono text-xs">
                lab/sqli_app/fixed.py
              </code>
              <span className="block text-xs text-slate-500">
                Query parametrizzate e validazione dell'input: il riferimento della
                correzione.
              </span>
            </li>
            <li>
              <code className="rounded bg-base px-1.5 py-0.5 font-mono text-xs">
                lab/tests/test_sqli_lab.py
              </code>
              <span className="block text-xs text-slate-500">
                Test di regressione: l'analizzatore deve segnalare il bersaglio e non
                segnalare la versione corretta.
              </span>
            </li>
          </ul>
        </Panel>

        <Panel title="Avvio manuale" description="Comandi da eseguire nel proprio terminale.">
          <pre className="overflow-x-auto rounded border border-edge bg-base p-3 font-mono text-xs text-slate-300">
{`# Bersaglio vulnerabile (localhost:8100)
python -m uvicorn lab.sqli_app.vulnerable:app --port 8100

# Versione corretta (localhost:8101)
python -m uvicorn lab.sqli_app.fixed:app --port 8101

# Verifica con la sola applicazione vulnerabile
curl "http://127.0.0.1:8100/search?q=alice"
curl "http://127.0.0.1:8100/search?q=%27%20OR%20%271%27=%271"`}
          </pre>
          <p className="mt-2 text-xs text-slate-500">
            Il secondo comando restituisce tutte le righe: e' il comportamento atteso
            del bersaglio, verificato dai test automatici.
          </p>
        </Panel>
      </div>

      <Panel title="Configurazione del provider">
        <p className="text-sm text-slate-400">
          {llm
            ? `Provider attivo: ${llm.provider} (${llm.base_url}, modello ${llm.model}).`
            : "Provider non raggiungibile dal backend."}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Il laboratorio non richiede un provider LLM: l'analisi statica e i test
          automatici funzionano in ogni caso.
        </p>
      </Panel>
    </div>
  );
}
