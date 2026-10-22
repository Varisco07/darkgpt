# DarkGPT

Piattaforma di sicurezza applicativa e bug bounty: **Scope Manager**, analisi
statica del codice, gestione dei finding con evidenze, report verificabili e
ricerca assistita da un provider LLM configurabile.

La piattaforma e' progettata attorno a una regola: **non simula risultati**.
Ogni tool dichiara la propria disponibilita' reale, ogni finding nasce come
ipotesi e puo' diventare confermato solo con evidenze registrate, ogni report
riporta solo cio' che e' stato effettivamente raccolto.

---

## Indice

- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Avvio](#avvio)
- [Configurazione del provider LLM](#configurazione-del-provider-llm)
- [Uso della piattaforma](#uso-della-piattaforma)
- [Laboratorio SQL injection](#laboratorio-sql-injection)
- [Test](#test)
- [Struttura del repository](#struttura-del-repository)
- [Documentazione di progettazione](#documentazione-di-progettazione)
- [Limitazioni note](#limitazioni-note)

---

## Requisiti

| Componente | Versione | Note |
|---|---|---|
| Python | 3.11+ | Sviluppato e verificato su 3.13 |
| Node.js | 18+ | Sviluppato e verificato su 24 |
| SQLAlchemy | `>=2.0.30,<2.1` | vedi nota su Windows |
| Docker | opzionale | Non presente su questa macchina; usato solo per l'isolamento opzionale |

> **Nota Windows.** SQLAlchemy 2.1.x carica un'estensione C (`.pyd`) che puo'
> essere bloccata dalle policy di controllo applicazioni di Windows quando il
> progetto risiede in una cartella sincronizzata (OneDrive, Dropbox). La serie
> 2.0.x ha un fallback puro Python e funziona senza problemi: per questo
> `backend/requirements.txt` fissa `sqlalchemy>=2.0.30,<2.1`.

## Installazione

```powershell
# 1. Backend (PowerShell)
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 2. Configurazione
Copy-Item .env.example .env

# 3. Frontend
cd frontend
npm.cmd install
cd ..
```

Su Linux/macOS/Git Bash gli stessi passi con `.venv/bin/python` e `cp`.

In alternativa, con `make` disponibile:

```bash
make install
```

## Avvio

### Windows — percorso consigliato

Il modo piu' semplice e' uno script che avvia entrambi i servizi in due
finestre. Su questa macchina la policy di esecuzione di PowerShell e'
`Restricted` (impostazione predefinita di Windows), quindi anche i file `.ps1`
vengono bloccati: la via che funziona sempre senza modificare la macchina e'
il launcher `.cmd`.

```bat
scripts\dev.cmd
```

Da PowerShell, lo stesso launcher:

```powershell
cmd /c scripts\dev.cmd
```

Se vuoi usare lo script PowerShell (avvio selettivo), invocalo con la policy
bypassata per il singolo processo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Target backend
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Target frontend
```

In alternativa due terminali, con i comandi corretti per PowerShell:

```powershell
# Terminale 1 — backend (127.0.0.1:8000)
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload

# Terminale 2 — dashboard (localhost:3000)
cd frontend
npm.cmd run dev
```

> **Nota PowerShell.** I comandi in stile bash (`.venv/Scripts/python ...`,
> `cd frontend && npm run dev`) non funzionano in PowerShell: serve `&` davanti
> al percorso dell'eseguibile e `.\` per i comandi locali. Inoltre `npm` e'
> uno script `.ps1` e su Windows puo' essere bloccato dalla policy
> (`Impossibile caricare il file ...\npm.ps1. L'esecuzione di script e'
> disabilitata`): usando `npm.cmd` (o gli script qui sopra) il problema non si
> presenta. Se preferisci abilitare gli script per il tuo utente:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Linux / macOS / Git Bash

Due terminali:

```bash
# Terminale 1 — backend (127.0.0.1:8000)
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload

# Terminale 2 — dashboard (localhost:3000)
cd frontend && npm run dev
```

- Dashboard: <http://localhost:3000>
- Documentazione interattiva dell'API: <http://127.0.0.1:8000/docs>
- Stato del servizio: <http://127.0.0.1:8000/health>

Il backend ascolta su `127.0.0.1` per impostazione predefinita: **non va
esposto su una rete pubblica** senza aver prima aggiunto autenticazione (non
presente nell'MVP, vedi [Limitazioni note](#limitazioni-note)).

## Configurazione del provider LLM

Il provider LLM è opzionale e non vincolato a un singolo vendor: basta un
endpoint che esponga l'API OpenAI-compatible.

```dotenv
# OpenAI
DARKGPT_LLM_BASE_URL=https://api.openai.com/v1
DARKGPT_LLM_API_KEY=sk-...
DARKGPT_LLM_MODEL=gpt-4o-mini

# Ollama in locale (nessuna API key)
DARKGPT_LLM_BASE_URL=http://localhost:11434/v1
DARKGPT_LLM_MODEL=llama3.1

# LM Studio in locale
DARKGPT_LLM_BASE_URL=http://localhost:1234/v1
DARKGPT_LLM_MODEL=<modello caricato>
```

Se `DARKGPT_LLM_BASE_URL` resta vuota la piattaforma resta pienamente
funzionante: analisi statica, scope, finding, report e laboratorio non
dipendono dal modello. La chat risponde allora con un provider di fallback
**dichiarato come simulato**, e la dashboard marca la risposta come tale.

## Uso della piattaforma

Flusso consigliato:

1. **Projects** — crea un progetto e scegli la modalita' operativa:
   - `PASSIVE`: solo analisi offline, nessun test attivo;
   - `LAB`: test attivi ammessi **solo** sui target locali del laboratorio;
   - `AUTHORIZED_ASSESSMENT`: richiede uno scope gia' importato con almeno
     una regola `ALLOW` (il backend rifiuta l'upgrade altrimenti).
2. **Scope** — incolla la policy del programma di bug bounty. Il backend
   estrae le regole, deriva gli asset e applica il controllo deny-by-default.
   Usa "Verifica un target" per capire se un bersaglio e' ammesso, senza
   eseguire alcuna richiesta.
3. **Scanner** — avvia l'analisi statica sul codice. Le esecuzioni sono
   registrate in `tool_runs` con durata, stato e hash dell'output: e' la fonte
   autorevole per l'audit.
4. **Findings** — i risultati dell'analisi nascono come `POTENTIAL`. Allega
   evidenze e porta il finding a `CONFIRMED` con una motivazione: la
   macchina a stati rifiuta transizioni non previste (HTTP 409) e la conferma
   senza evidenze (HTTP 422).
5. **Reports** — genera il report in Markdown, HTML o JSON. Il report
   contiene solo i dati registrati e chiude con i limiti dell'analisi.
6. **AI Research** — chat con il contesto del progetto (scope, finding,
   esecuzioni). Il contenuto inviato al provider e' redatto e troncato.

### Modalita' operative

| Modalita' | Bersagli ammessi | Rete |
|---|---|---|
| `PASSIVE` | solo file locali | nessuna |
| `LAB` | bersagli del laboratorio | loopback |
| `AUTHORIZED_ASSESSMENT` | asset in scope | host in scope |

La modalita' è un **confine di sicurezza applicato dal backend**: la UI non
puo' eluderlo.

## Laboratorio SQL injection

Il laboratorio contiene un bersaglio **intenzionalmente vulnerabile** e la
versione corretta, affiancate, con i dati fittizi.

```bash
# Bersaglio vulnerabile
.venv/Scripts/python -m uvicorn lab.sqli_app.vulnerable:app --port 8100

# Versione corretta
.venv/Scripts/python -m uvicorn lab.sqli_app.fixed:app --port 8101
```

```bash
# Richiesta legittima: una sola riga
curl "http://127.0.0.1:8100/search?q=alice"

# Payload iniettivo: tutte le righe (comportamento atteso del bersaglio)
curl "http://127.0.0.1:8100/search?q=%27%20OR%20%271%27=%271"
```

Sulla versione corretta la stessa richiesta restituisce zero righe e
l'endpoint numerico rifiuta l'input non numerico.

> Il laboratorio deve restare in locale, con dati fittizi, e non va mai
> esposto su una rete.

## Test

```powershell
# Intera suite (backend + laboratorio + game)
& .\.venv\Scripts\python.exe scripts\run_tests.py

# Solo backend
cd backend
& ..\.venv\Scripts\python.exe -m pytest -q
cd ..

# Solo laboratorio
& .\.venv\Scripts\python.exe -m pytest lab\tests -q

# Verifica end-to-end dell'API reale
& .\.venv\Scripts\python.exe scripts\smoke_e2e.py

# Verifica che TUTTO funzioni da zero (come un primo avvio)
& .\.venv\Scripts\python.exe scripts\cold_start.py

# Validazione esaustiva del CVSS su tutti i 2592 vettori base
& .\.venv\Scripts\python.exe scripts\validate_cvss.py
```

> Su Linux/macOS/Git Bash usare `.venv/bin/python` al posto di
> `& .\.venv\Scripts\python.exe`.

`scripts/cold_start.py` e' la verifica piu' utile per chi ha appena clonato
il repository: rimuove il database, riavvia backend e dashboard con i
comandi documentati e percorre un flusso completo (progetto -> scope ->
scansione -> finding -> report) verificando che la dashboard mostri i dati.

Il report della suite viene scritto in `test-report.txt` (e in
`test-report.xml`).

`scripts/validate_cvss.py` confronta l'implementazione interna con la
libreria di riferimento `cvss`; va eseguito in un ambiente che la abbia
installata (`pip install cvss`).

## Struttura del repository

```
dark gpt/
├── backend/app/          API FastAPI, servizi, tool, provider LLM
├── backend/tests/        Test del backend
├── lab/sqli_app/         Bersaglio vulnerabile + versione corretta
├── lab/tests/            Test del laboratorio (regressione)
├── game/                 Game Security Research & Modding
│   ├── analyzer.py       Riconoscimento motore e vie di modding
│   ├── mod_creator.py    Scaffolding di mod, backup e ripristino
│   ├── memory_lab.py     Dimostrazione di modifica dei valori
│   ├── multiplayer.py    Analisi dell'architettura client-server
│   └── tests/
├── frontend/src/         Dashboard Next.js (App Router, TypeScript)
├── docs/                 Documentazione di progettazione
├── scripts/              Utilita' (test runner, validazione CVSS, smoke test)
└── .env.example          Configurazione di esempio
```

## Tool disponibili

| Tool | Categoria | Richiede conferma | Note |
|---|---|---|---|
| `sast.sql.python` | SAST | no | Analisi AST per SQL injection (in-process) |
| `sast.bandit` | SAST | no | Richiede `pip install bandit` |
| `sca.pip_audit` | SCA | no | Richiede `pip install pip-audit` |
| `scm.git` | SCM | no | Solo sottocomandi in lettura |
| `http.request` | HTTP | **si** | Scope verificato **per ogni richiesta** + budget |
| `game.analyze` | Game | no | Analisi statica di una cartella di gioco |
| `game.mod_scaffold` | Game | **si** | Genera lo scaffolding di un mod (scrive file) |

Dalla UI (**Scanner**) si puo' usare un campo percorso oppure un campo
**input JSON avanzato**, necessario per i tool con schemi complessi
(es. `http.request`).

```json
{
  "requests": [
    { "url": "http://127.0.0.1:8100/search", "method": "GET" }
  ],
  "technique": "active_testing"
}
```

## Game Security Research & Modding

Il modulo `game/` copre analisi del gioco, generazione di mod, dimostrazione
del metodo di modifica dei valori e analisi dell'architettura client-server.
I suoi confini sono espliciti: **giochi offline, progetti propri, software
open source**; nessun meccanismo di evasione anti-cheat, nessuno strumento
per compromettere altri giocatori. Dettagli in [`game/README.md`](game/README.md).

## Documentazione di progettazione

| Documento | Contenuto |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Componenti, flussi di dati, struttura, dipendenze |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | Entita', enumerazioni, macchina a stati dei finding |
| [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) | Confini, gestione segreti, regole di scope, limiti |
| [`docs/API.md`](docs/API.md) | Riferimento degli endpoint REST |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Stato delle fasi e lavoro previsto |

## Limitazioni note

Dichiarate esplicitamente, per non creare false certezze:

- **Nessuna autenticazione nell'MVP.** Il backend e' pensato per l'uso in
  localhost. esporlo su una rete richiede di aggiungere autenticazione.
- **L'isolamento dei subprocess non e' a livello di kernel.** Su Windows non
  e' disponibile il sandboxing kernel: per ambienti non fidati usare Docker
  o una macchina virtuale dedicata.
- **L'analizzatore SAST e' mirato.** Copre le query SQL costruite per
  interpolazione in Python; non e' un sostituto di `bandit` o `semgrep`, che
  restano integrabili come tool esterni.
- **L'analisi del tainted data e' eqlice.** Un finding da analisi statica
  resta `POTENTIAL` finche' non viene confermato con prove.
- **La chat non e' in streaming nell'MVP.** Il provider espone gia' lo
  streaming, ma il trasporto SSE verso il browser non e' ancora cablato.
- **Docker non e' disponibile su questa macchina**, quindi i laboratori
  isolati via container non sono stati verificati.
- **Il calcolo CVSS copre solo il base score v3.1.** Le metriche temporali e
  ambientali non sono implementate.
