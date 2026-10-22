# DarkGPT — Stato delle fasi e roadmap

## Stato al termine della Fase 5

| Fase | Stato | Cosa e' stato consegnato |
|---|---|---|
| 1. Progettazione | **Completata** | Architettura, modello dati, modello di sicurezza, API, roadmap |
| 2. MVP backend | **Completata** | FastAPI, provider LLM, sessioni, SQLite, Scope Manager, API finding |
| 3. SQL Injection Lab | **Completata** | Bersaglio vulnerabile + versione corretta, analizzatore SAST, test di regressione |
| 4. Dashboard | **Completata** | Next.js 14 + TypeScript, 10 sezioni, build di produzione verificata |
| 5. Validazione | **Completata** | 80 test verdi, smoke test end-to-end, CVSS validato su 2592 vettori |

### Verifiche eseguite

| Verifica | Esito |
|---|---|
| Suite pytest (backend + laboratorio) | **80 test, 0 fallimenti** |
| Smoke test end-to-end su API reale | **22/22 verifiche passate** |
| Validazione CVSS vs libreria di riferimento | **2592/2592 vettori allineati** |
| TypeScript typecheck (frontend) | **nessun errore** |
| Build di produzione Next.js | **10 route compilate** |

## Cosa e' stato verificato e cosa no

**Verificato in esecuzione reale:**

- API REST completa (progetti, scope, finding, tool, report, chat, settings).
- Analisi statica su codice reale: 3 sospetti rilevati sul bersaglio del
  laboratorio, 0 sulla versione corretta.
- Macchina a stati dei finding: transizioni non consentite rifiutate (409),
  conferma senza evidenze rifiutata (422).
- Provider di fallback: la chat risponde in modo dichiarato come simulato
  quando non c'e' alcun endpoint configurato.
- Dashboard: build di produzione completata, tutte le sezioni compilate.

**Non verificato (presente nel codice ma non esercitato):**

- Streaming SSE della chat verso il browser: il provider espone lo streaming,
  il trasporto non e' cablato.
- Tool calling del modello: l'adapter supporta l'API `tools`, ma nessun
  provider e' stato configurato durante le verifiche.
- Esecuzione dei tool esterni `bandit` e `pip-audit`: dichiarati
  `unavailable` perché non installati in questo ambiente.
- PostgreSQL: il codice e' portabile ma la migrazione non e' stata eseguita
  (richiede un'istanza di database).

## Lavoro successivo

### Fase 6 — Sicurezza operativa (priorita' alta)

1. **Autenticazione dell'API.** Token di sessione o API key, con scadenza e
   revoca. Senza questo, il backend non puo' essere esposto oltre il
   localhost.
2. **Audit trail append-only.** `tool_runs` e' gia' la fonte autorevole, ma
   manca la catena di integrita' (hash concatenati) e l'esportazione
   firmata.
3. **Rate limiting** per progetto e per operatore.

### Fase 7 — Capacita' di analisi

4. ~~**Client HTTP operativo**~~ **FATTO**: `http.request` e' registrato come
   tool. Ogni richiesta e' verificata contro lo scope **prima** di partire,
   la sequenza si ferma alla prima URL fuori scope, il numero di richieste e'
   limitato dal budget e l'operazione richiede la conferma esplicita.
5. **Moduli di analisi aggiuntivi**: XSS, SSRF, IDOR/BOLA, path traversal,
   parsing OpenAPI, SBOM.
6. **Analisi del tainted data piu' profonda**: oggi l'analizzatore distingue
   costrutti dinamici e sorgenti di input, ma non traccia il flusso completo
   fino al sink.
7. **Ricerca full-text o RAG** sulla memoria di progetto, come indicato nella
   specifica.

### Fase 8 — Operativita'

8. **Coda di task asincrona** per analisi lunghe, con SSE per il progresso
   (`tasks/queue.py` previsto in architettura, non ancora implementato).
9. **Container per i laboratori** (Docker non e' disponibile su questa
   macchina): isolamento kernel per i bersagli.
10. **CI completa**: test automatici su ogni push, con la validazione CVSS
    esaustiva come job separato.

### Fase 9 — Moduli specialistici

11. ~~**Game Security Research**~~ **FATTO (prima parte)**: il modulo `game/`
    implementa l'Analyzer (riconoscimento motore e vie di modding), il Mod
    Creator (scaffolding con backup e ripristino verificati), il Memory
    Research Lab (dimostrazione su strutture allocate dallo stesso processo) e
    l'analisi dell'architettura client-server. Esposto come tool
    `game.analyze` e `game.mod_scaffold`.
    **Da completare**: analisi statica dei binari (import table, stringhe,
    firma del motore dentro l'eseguibile) e integrazione con i tool esterni
    di reverse engineering.
12. **API Security Analyzer**: controlli di autorizzazione mancanti sulle
    specifiche OpenAPI.
13. **Report con template differenziati** per programmi di bug bounty con
    requisiti formali specifici.

## Debito tecnico noto

| Debito | Impatto | Piano |
|---|---|---|
| Chat senza streaming verso il browser | Esperienza peggiore su risposte lunghe | Fase 8, punto 8 |
| Nessuna autenticazione | Backend limitato al localhost | Fase 6, punto 1 |
| `FileRecord` non popolato dalla scansione | La memoria dei file analizzati resta vuota | Fase 7 |
| Nessun tool di SCA/SAST esterno installato | Copertura SAST limitata al modulo SQL | Fase 7 |
| Nessuna migrazione Alembic | Gli schemi evolvono solo per `create_all` | Fase 8 |
| Tool calling non verificato con un provider reale | Il percorso e' testato con un provider finto | Fase 8 |
| Nessuna analisi statica dei binari di gioco | L'Analyzer lavora sui file, non sugli eseguibili | Fase 9 |

## Aggiunte successive alla Fase 5

Implementate a seguito della richiesta di completare le parti mancanti:

| Aggiunta | Contenuto | Verifica |
|---|---|---|
| Tool HTTP | `http.request` con scope per singola richiesta, budget e conferma | 14 test |
| Tool-calling del modello | Il modello propone, il runner esegue; i tool attivi non sono esposti | 9 test |
| Modulo Game Security | Analyzer, Mod Creator, Memory Lab, Multiplayer | 31 test |
| Tool Game | `game.analyze` e `game.mod_scaffold` | 6 test |
| UI Scanner | campo "input JSON avanzato" per gli schemi complessi | typecheck + build |
