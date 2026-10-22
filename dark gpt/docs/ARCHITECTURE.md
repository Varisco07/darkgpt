# DarkGPT — Architettura Tecnica (Fase 1)

> Documento di progettazione. Descrive il sistema come sarà costruito, non ciò che
> "dovrebbe" esserci. Lo stato di implementazione è tracciato in `ROADMAP.md`.

## 1. Obiettivi di design

| Obiettivo | Scelta progettuale |
|---|---|
| Usabilità reale da subito | Backend FastAPI autonomo + dashboard Next.js, avvio con 2 comandi |
| Nessun vendor lock-in | Provider LLM via interfaccia OpenAI-compatible (`/v1/chat/completions`) |
| Tracciabilità | Ogni azione del tool è persistita in `tool_runs` con hash del comando e output |
| Non simulare risultati | I tool dichiarano `availability` reale (binario presente? versione?); mai output inventato |
| Separazione netta | Backend (API/analisi) ≠ Frontend (UI) ≠ Lab (target vulnerabili) |
| Modalità operative reali | `PASSIVE` / `LAB` / `AUTHORIZED_ASSESSMENT` governano l'esecuzione dei tool |

## 2. Vista d'insieme

```
┌──────────────────────────────────────────────────────────────────────┐
│  Frontend  Next.js 14 (App Router) + React 18 + TypeScript          │
│  Dashboard / Projects / Scope / Scanner / Findings / AI Research /   │
│  Tool Manager / Reports / Lab / Settings                            │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ REST (JSON) + SSE per lo streaming
┌───────────────────────────────▼──────────────────────────────────────┐
│  Backend  FastAPI (Python 3.11+)                                     │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────────┐  │
│  │ api/       │ │ services/  │ │ tools/     │ │ ai/              │  │
│  │ routers    │ │ dominio    │ │ registry + │ │ provider adapter │  │
│  │ + schemas  │ │ transazio- │ │ runner iso-│ │ OpenAI-compat.   │  │
│  │ Pydantic   │ │ nale       │ │ lato       │ │ + tool calling   │  │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ core/  config · db · logging · security · errors · events    │    │
│  └──────────────────────────────────────────────────────────────┘    │
└───────────────┬──────────────────────────────┬───────────────────────┘
                │ SQLAlchemy                    │ subprocess isolato
┌───────────────▼──────────────┐  ┌────────────▼───────────────────────┐
│  Storage  SQLite (WAL)      │  │  Tool runtime                     │
│  SQLAlchemy 2.0 ORM        │  │  allowlist comandi, timeout,       │
│  → PostgreSQL (futuro)     │  │  cwd jail, env minimizzata,        │
└─────────────────────────────┘  │  stdout/stderr catturati, hash    │
                                  └────────────┬───────────────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    ▼                          ▼                          ▼
             ┌─────────────┐           ┌──────────────┐          ┌───────────┐
             │  Lab        │           │  Target      │          │  Tool     │
             │  vulnerabile│           │  esterno     │          │  esterno  │
             │  (locale)   │           │  (solo con   │          │  (SAST/   │
             │  sqli_app   │           │  scope OK)   │          │  SCA/git) │
             └─────────────┘           └──────────────┘          └───────────┘
```

## 3. Componenti

### 3.1 Backend — `backend/app/`

| Modulo | Responsabilità | Note |
|---|---|---|
| `main.py` | Composition root FastAPI, CORS, lifecycle, router mount, error handlers | Nessuna logica business |
| `core/config.py` | Settings Pydantic da env (`.env`), provider LLM, limiti, path lab | Prefisso `DARKGPT_`, secret mai loggato |
| `core/db.py` | Engine SQLAlchemy, session factory, `init_db`, seed demo | SQLite `check_same_thread=False`, WAL |
| `core/logging.py` | Logging strutturato JSON su stderr + buffer in memoria per UI | Un solo logger `darkgpt` |
| `core/errors.py` | Gerarchia eccezioni → HTTP mapping uniforme | `AppError` base |
| `core/security.py` | Redazione segreti, hashing, sanitizzazione output tool, allowlist URL | Nessun segreto in log |
| `api/deps.py` | Dipendenze FastAPI: session DB, progetto corrente, scope guard | Iniezione, no globali |
| `api/routers/*.py` | Risorse REST per progetto/scope/finding/tool/report/chat | Sottorisorse per progetto |
| `schemas/*.py` | Modelli Pydantic v2 (request/response) | Validazione stretta, `extra="forbid"` |
| `services/scope.py` | Scope Manager: parsing policy, match asset, decisioni allow/deny | Decisione centralizzata |
| `services/findings.py` | Lifecycle finding + transizioni di stato + evidenze | Macchina a stati esplicita |
| `services/projects.py` | CRUD progetto, memoria contesto, import file analizzati | |
| `services/reports.py` | Rendering Markdown/HTML/JSON dei finding | Solo dati realmente presenti |
| `services/cvss.py` | Calcolo CVSS v3.1 base vector + spiegazione metriche | Implementazione propria, testata |
| `tools/registry.py` | Registro tool: schema input, availability, runner | Tool assente → `unavailable`, mai simulato |
| `tools/runner.py` | Esecuzione isolata: allowlist, timeout, jail, capture | `subprocess` senza `shell=True` |
| `tools/http_client.py` | Client HTTP per test autorizzati, con budget di richieste | Richiede scope valido |
| `tools/sast_sql.py` | Analizzatore statico Python per SQL injection | AST-based, no regex fragili |
| `ai/provider.py` | Interfaccia `LLMProvider` + factory OpenAI-compatible | Streaming + tool calling opzionale |
| `ai/prompts.py` | Prompt di sistema modulari per ruolo (analysis/report/code) | Nessun secret nei prompt |
| `ai/tools.py` | Tool-calling: schema tool derivato dal registry | Guard: un tool alla volta |
| `tasks/queue.py` | Esecuzione analisi lunghe in background + event stream | In-process, thread pool |

### 3.2 Tool Registry — contratto

Ogni tool è un oggetto con:

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str                 # "sast.sql.python"
    category: str             # "sast" | "http" | "sca" | "scanner" | "lab"
    description: str
    input_schema: dict        # JSON Schema, usato anche per validazione
    requires_scope: bool      # True -> serve asset in scope
    mutating: bool            # True -> richiede conferma operatore
    timeout_seconds: int
    availability: str         # "available" | "unavailable" | "degraded"
    availability_reason: str
```

Il runner applica, in ordine: validazione input → controllo scope (se
`requires_scope`) → conferma operatore (se `mutating`) → timeout → esecuzione
→ sanitizzazione output → persistenza in `tool_runs`.

**Regola assoluta:** se il binario non è installato, il tool risponde
`status="unavailable"` con il motivo e il comando di installazione. Non
produce output simulato.

### 3.3 AI Engine

- Interfaccia `LLMProvider` con `chat(messages, tools=None, stream=False)`.
- Implementazione `OpenAICompatProvider` che parla `/v1/chat/completions`
  verso qualunque endpoint OpenAI-compatible: provider cloud, LM Studio,
  Ollama (via `/v1`), vLLM, o gateway interni.
- Configurazione: `DARKGPT_LLM_BASE_URL`, `DARKGPT_LLM_API_KEY`,
  `DARKGPT_LLM_MODEL`, `DARKGPT_LLM_TEMPERATURE`, `DARKGPT_LLM_TIMEOUT`.
- Se `DARKGPT_LLM_API_KEY` e vuota -> funziona in modalita **mock dichiarata**
  (risposta esplicita "provider non configurato"), utile per sviluppo e test.
  La UI marca sempre le risposte simulate.
- Tool calling: quando il provider supporta `tools`, il modello puo invocare
  tool del registry; l'esecuzione passa dal runner (mai esecuzione diretta).
- Rate limit e timeout gestiti con retry esponenziale + jitter, e
  `Retry-After` rispettato.

## 4. Flussi di dati principali

### 4.1 Analisi statica (SAST SQL) su codice utente

```
UI "Scanner" -> POST /api/projects/{id}/scans {tool, target}
  -> router: verifica progetto + scope del path target
  -> tools/registry: lookup spec + availability
  -> tools/runner: validazione input, timeout, jail
  -> sast_sql analizza i file -> findings "POTENTIAL"
  -> services/findings: crea finding, registra evidenza, transizione
  -> SSE /api/projects/{id}/events  (aggiornamento UI in tempo reale)
  -> tool_runs: record completo (command, duration, hash output)
```

### 4.2 Chat AI con contesto di progetto

```
UI chat -> POST /api/projects/{id}/chat {message}
  -> costruisce contesto: descrizione progetto, stack, scope, finding aperti,
    ultimi tool_runs (troncati), estratti di file gia analizzati
  -> provider.chat(stream=True) -> SSE token
  -> se il modello richiede tool -> registry + runner -> risultato -> secondo turno
  -> persistenza in chat_messages (project_id, role, content, tool_calls)
```

### 4.3 Verifica di una vulnerabilita in LAB MODE

```
UI "Findings" -> "Valida" -> POST /api/projects/{id}/findings/{fid}/validate
  -> crea FindingEvidence (richieste, risposte, output tool)
  -> transition a CONFIRMED solo se l'evidenza contiene i marker richiesti
    (es. differenza di risposta tra payload benigno e payload iniettivo)
  -> in caso contrario NEEDS_VALIDATION, con motivo esplicito
```

## 5. Modalita operative

| Modalita | Target consentiti | Tool attivi | Conferma |
|---|---|---|---|
| `PASSIVE` | solo file locali e documentazione | SAST, SCA, git, OpenAPI parser | non richiesta |
| `LAB` | app locali del progetto `lab/` | + http client verso `127.0.0.1` | richiesta al mutating |
| `AUTHORIZED_ASSESSMENT` | asset elencati in scope | + http client verso asset in scope | richiesta sempre |

La modalita e impostata per progetto (`Project.mode`) ed e **contestata dal
backend** a ogni esecuzione di tool: la UI non puo eludere il vincolo.

## 6. Struttura delle cartelle

```
dark gpt/
├── README.md
├── .env.example
├── .gitignore
├── Makefile                      # comandi wrapper
├── docs/
│   ├── ARCHITECTURE.md           # questo documento
│   ├── DATA_MODEL.md
│   ├── API.md
│   ├── SECURITY_MODEL.md
│   └── ROADMAP.md
├── backend/
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py               # composition root
│   │   ├── core/
│   │   │   ├── config.py         # settings da env
│   │   │   ├── db.py             # engine, session factory, bootstrap
│   │   │   ├── logging.py        # log JSON + buffer per la UI
│   │   │   ├── errors.py         # gerarchia errori -> HTTP
│   │   │   └── security.py       # redazione, hashing, normalizzazione target
│   │   ├── api/
│   │   │   ├── deps.py           # sessione DB, progetto corrente
│   │   │   └── routers/          # projects, scope, findings, tools,
│   │   │                         # chat, reports, settings
│   │   ├── schemas/              # modelli Pydantic v2 (request/response)
│   │   ├── models/               # SQLAlchemy 2.0: base, enums, project,
│   │   │                         # scope, finding, tool_run, chat
│   │   ├── services/
│   │   │   ├── scope.py          # Scope Manager: parsing, matching, decisioni
│   │   │   ├── findings.py       # macchina a stati, evidenze
│   │   │   ├── reports.py        # Markdown / HTML / JSON
│   │   │   ├── cvss.py           # CVSS v3.1 base score
│   │   │   └── chat_service.py   # contesto di progetto + orchestrazione LLM
│   │   ├── tools/
│   │   │   ├── registry.py       # ToolSpec, disponibilita', lookup
│   │   │   ├── runner.py         # validazione, scope, conferma, persistenza
│   │   │   ├── schema.py         # validatore JSON Schema minimale
│   │   │   ├── builtin.py        # tool concreti (SAST SQL, bandit, pip-audit, git)
│   │   │   ├── sast_sql.py       # analizzatore AST per SQL injection
│   │   │   └── http_client.py    # client HTTP (non ancora registrato come tool)
│   │   └── ai/
│   │       ├── provider.py       # interfaccia + adattatore OpenAI-compatible
│   │       └── prompts.py        # prompt di sistema per ruolo
│   └── tests/
│       ├── conftest.py
│       ├── test_scope.py
│       ├── test_findings.py
│       ├── test_cvss.py
│       ├── test_sast_sql.py
│       └── test_api.py
├── lab/
│   ├── README.md
│   ├── sqli_app/
│   │   ├── db.py                 # dati fittizi su file temporaneo
│   │   ├── vulnerable.py         # bersaglio intenzionalmente vulnerabile
│   │   └── fixed.py              # versione corretta (query parametrizzate)
│   └── tests/test_sqli_lab.py    # dimostrazione + test di regressione
├── frontend/
│   ├── package.json
│   ├── next.config.mjs
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── globals.css
│       │   └── (dashboard)/
│       │       ├── layout.tsx    # navigazione laterale + selettore progetto
│       │       └── {overview,projects,scope,scanner,findings,chat,
│       │            tools,reports,lab,settings}/page.tsx
│       ├── components/           # componenti client interattivi
│       └── lib/{api,types}.ts    # client HTTP tipizzato
└── scripts/
    ├── run_tests.py              # runner della suite (backend + lab)
    ├── validate_cvss.py          # validazione CVSS esaustiva
    ├── smoke_e2e.py              # verifica end-to-end dell'API reale
    ├── smoke_frontend.py         # verifica end-to-end della dashboard
    ├── diag_import.py            # diagnostica degli import
    └── list_files.py             # inventario dei file
```

> **Moduli previsti ma non ancora implementati** (cfr. `ROADMAP.md`):
> `services/projects.py`, `ai/tools.py` (tool-calling), `tasks/queue.py`
> (analisi lunghe in background), `tools/openapi.py`, `tools/git_tools.py`.

## 7. Dipendenze

**Backend** (tutte mantenute, licenze permissive):
`fastapi`, `uvicorn[standard]`, `pydantic` v2, `pydantic-settings`,
`sqlalchemy` 2.0, `httpx`, `python-multipart`, `structlog`,
`pytest`, `pytest-asyncio`, `pyyaml`, `bleach`, `packaging`.

**Tool esterni** (opzionali, il tool si dichiara `unavailable` se assenti):
`bandit` (SAST Python), `pip-audit` (SCA), `semgrep`, `nuclei`, `git`,
`nmap` (solo in AUTHORIZED mode con conferma), `trivy`.

**Frontend**: `next` 14, `react` 18, `typescript`, `tailwindcss`,
`@tanstack/react-query`, `react-markdown`, `shiki` (evidenziazione sintassi).

## 8. Migrazione a PostgreSQL

`core/db.py` costruisce l'engine da `DARKGPT_DATABASE_URL`. Il default e
`sqlite:///./darkgpt.db`. Per PostgreSQL: `postgresql+psycopg://user:pass@host/db`.
I modelli usano tipi SQLAlchemy portabili; l'unica differenza specifica SQLite
e il `PRAGMA journal_mode=WAL`, applicato condizionalmente via
`dialect.name == "sqlite"`. Nessuna query SQL raw con sintassi SQLite-specifica.
