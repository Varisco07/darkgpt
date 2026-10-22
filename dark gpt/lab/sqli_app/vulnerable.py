"""Applicazione di laboratorio INTENZIONALMENTE VULNERABILE a SQL injection.

Questo file e' un bersaglio didattico. Non deve mai essere esposto su una
rete: si usa esclusivamente in locale, con dati fittizi, per verificare che
l'analizzatore statico di DarkGPT riconosca le query costruite per
interpolazione e che i test dinamici distinguano il comportamento
vulnerabile da quello corretto.

Le vulnerabilita' sono:
- `GET /search?q=`  -> concatenazione in una clausola LIKE
- `GET /item?id=`   -> concatenazione in una clausola numerica
- `GET /report?name=` -> concatenazione in un ordinamento
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query

from .db import connect, create_database

app = FastAPI(
    title="DarkGPT SQLi Lab (vulnerable)",
    description=(
        "Bersaglio didattico INTENZIONALMENTE vulnerabile. "
        "Usare solo in locale, con dati fittizi."
    ),
    version="1.0.0",
)

#: Percorso del database del laboratorio.
DB_PATH = create_database()


@app.get("/health")
def health() -> dict:
    """Verifica che l'applicazione sia attiva."""
    return {"status": "ok", "db": str(DB_PATH)}


@app.get("/search")
def search(q: str = Query(default="", description="Termine di ricerca")) -> dict:
    """Endpoint VULNERABILE: il termine e' concatenato nella query SQL."""
    connection = connect(DB_PATH)
    try:
        cursor = connection.cursor()
        # VULNERABILE: il valore di `q` entra direttamente nella stringa SQL.
        query = f"SELECT id, name, email FROM users WHERE name LIKE '%{q}%' ORDER BY id"
        cursor.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]
        return {"query": query, "count": len(rows), "rows": rows}
    finally:
        connection.close()


@app.get("/item")
def item(id: str = Query(default="1", description="Identificativo")) -> dict:
    """Endpoint VULNERABILE: l'identificativo e' concatenato senza parametri."""
    connection = connect(DB_PATH)
    try:
        cursor = connection.cursor()
        # VULNERABILE: nessun uso di parametri, nessuna validazione del tipo.
        query = f"SELECT id, name, email FROM users WHERE id = {id}"
        cursor.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]
        return {"query": query, "count": len(rows), "rows": rows}
    finally:
        connection.close()


@app.get("/report")
def report(name: str = Query(default="alice", description="Nome utente")) -> dict:
    """Endpoint VULNERABILE: il nome e' concatenato in un ordinamento."""
    connection = connect(DB_PATH)
    try:
        cursor = connection.cursor()
        # VULNERABILE: l'ordinamento e' costruito per concatenazione.
        query = f"SELECT id, label, amount FROM orders ORDER BY {name}"
        cursor.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]
        return {"query": query, "count": len(rows), "rows": rows}
    finally:
        connection.close()
