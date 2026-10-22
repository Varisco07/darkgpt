"""Game Analyzer: riconosce il motore di gioco e le vie di modding.

Regole di impiego (non negoziabili, valgono per tutto il modulo):

- l'analisi si fa su giochi **offline**, su progetti **propri** o su software
  **open source** con licenza che lo consenta;
- il modulo non produce bypass di anti-cheat e non e' usabile per il
  multiplayer pubblico;
- non viene mai inventato un indirizzo, un offset o una funzione: ogni dato
  restituito e' o derivato dai file presenti o dichiarato non verificato.

Il riconoscimento del motore e' basato sui **file presenti** nella cartella
esaminata: e' analisi statica e passiva, non esecuzione del gioco.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Motori riconosciuti.
ENGINE_UNITY = "Unity"
ENGINE_UNREAL = "Unreal Engine"
ENGINE_GODOT = "Godot"
ENGINE_RPG_MAKER = "RPG Maker"
ENGINE_GAMEMAKER = "GameMaker"
ENGINE_RENPY = "Ren'Py"
ENGINE_CUSTOM = "Custom / sconosciuto"

#: Pattern di file che identificano ciascun motore.
ENGINE_SIGNATURES: dict[str, tuple[str, ...]] = {
    ENGINE_UNITY: (
        "*/Managed/Assembly-CSharp.dll",
        "*/globalgamemanagers",
        "*/data.unity3d",
        "*/il2cpp_data/Metadata/global-metadata.dat",
    ),
    ENGINE_UNREAL: (
        "*/Engine/Binaries/*/Engine.ini",
        "*/Engine/Build/Build.version",
        "*.uproject",
        "*/Content/Paks/*.pak",
    ),
    ENGINE_GODOT: ("project.godot", "*.tscn", "*.tres"),
    ENGINE_RPG_MAKER: ("*/data/Actors.json", "*/data/System.json"),
    ENGINE_GAMEMAKER: ("*.yy", "*/data.win"),
    ENGINE_RENPY: ("*/game.rpy", "*/game.rpa"),
}

#: Framework di modding riconosciuti.
MODDING_FRAMEWORKS: dict[str, tuple[str, ...]] = {
    "BepInEx": ("BepInEx/", "*/BepInEx/plugins/", "BepInEx.cfg"),
    "MelonLoader": ("MelonLoader/", "*/Mods/*.dll"),
    "UE4SS": ("UE4SS/", "*/UE4SS/Mods/"),
    "REFramework": ("*/REFramework/",),
    "Godot addon": ("*/addons/*/plugin.cfg",),
    "Mod loader generico": ("mods/", "*/plugins/*.py"),
}

#: Estensioni dei file di configurazione.
CONFIG_PATTERNS = (".ini", ".cfg", ".conf", ".yaml", ".yml", ".json", ".toml")

#: Marker dei file di salvataggio.
SAVE_PATTERNS = ("save", "sav", "slot", "profile", "savegame", "progress")


@dataclass
class GameInfo:
    """Esito dell'analisi di una cartella di gioco."""

    root: str
    engine: str = ENGINE_CUSTOM
    engine_version: str = ""
    languages: list[str] = field(default_factory=list)
    modding_frameworks: list[str] = field(default_factory=list)
    modding_entrypoints: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    save_files: list[str] = field(default_factory=list)
    executables: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def modding_feasibility(self) -> str:
        """Valutazione della fattibilita' del modding per questo gioco."""
        if self.modding_frameworks:
            return "supportato"
        if self.engine in (ENGINE_UNITY, ENGINE_UNREAL, ENGINE_GODOT):
            return "parziale"
        return "sconosciuto"

    def to_dict(self) -> dict[str, Any]:
        """Serializza l'analisi in una struttura JSON."""
        return {
            "root": self.root,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "languages": self.languages,
            "modding_frameworks": self.modding_frameworks,
            "modding_entrypoints": self.modding_entrypoints,
            "config_files": self.config_files,
            "save_files": self.save_files,
            "executables": self.executables,
            "modding_feasibility": self.modding_feasibility,
            "notes": self.notes,
        }


def _matches(root: Path, pattern: str) -> list[Path]:
    """Trova i file che corrispondono a un pattern, senza scendere ovunque."""
    return [path for path in root.glob(pattern) if path.is_file()]


def _detect_engine(root: Path) -> tuple[str, list[str]]:
    """Riconosce il motore di gioco e restituisce (motore, prove trovate)."""
    for engine, patterns in ENGINE_SIGNATURES.items():
        for pattern in patterns:
            if _matches(root, pattern):
                return engine, [pattern]
    return ENGINE_CUSTOM, []


def _detect_engine_version(root: Path, engine: str) -> str:
    """Cerca la versione del motore nei file di metadati, se presenti."""
    candidates: list[Path] = []
    if engine == ENGINE_UNREAL:
        candidates = _matches(root, "*/Engine/Build/Build.version")
    elif engine == ENGINE_GODOT:
        candidates = _matches(root, "project.godot")
    elif engine == ENGINE_UNITY:
        candidates = _matches(root, "*/globalgamemanagers")

    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        match = re.search(r'"(?:MajorVersion|MinorVersion|PatchVersion)"\s*:\s*"?(\d+)', text)
        if match:
            return match.group(1)
        match = re.search(r"config_version=(\d+)", text)
        if match:
            return match.group(1)
    return ""


def _detect_languages(root: Path) -> list[str]:
    """Individua i linguaggi di scripting presenti nella cartella."""
    mapping = {
        ".cs": "C#",
        ".lua": "Lua",
        ".gd": "GDScript",
        ".py": "Python",
        ".js": "JavaScript",
        ".rb": "Ruby",
        ".rpy": "Ren'Py",
    }
    languages: set[str] = set()
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in mapping:
            languages.add(mapping[path.suffix.lower()])
        if len(languages) > 8:
            break
    return sorted(languages)


def _add_unique(target: list[str], value: str) -> None:
    """Aggiunge un valore a una lista senza duplicati."""
    if value not in target:
        target.append(value)


def analyze_directory(root: str | Path, max_entries: int = 20000) -> GameInfo:
    """Analizza una cartella di gioco e restituisce le informazioni trovate.

    L'analisi e' statica: legge i nomi dei file e, quando sono file di testo
    piccoli, il loro contenuto. Non esegue il gioco e non modifica nulla.
    """
    root_path = Path(root)
    info = GameInfo(root=str(root_path))

    if not root_path.exists() or not root_path.is_dir():
        info.notes.append("percorso inesistente o non directory: analisi impossibile")
        return info

    engine, evidence = _detect_engine(root_path)
    info.engine = engine
    info.engine_version = _detect_engine_version(root_path, engine)
    if evidence:
        info.notes.append(f"motore riconosciuto tramite: {', '.join(evidence)}")
    else:
        info.notes.append(
            "motore non riconosciuto: nessuna firma trovata. "
            "Gli indirizzi e le funzioni non possono essere dedotti senza "
            "analisi dinamica, e non vengono ipotizzati."
        )

    entries = 0
    for path in root_path.rglob("*"):
        entries += 1
        if entries > max_entries:
            info.notes.append(f"analisi interrotta dopo {max_entries} elementi")
            break
        if not path.is_file():
            continue
        relative = path.relative_to(root_path).as_posix()
        suffix = path.suffix.lower()
        name_lower = path.name.lower()

        if suffix in CONFIG_PATTERNS:
            _add_unique(info.config_files, relative)
        if any(marker in name_lower for marker in SAVE_PATTERNS):
            _add_unique(info.save_files, relative)
        if suffix == ".exe" or (os.name == "posix" and os.access(path, os.X_OK)):
            _add_unique(info.executables, relative)

        for framework, patterns in MODDING_FRAMEWORKS.items():
            for pattern in patterns:
                if pattern.endswith("/"):
                    if relative.startswith(pattern) or f"/{pattern}" in f"/{relative}":
                        _add_unique(info.modding_frameworks, framework)
                        _add_unique(info.modding_entrypoints, relative)
                elif path.match(pattern):
                    _add_unique(info.modding_frameworks, framework)
                    _add_unique(info.modding_entrypoints, relative)

    info.languages = _detect_languages(root_path)
    info.config_files = sorted(info.config_files)[:50]
    info.save_files = sorted(info.save_files)[:50]
    info.executables = sorted(info.executables)[:30]
    return info


def suggest_tools(info: GameInfo) -> list[str]:
    """Suggerisce gli strumenti compatibili con il gioco analizzato.

    I suggerimenti sono basati sul motore e sui framework rilevati: sono
    indicazioni di partenza, non verifiche di compatibilita' con una
    specifica versione del gioco.
    """
    suggestions: list[str] = []
    if info.engine == ENGINE_UNITY:
        suggestions.append("BepInEx (plugin C# per Unity mono/il2cpp)")
        suggestions.append("MelonLoader (alternativa con supporto il2cpp)")
    elif info.engine == ENGINE_UNREAL:
        suggestions.append("UE4SS (scripting Lua in-process)")
        suggestions.append("REFramework (reverse engineering e modding)")
    elif info.engine == ENGINE_GODOT:
        suggestions.append("Godot GDScript / addon nativi")
    elif info.engine == ENGINE_GAMEMAKER:
        suggestions.append("UndertaleModTool (GMML) per le risorse")
    elif info.engine == ENGINE_RENPY:
        suggestions.append("script patching Ren'Py")
    else:
        suggestions.append("analisi statica delle risorse (nessun framework noto)")

    if info.modding_frameworks:
        suggestions.append(
            "framework gia' presente: " + ", ".join(sorted(info.modding_frameworks))
        )
    return suggestions
