"""Memory Research Lab: dimostrazione del metodo di modifica dei valori.

Cosa fa, in concreto:

- alloca una struttura di gioco **nello stesso processo** che esegue lo
  script (tramite `ctypes`), con campi tipo salute, munizioni e punteggio;
- espone una scansione dei campi per un valore, che restituisce **offset
  verificati** e l'indirizzo reale dell'area allocata;
- permette di scrivere un valore e **rileggerlo** per confermare la modifica.

Cosa NON fa, per scelta:

- non scansiona e non modifica la memoria di altri processi: gli indirizzi
  restituiti sono quelli di un buffer creato qui, e sono quindi verificabili
  direttamente;
- non produce strumenti di evasione anti-cheat.

Il valore del laboratorio e' didattico: mostra il *metodo* (cercare ->
candidati -> modificare -> verificare) che si applica a un ambiente di test
autorizzato, con dati e processi propri.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Any


class PlayerState(ctypes.Structure):
    """Struttura di gioco dimostrativa: i campi sono quelli che un trainer
    cercherebbe in un'applicazione di test."""

    _fields_ = [
        ("health", ctypes.c_int),
        ("armor", ctypes.c_int),
        ("ammo", ctypes.c_int),
        ("score", ctypes.c_int),
        ("level", ctypes.c_int),
        ("flags", ctypes.c_int),
        ("name", ctypes.c_char * 16),
    ]


#: Etichetta logica di ogni campo numerico, nell'ordine della struttura.
FIELD_LABELS: dict[str, str] = {
    "health": "salute",
    "armor": "armatura",
    "ammo": "munizioni",
    "score": "punteggio",
    "level": "livello",
    "flags": "flag",
}


@dataclass
class StateHandle:
    """Handle sulla struttura allocata, con i suoi metadati."""

    buffer: ctypes.Array
    state: PlayerState

    @property
    def base_address(self) -> int:
        """Indirizzo reale dell'area allocata (verificabile con un debugger)."""
        return ctypes.addressof(self.buffer)

    @property
    def size(self) -> int:
        """Dimensione della struttura in byte."""
        return ctypes.sizeof(PlayerState)


@dataclass
class MemoryCandidate:
    """Un candidato trovato durante la scansione."""

    label: str
    field: str
    offset: int
    address: int
    value: int
    verified: bool


def allocate_state(
    health: int = 100,
    armor: int = 50,
    ammo: int = 30,
    score: int = 1000,
    level: int = 3,
    flags: int = 0,
    name: bytes = b"player",
) -> StateHandle:
    """Alloca e inizializza la struttura di gioco dimostrativa."""
    buffer = ctypes.create_string_buffer(ctypes.sizeof(PlayerState))
    state = PlayerState.from_buffer(buffer)
    state.health = health
    state.armor = armor
    state.ammo = ammo
    state.score = score
    state.level = level
    state.flags = flags
    state.name = name[:15]
    return StateHandle(buffer=buffer, state=state)


def field_offsets() -> dict[str, int]:
    """Offset dei campi della struttura, calcolati da ctypes.

    Sono offset **verificati**: derivano dalla definizione della struttura e
    sono leggibili con un debugger sul buffer allocato.
    """
    offsets: dict[str, int] = {}
    for name, _type in PlayerState._fields_:
        field = getattr(PlayerState, name)
        offsets[name] = int(field.offset)
    return offsets


def scan_for_value(handle: StateHandle, value: int) -> list[MemoryCandidate]:
    """Cerca un valore nei campi della struttura e restituisce i candidati.

    E' l'equivalente del primo passo di un value scan: trovare dove un
    valore vive in memoria. Qui la ricerca e' limitata alla struttura creata
    dal laboratorio, quindi i risultati sono certi.
    """
    offsets = field_offsets()
    base = handle.base_address
    candidates: list[MemoryCandidate] = []
    for name in FIELD_LABELS:
        current = int(getattr(handle.state, name))
        if current != value:
            continue
        offset = offsets[name]
        # Rileggere il valore dalla memoria all'offset per confermare.
        verified = ctypes.c_int.from_address(base + offset).value == value
        candidates.append(
            MemoryCandidate(
                label=FIELD_LABELS[name],
                field=name,
                offset=offset,
                address=base + offset,
                value=current,
                verified=verified,
            )
        )
    return candidates


def write_value(handle: StateHandle, field: str, value: int) -> bool:
    """Scrive un valore nel campo indicato e verifica la scrittura.

    Restituisce True se il valore riletto coincide con quello scritto.
    """
    if field not in FIELD_LABELS:
        raise KeyError(f"campo sconosciuto: {field}. Disponibili: {sorted(FIELD_LABELS)}")
    setattr(handle.state, field, int(value))
    return int(getattr(handle.state, field)) == int(value)


def describe(handle: StateHandle) -> dict[str, Any]:
    """Restituisce lo stato corrente della struttura, con gli offset."""
    offsets = field_offsets()
    base = handle.base_address
    values: dict[str, Any] = {}
    for name, label in FIELD_LABELS.items():
        values[label] = {
            "field": name,
            "value": int(getattr(handle.state, name)),
            "offset": offsets[name],
            "address": base + offsets[name],
        }
    return {
        "base_address": base,
        "size_bytes": handle.size,
        "fields": values,
        "name": handle.state.name.decode("utf-8", errors="replace"),
    }
