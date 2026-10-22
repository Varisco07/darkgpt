"""Game Security Research: analisi, modding e sicurezza del multiplayer.

Confini del modulo:

- analisi su giochi **offline**, progetti **propri** o software **open
  source** con licenza compatibile;
- nessun meccanismo di evasione anti-cheat;
- nessuno strumento per compromettere altri giocatori o i loro account;
- gli indirizzi e gli offset riportati sono sempre **verificati** su
  strutture allocate dallo stesso processo, mai ipotizzati.
"""

from .analyzer import GameInfo, analyze_directory, suggest_tools
from .memory_lab import allocate_state, describe, scan_for_value, write_value
from .mod_creator import ModSpec, generate_mod, install_instructions
from .multiplayer import (
    ActionSpec,
    ArchitectureManifest,
    MovementAction,
    analyze_architecture,
    validate_movement,
)

__all__ = [
    "ActionSpec",
    "ArchitectureManifest",
    "GameInfo",
    "ModSpec",
    "MovementAction",
    "allocate_state",
    "analyze_architecture",
    "analyze_directory",
    "describe",
    "generate_mod",
    "install_instructions",
    "scan_for_value",
    "suggest_tools",
    "validate_movement",
    "write_value",
]
