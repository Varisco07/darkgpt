# Laboratorio DarkGPT

Ambienti di prova **locali**. Ogni applicazione e' intenzionalmente
vulnerabile o e' il riferimento della correzione.

> **Regola assoluta:** questi bersagli non vanno mai esposti su una rete e non
> contengono dati reali. Tutti i dati sono fittizi e vengono ricreati a ogni
> avvio su un file temporaneo.

## `sqli_app` — SQL injection

Due applicazioni affiancate con gli stessi endpoint:

| File | Ruolo | Endpoint |
|---|---|---|
| `sqli_app/vulnerable.py` | Bersaglio **vulnerabile** | `GET /search`, `GET /item`, `GET /report` |
| `sqli_app/fixed.py` | Riferimento **corretto** | gli stessi, con query parametrizzate |
| `sqli_app/db.py` | Database con dati fittizi | — |

Le vulnerabilita' del bersaglio:

1. `/search?q=` — il termine e' concatenato in una clausola `LIKE`
   (`f"SELECT ... WHERE name LIKE '%{q}%'"`).
2. `/item?id=` — l'identificativo e' concatenato in una clausola numerica,
   senza validazione del tipo.
3. `/report?name=` — il campo di ordinamento e' concatenato nella clausola
   `ORDER BY`.

Sintomi osservabili, verificati dai test automatici:

- il payload `' OR '1'='1` annulla il filtro e restituisce tutte le righe;
- un valore non numerico su `/item` produce un errore SQL propagato al
  cliente (disclosure di informazioni sul driver).

## Avvio

```bash
# Bersaglio vulnerabile
.venv/Scripts/python -m uvicorn lab.sqli_app.vulnerable:app --port 8100

# Versione corretta
.venv/Scripts/python -m uvicorn lab.sqli_app.fixed:app --port 8101
```

```bash
# Comportamento atteso del bersaglio
curl "http://127.0.0.1:8100/search?q=alice"      # 1 riga
curl "http://127.0.0.1:8100/search?q=%27%20OR%20%271%27=%271"  # 5 righe

# Comportamento della versione corretta
curl "http://127.0.0.1:8101/search?q=%27%20OR%20%271%27=%271"  # 0 righe
curl "http://127.0.0.1:8101/item?id=1%20OR%201%3D1"             # 422
```

## Test di regressione

`lab/tests/test_sqli_lab.py` verifica tre cose:

1. il bersaglio e' effettivamente iniettabile;
2. la versione corretta non lo e', a parita' di input legittimo;
3. l'analizzatore statico segnala `vulnerable.py` e **non** segnala
   `fixed.py`: e' il test che impedisce alla correzione di regredere.

```bash
.venv/Scripts/python -m pytest lab/tests -q
```

## Come aggiungere un nuovo bersaglio

1. Creare `lab/<nome>/` con l'applicazione vulnerabile e quella corretta.
2. Usare un database temporaneo con dati fittizi: nessun dato reale.
3. Aggiungere i test in `lab/tests/test_<nome>.py` seguendo lo schema
   esistente: comportamento vulnerabile, comportamento corretto, regressione
   dell'analizzatore.
