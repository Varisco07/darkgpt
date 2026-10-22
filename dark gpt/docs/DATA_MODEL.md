# DarkGPT — Modello dei Dati (Fase 1)

Database: SQLite in WAL (default `sqlite:///./darkgpt.db`), ORM SQLAlchemy 2.0
tipizzato. Migrazione futura a PostgreSQL senza modifiche ai modelli.

## 1. Diagramma entità-relazione

```
                 ┌──────────────┐
                 │   Project    │
                 │──────────────│
                 │ id  PK       │◄──────────────┐
                 │ name         │               │
                 │ mode  enum   │       ┌───────┴────────┐
                 │ description  │       │  ScopePolicy   │
                 │ stack  JSON  │       │───────────────│
                 │ root_path    │       │ id PK         │
                 │ created_at   │       │ project_id FK │
                 │ updated_at   │       │ raw_text      │
                 └──────┬───────┘       │ asset_count   │
                        │               │ prohibited    │
        ┌───────────────┼───────────────┴───────┐       │
        │               │                       │       │
        ▼               ▼                       │       │
┌───────────────┐ ┌──────────────┐             │       │
│  ScopeAsset   │ │  ScopeRule   │             │       │
│───────────────│ │──────────────│             │       │
│ id PK         │ │ id PK        │             │       │
│ policy_id FK  │ │ policy_id FK │             │       │
│ kind enum     │ │ kind enum    │             │       │
│ value         │ │ pattern      │             │       │
│ allowed bool  │ │ effect enum  │             │       │
│ technique     │ │ technique    │             │       │
│ notes         │ │ notes        │             │       │
└───────────────┘ └──────────────┘             │       │
                                                └───────┘
        ┌───────────────┐
        │  FileRecord   │  (file analizzati / memoria progetto)
        │───────────────│
        │ id PK         │
        │ project_id FK │
        │ path          │
        │ sha256        │
        │ language      │
        │ size_bytes    │
        │ analyzed_at   │
        └───────────────┘

┌──────────────┐      ┌──────────────────┐      ┌────────────────────┐
│   Finding    │      │  FindingEvidence │      │     ToolRun        │
│──────────────│      │──────────────────│      │────────────────────│
│ id PK        │─────►│ id PK            │      │ id PK              │
│ project_id FK│      │ finding_id FK    │      │ project_id FK      │
│ title        │      │ kind enum        │      │ tool_name          │
│ category     │      │ payload          │      │ status enum        │
│ component    │      │ observed         │      │ input_json JSON    │
│ severity     │      │ created_at       │      │ output_text        │
│ cvss_score   │      └──────────────────┘      │ exit_code          │
│ cvss_vector  │                               │ duration_ms        │
│ status enum  │                               │ error_text         │
│ confidence   │                               │ created_at         │
│ hypothesis   │                               └────────────────────┘
│ impact       │
│ remediation  │
│ created_at   │      ┌──────────────┐
│ updated_at   │─────►│ StateChange  │
└──────────────┘      │──────────────│
                      │ id PK        │
                      │ finding_id   │
                      │ from_status  │
                      │ to_status    │
                      │ reason       │
                      │ actor        │
                      │ created_at   │
                      └──────────────┘

┌──────────────┐      ┌────────────────────┐
│ ChatMessage  │      │      Report        │
│──────────────│      │────────────────────│
│ id PK        │      │ id PK              │
│ project_id FK│      │ project_id FK      │
│ role         │      │ format enum        │
│ content      │      │ content            │
│ tool_calls   │      │ created_at         │
│ created_at   │      └────────────────────┘
└──────────────┘
```

## 2. Enumerazioni

### `ProjectMode`
| Valore | Significato |
|---|---|
| `PASSIVE` | solo analisi offline di file/documentazione |
| `LAB` | attivi consentiti solo su target locali del progetto `lab/` |
| `AUTHORIZED_ASSESSMENT` | attivi consentiti sugli asset in scope del progetto |

### `FindingStatus` (macchina a stati)
| Valore | Significato | Transizioni ammesse |
|---|---|---|
| `INFO` | informazione utile, non una vulnerabilita | → POTENTIAL, FALSE_POSITIVE |
| `POTENTIAL` | ipotesi formulata | → CONFIRMED, FALSE_POSITIVE, NEEDS_VALIDATION |
| `NEEDS_VALIDATION` | servono prove ulteriori | → CONFIRMED, FALSE_POSITIVE, POTENTIAL |
| `CONFIRMED` | riproducibile con prove | → FIXED, FALSE_POSITIVE |
| `FALSE_POSITIVE` | non confermata / errore di analisi | → POTENTIAL (nuova ipotesi) |
| `FIXED` | correzione verificata con test di regressione | → CONFIRMED (regressione) |

Ogni transizione e scritta in `state_changes` con `reason` e `actor`. Il
servizio `services/findings.py` rifiuta transizioni non previste con HTTP 409.

### `FindingSeverity`
`INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` — non coincide con lo stato.

### `EvidenceKind`
`HTTP_REQUEST`, `HTTP_RESPONSE`, `TOOL_OUTPUT`, `CODE_SNIPPET`, `LOG_LINE`,
`SCREENSHOT_REF`, `MANUAL_NOTE`.

### `ScopeRuleKind`
`DOMAIN`, `URL_PREFIX`, `CIDR`, `FILE_PATH`, `REPOSITORY`, `API_ENDPOINT`,
`TECHNIQUE_ALLOW`, `TECHNIQUE_DENY`.

### `ScopeRuleEffect`
`ALLOW`, `DENY`. Regola `DENY` vince sempre su `ALLOW` (deny-by-default).

### `ToolRunStatus`
`SUCCESS`, `FAILED`, `TIMEOUT`, `UNAVAILABLE`, `DENIED`, `INVALID_INPUT`.

## 3. Regole di integrita applicate dal livello servizi

- Un asset `ScopeAsset` esiste solo se una `ScopeRule` lo ha prodotto: gli
  asset sono derivati, non inseriti a mano. Questo impedisce che un utente
  "autorizzi" un target solo dichiarandolo.
- `Finding` senza `evidence` non puo essere `CONFIRMED`.
- `ToolRun` con `status=DENIED` deve avere `error_text` che cita la regola
  di scope applicata.
- Non si archiviano segreti: i campi di evidenza passano da
  `core.security.redact()` prima della persistenza.

## 4. Politiche di cancellazione

- Un `Project` con finding non puo essere cancellato: si archivia
  (`archived_at`). Lo storico e parte del valore della piattaforma.
- Le `chat_messages` sono cancellabili per progetto (GDPR: minimizzazione).
- Gli `evidence` sono conservati con il finding; la cancellazione del finding
  rimuove le evidenze in cascata.

## 5. Mapping SQLAlchemy

| Tabella | Modello | Chiave primaria |
|---|---|---|
| `projects` | `models.project.Project` | `id` (Integer autoincrement) |
| `scope_policies` | `models.scope.ScopePolicy` | `id` |
| `scope_rules` | `models.scope.ScopeRule` | `id` |
| `scope_assets` | `models.scope.ScopeAsset` | `id` |
| `file_records` | `models.project.FileRecord` | `id` |
| `findings` | `models.finding.Finding` | `id` |
| `finding_evidences` | `models.finding.FindingEvidence` | `id` |
| `finding_state_changes` | `models.finding.StateChange` | `id` |
| `tool_runs` | `models.tool_run.ToolRun` | `id` |
| `chat_messages` | `models.chat.ChatMessage` | `id` |
| `reports` | `models.project.Report` | `id` |

Tutte le tabelle hanno `id` autoincrement e foreign key con `ondelete="CASCADE"`
dove il ciclo di vita lo prevede. Gli enum sono persistiti come stringhe
(VALUES) tramite `Enum(..., native_enum=False)` per portabilita SQLite/Postgres.
