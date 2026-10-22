"""Versione CORRETTA dell'applicazione di laboratorio.

Stessi endpoint del bersaglio vulnerabile, ma con query parametrizzate e
validazione dell'input. Serve come riferimento per il test di regressione:
il comportamento deve essere identico per l'input legittimo e diverso per il
payload iniettivo.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .db import connect, create_database

app = FastAPI(
    title="DarkGPT SQLi Lab (fixed)",
    description="Versione corretta: query parametrizzate e validazione dell'input.",
    version="1.0.0",
)

#: Percorso del database del laboratorio.
DB_PATH = create_database()

#: Lunghezza massima accettata per un parametro di ricerca.
MAX_TERM_LENGTH = 64

#: Query di ordinamento: l'input e' mappato su query costanti, senza
#: concatenazione. La whitelist da sola non basterebbe a eliminare ogni
#: costruzione dinamica; mappare su query costanti e' il pattern consigliato.
REPORT_QUERIES = {
    "id": "SELECT id, label, amount FROM orders ORDER BY id",
    "label": "SELECT id, label, amount FROM orders ORDER BY label",
    "amount": "SELECT id, label, amount FROM orders ORDER BY amount",
}


@app.get("/health")
def health() -> dict:
    """Verifica che l'applicazione sia attiva."""
    return {"status": "ok", "db": str(DB_PATH)}


@app.get("/search")
def search(q: str = Query(default="", max_length=MAX_TERM_LENGTH)) -> dict:
    """Endpoint CORRETTO: il termine e' passato come parametro della query."""
    connection = connect(DB_PATH)
    try:
        cursor = connection.cursor()
        # CORRETTO: il valore non entra mai nella stringa SQL.
        query = "SELECT id, name, email FROM users WHERE name LIKE ? ORDER BY id"
        cursor.execute(query, (f"%{q}%",))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"query": query, "count": len(rows), "rows": rows}
    finally:
        connection.close()


@app.get("/item")
def item(id: int = Query(default=1, description="Identificativo numerico")) -> dict:
    """Endpoint CORRETTO: l'identificativo e' convertito a intero e parametrizzato."""
    connection = connect(DB_PATH)
    try:
        cursor = connection.cursor()
        query = "SELECT id, name, email FROM users WHERE id = ?"
        cursor.execute(query, (id,))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"query": query, "count": len(rows), "rows": rows}
    finally:
        connection.close()


@app.get("/report")
def report(name: str = Query(default="id", max_length=64)) -> dict:
    """Endpoint CORRETTO: l'ordinamento e' mappato su una query costante."""
    query = REPORT_QUERIES.get(name)
    if query is None:
        raise HTTPException(
            status_code=400,
            detail=f"campo di ordinamento non consentito: ammessi {sorted(REPORT_QUERIES)}",
        )
    connection = connect(DB_PATH)
    try:
        cursor = connection.cursor()
        # CORRETTO: la query e' una costante; l'input non la modifica.
        cursor.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]
        return {"query": query, "count": len(rows), "rows": rows}
    finally:
        connection.close()
