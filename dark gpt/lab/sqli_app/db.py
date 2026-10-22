"""Database del laboratorio SQL injection.

Contiene esclusivamente dati fittizi, creati a runtime su un file temporaneo.
Nessun dato reale viene toccato.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

#: Dati fittizi inseriti nel database del laboratorio.
SEED_USERS = [
    (1, "alice", "alice@example.test"),
    (2, "bob", "bob@example.test"),
    (3, "carol", "carol@example.test"),
    (4, "dave", "dave@example.test"),
    (5, "erin", "erin@example.test"),
]

SEED_ORDERS = [
    (1, 1, "ordine A", 19.99),
    (2, 2, "ordine B", 45.00),
    (3, 1, "ordine C", 120.50),
]


def create_database(path: Path | None = None) -> Path:
    """Crea il database del laboratorio con i dati fittizi.

    Se `path` non e' indicato, usa un file temporaneo.
    """
    target = path or Path(tempfile.mkdtemp(prefix="darkgpt_lab_")) / "lab.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    try:
        cursor = connection.cursor()
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("DROP TABLE IF EXISTS orders")
        cursor.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)"
        )
        cursor.execute(
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, "
            "label TEXT, amount REAL)"
        )
        cursor.executemany("INSERT INTO users (id, name, email) VALUES (?, ?, ?)", SEED_USERS)
        cursor.executemany(
            "INSERT INTO orders (id, user_id, label, amount) VALUES (?, ?, ?, ?)",
            SEED_ORDERS,
        )
        connection.commit()
    finally:
        connection.close()
    return target


def connect(path: Path) -> sqlite3.Connection:
    """Apre una connessione al database del laboratorio."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection
