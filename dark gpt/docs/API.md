# DarkGPT — Riferimento API (Fase 2)

Base: `http://127.0.0.1:8000`. Tutte le risposte sono JSON.
Documentazione interattiva: `/docs` (Swagger) e `/redoc`.

## 1. Formato degli errori

Ogni errore applicativo ha la stessa forma:

```json
{
  "error": {
    "code": "out_of_scope",
    "message": "operazione fuori scope: nessuna regola ALLOW copre il target richiesto",
    "details": { "target": "example.org", "decision": "OUT_OF_SCOPE" }
  }
}
```

| Codice | HTTP | Significato |
|---|---|---|
| `not_found` | 404 | Risorsa inesistente |
| `validation_error` | 422 | Richiesta non conforme allo schema, o precondizione non soddisfatta |
| `conflict` | 409 | Transizione di stato non consentita |
| `out_of_scope` | 403 | Operazione fuori dallo scope autorizzato |
| `scope_required` | 409 | Modalita' `AUTHORIZED_ASSESSMENT` senza scope |
| `tool_unavailable` | 503 | Tool non installato |
| `tool_execution_failed` | 500 | Tool fallito durante l'esecuzione |
| `confirmation_required` | 428 | Operazione che richiede conferma esplicita |
| `llm_provider_error` | 502 | Errore del provider LLM |

## 2. Sistema

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/health` | Stato del servizio e del database |
| `GET` | `/api/overview` | Panoramica sintetica |
| `GET` | `/api/settings/llm` | Stato del provider LLM (senza segreti) |
| `GET` | `/api/settings/limits` | Limiti operativi in vigore |
| `GET` | `/api/logs?limit=N` | Log recenti dal buffer in memoria |

## 3. Progetti

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/api/projects` | Elenco dei progetti |
| `POST` | `/api/projects` | Crea un progetto |
| `GET` | `/api/projects/{id}` | Dettaglio |
| `PATCH` | `/api/projects/{id}` | Modifica i campi descrittivi |
| `PATCH` | `/api/projects/{id}/mode` | Cambia la modalita' operativa |
| `GET` | `/api/projects/{id}/summary` | Riepilogo quantitativo |
| `GET` | `/api/projects/{id}/files` | File analizzati registrati |

```http
POST /api/projects
Content-Type: application/json

{
  "name": "Portale cliente",
  "description": "Analisi del codice del portale",
  "mode": "PASSIVE",
  "stack": ["python", "fastapi"],
  "root_path": "C:\\progetti\\portal"
}
```

`PATCH /api/projects/{id}/mode` con `AUTHORIZED_ASSESSMENT` restituisce
`409 scope_required` se il progetto non ha ancora almeno una regola `ALLOW`.

## 4. Scope

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/api/projects/{id}/scope` | Policy corrente (regole e asset) |
| `POST` | `/api/projects/{id}/scope/import` | Importa (o sostituisce) la policy da testo |
| `POST` | `/api/projects/{id}/scope/rules` | Aggiunge una regola puntuale |
| `POST` | `/api/projects/{id}/scope/check` | Verifica un target (nessuna richiesta eseguita) |

```http
POST /api/projects/1/scope/import
Content-Type: application/json

{
  "text": "in scope: example.com\nin scope: *.example.com\nout of scope: admin.example.com\ndo not perform denial of service",
  "notes": "policy del programma Q1 2026"
}
```

L'importazione **sostituisce** integralmente la policy precedente. Gli asset
sono derivati dalle regole: non e' possibile dichiarare un asset senza la
regola che lo produce.

```http
POST /api/projects/1/scope/check
Content-Type: application/json

{ "target": "https://api.example.com/v1/users", "technique": "" }
```

Risposta:

```json
{
  "decision": "ALLOWED",
  "reason": "target coperto da una regola ALLOW (pattern: *.example.com)",
  "matched_rule_id": 2,
  "matched_pattern": "*.example.com",
  "requires_confirmation": false,
  "prohibited": []
}
```

## 5. Finding

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/api/projects/{id}/findings` | Elenco (filtri `status`, `severity`, `category`) |
| `POST` | `/api/projects/{id}/findings` | Crea un finding |
| `GET` | `/api/projects/{id}/findings/{fid}` | Dettaglio con evidenze e transizioni |
| `PATCH` | `/api/projects/{id}/findings/{fid}` | Modifica i campi descrittivi |
| `POST` | `/api/projects/{id}/findings/{fid}/evidence` | Allega un'evidenza |
| `POST` | `/api/projects/{id}/findings/{fid}/transition` | Cambia stato |

```http
POST /api/projects/1/findings/7/transition
Content-Type: application/json

{
  "status": "CONFIRMED",
  "reason": "payload riproducibile sul bersaglio di laboratorio",
  "evidence": [
    {
      "kind": "HTTP_REQUEST",
      "payload": "GET /search?q=%27%20OR%20%271%27=%271",
      "observed": "5 righe restituite invece di 1",
      "source": "lab/sqli_app"
    }
  ]
}
```

Regole applicate dal backend:

- transizione non prevista → `409 conflict`;
- transizione senza motivazione → `422 validation_error`;
- `CONFIRMED` senza evidenze → `422 validation_error`;
- `FIXED` senza evidenza di regressione → `422 validation_error`.

## 6. Tool

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/api/tools` | Catalogo con disponibilita' reale |
| `GET` | `/api/tools/{name}` | Dettaglio di un tool |
| `POST` | `/api/projects/{id}/scans` | Esegue un tool |
| `GET` | `/api/projects/{id}/tool-runs` | Cronologia delle esecuzioni |

```http
POST /api/projects/1/scans
Content-Type: application/json

{
  "tool": "sast.sql.python",
  "input": { "path": "." },
  "confirm": false
}
```

Stati possibili di `ToolRunStatus`: `SUCCESS`, `FAILED`, `TIMEOUT`,
`UNAVAILABLE`, `DENIED`, `INVALID_INPUT`. Ogni esecuzione e' persistita in
`tool_runs` con input redatto, hash SHA-256 dell'output, durata e codice di
uscita.

### Tool disponibili

| Tool | Categoria | Attivo | Conferma | Note |
|---|---|---|---|---|
| `sast.sql.python` | sast | no | no | Analisi AST per SQL injection |
| `sast.bandit` | sast | no | no | Richiede `bandit` installato |
| `sca.pip_audit` | sca | no | no | Richiede `pip-audit` installato |
| `scm.git` | scm | no | no | Solo sottocomandi git in lettura |
| `http.request` | http | **si** | **si** | Scope verificato per ogni singola richiesta |
| `game.analyze` | game | no | no | Analisi statica di una cartella di gioco |
| `game.mod_scaffold` | game | no | **si** | Scrive file: non sovrascrive |

```http
POST /api/projects/1/scans
Content-Type: application/json

{
  "tool": "http.request",
  "input": {
    "requests": [
      { "url": "http://127.0.0.1:8100/search", "method": "GET" }
    ],
    "technique": "active_testing"
  },
  "confirm": true
}
```

La sequenza si ferma alla prima URL fuori scope: l'errore e' propagato come
`DENIED` e la richiesta non parte.

## 7. Chat

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/api/projects/{id}/chat` | Cronologia e stato del provider |
| `POST` | `/api/projects/{id}/chat` | Invia un messaggio |

```http
POST /api/projects/1/chat
Content-Type: application/json

{ "message": "Analizza il finding #3 e proponi un test di verifica.", "role": "analysis" }
```

Se il provider non e' configurato, la risposta arriva dal provider di
fallback e il campo `simulated` vale `true`.

## 8. Report

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/api/projects/{id}/reports` | Elenco dei report |
| `POST` | `/api/projects/{id}/reports?format=MARKDOWN` | Genera un report |
| `GET` | `/api/projects/{id}/reports/{rid}/download` | Scarica il contenuto |

Formati: `MARKDOWN`, `HTML`, `JSON`.
