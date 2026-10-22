# DarkGPT — Modello di Sicurezza (Fase 1)

Questo documento descrive i controlli applicati dalla piattaforma. La regola
generale: **il backend decide, la UI suggerisce**. Nessuna decisione di
sicurezza puo essere presa solo dal frontend.

## 1. Minimo privilegio e confini

| Confine | Regola |
|---|---|
| Backend -> filesystem | i tool operano solo dentro `project.root_path` o `DARKGPT_LAB_ROOT`; path traversal bloccato con `Path.resolve()` + verifica di prefisso |
| Backend -> rete | l'http client effettua richieste solo se l'host e in scope (o e loopback in LAB MODE); niente DNS rebinding: si risolve l'host e si confronta l'IP |
| Backend -> subprocess | `shell=False` sempre; argv list; allowlist di binari; env minimizzata (`PATH`, `LANG`, `HOME`); cwd = jail del progetto |
| Backend -> LLM | nessun segreto nel prompt; il contesto inviato e filtrato da `redact()`; output del modello non viene eseguito |
| Tool -> modello | l'output dei tool e trattato come **input non attendibile**: non viene mai usato per costruire comandi |
| LLM -> tool | il modello puo *proporre* una chiamata, ma l'esecuzione passa dal runner che rivalida scope, input e permessi |

## 2. Gestione dei segreti

- `DARKGPT_LLM_API_KEY` letta da `.env` (mai committata, `.gitignore`).
- La chiave non compare mai nelle risposte API: `GET /api/settings` restituisce
  solo `llm_api_key_set: bool`.
- `core.security.redact()` sostituisce pattern sensibili (token, password,
  `Authorization:`, chiavi private) con `[REDACTED]` prima di log, persistenza
  e invio al provider.
- `.env` letto solo dal backend; il frontend non riceve segreti.

## 3. Autorizzazione e scope

Pipeline di decisione, eseguita dal `services/scope.py`:

```
1. normalizza target (URL -> host+path, path -> resolved path, host -> lowercase)
2. raccoglie regole ALLOW e DENY applicabili al target
3. se esiste una regola DENY applicabile  -> DENIED  (deny-by-default)
4. se esiste una regola ALLOW applicabile  -> ALLOWED
5. se il progetto e in LAB MODE e il target e loopback/locale -> ALLOWED (lab)
6. altrimenti -> OUT_OF_SCOPE
```

La tecnica richiesta viene inoltre controllata contro le regole
`TECHNIQUE_ALLOW` / `TECHNIQUE_DENY`. Le tecniche destructive
(`dos`, `destructive`, `data_exfiltration`, `brute_force`) sono negate da
default in ogni modalita: per disattivare la deny serve una regola esplicita
registrata, e l'operatore vede un warning.

## 4. Protezione contro attacchi al canale del modello

Il contenuto esterno (output di tool, contenuto di file analizzati, reply
dell'utente) e trattato come non attendibile:

- Nessuna istruzione contenuta in un file puo abilitare un tool.
- Gli argomenti dei tool proposti dal modello sono validati con lo stesso
  schema usato per le richieste UI.
- Il modello non puo cambiare la modalita del progetto ne modificare lo scope.
- Il contesto inviato al provider e limitato a un budget di caratteri, con
  truncamento esplicito e marcato (`[truncated]`).

## 5. Esecuzione dei tool

`tools/runner.py` applica in sequenza:

1. **Validazione input** via JSON Schema (no argomenti liberi).
2. **Controllo scope** se `requires_scope`.
3. **Conferma operatore** se `mutating` (flag `confirm=true` + riepilogo
   mostrato nella UI). Scadenza: la conferma vale per una singola esecuzione.
4. **Budget**: timeout, dimensione massima dell'output, numero massimo di
   richieste HTTP per run.
5. **Esecuzione** in subprocess isolato (o in-process per tool puri Python).
6. **Validazione output** contro lo schema del tool: output non conforme =
   `FAILED`, non successo silenzioso.
7. **Persistenza** in `tool_runs` con durata, exit code, hash SHA-256
   dell'output, parametri redattati.

## 6. Modalita operative come confine di sicurezza

| Modalita | Rete consentita | Scrittura | Destructive |
|---|---|---|---|
| `PASSIVE` | nessuna | solo file del progetto | mai |
| `LAB` | loopback | solo lab root | mai |
| `AUTHORIZED_ASSESSMENT` | host in scope | no | solo con regola esplicita |

Il downgrade da `AUTHORIZED_ASSESSMENT` a `PASSIVE` e sempre permesso; il
upgrade richiede che il progetto abbia almeno una `ScopePolicy` con almeno
una regola `ALLOW`. Il backend rifiuta l'upgrade a `AUTHORIZED_ASSESSMENT`
senza scope (`409 SCOPE_REQUIRED`).

## 7. Protezione della superficie esposta

- Il backend non e pensato per essere esposto pubblicamente. Di default ascolta
  su `127.0.0.1:8000`.
- CORS limitato a `DARKGPT_CORS_ORIGINS` (default `http://localhost:3000`).
- Nessun endpoint di autenticazione nell'MVP: l'accesso e legato al binding
  localhost. Documentato come limitazione in `ROADMAP.md` (Fase 6 prevista:
  API key di sessione).
- Header di sicurezza applicati dal middleware: `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
  `Content-Security-Policy: default-src 'self'`.

## 8. Logging e minimizzazione

- Log strutturato JSON su stderr; ogni record ha `ts`, `level`, `event`,
  `project_id`, `request_id`.
- I payload di richiesta non contengono credenziali; le chiavi note sono
  redattate (`api_key`, `password`, `token`, `authorization`, `secret`).
- Il buffer di log in memoria (per la UI) e limitato a N righe e rimosso al
  riavvio: non e un archivio di audit. Per l'audit, i `tool_runs` in DB sono la
  fonte autorevole.

## 9. Cosa NON e garantito

Documentazione esplicita dei limiti, per non creare false certezze:

- Il backend non verifica la validita legale di un programma di bug bounty:
  verifica la *coerenza interna* tra policy dichiarata e asset utilizzati.
- Il modello LLM puo sbagliare l'analisi: per questo i finding nascono sempre
  come `POTENTIAL` e la conferma richiede evidenze strutturate.
- La sandboxing dei subprocess e a livello di processo e filesystem, non
  container: su Windows non e disponibile l'isolamento kernel. Per ambienti
  non fidati usare Docker (non presente su questa macchina) o un ambiente
  virtuale dedicato.
- L'http client non e un proxy per evasione di WAF: gli header sono espliciti
  e le richieste non tentano di mascherarsi.
