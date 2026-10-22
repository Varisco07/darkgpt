"""Mod Creator: genera lo scaffolding di un mod e ne gestisce backup e ripristino.

Il modulo produce **scaffolding**, non codice pronto all'uso: i file
generati sono scheletri con la struttura corretta, da completare. Nulla
viene installato senza esplicita richiesta e ogni file modificato viene
copiato in backup con verifica SHA-256, cosi' il ripristino e' sempre
possibile.

Vincoli: i mod generati sono per giochi offline, progetti propri o software
open source. Nessun output di questo modulo e' un meccanismo di evasione
anti-cheat o di compromissione di altri giocatori.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Target supportati per la generazione.
TARGET_BEPINEX = "bepinex"
TARGET_UE4SS = "ue4ss"
TARGET_GODOT = "godot"
TARGET_PYTHON = "python"

SUPPORTED_TARGETS = (TARGET_BEPINEX, TARGET_UE4SS, TARGET_GODOT, TARGET_PYTHON)


@dataclass
class ModSpec:
    """Specifica di un mod da generare."""

    name: str
    author: str = "anonymous"
    version: str = "0.1.0"
    description: str = ""
    target: str = TARGET_BEPINEX
    game_version: str = ""
    features: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializza la specifica."""
        return {
            "name": self.name,
            "author": self.author,
            "version": self.version,
            "description": self.description,
            "target": self.target,
            "game_version": self.game_version,
            "features": self.features,
        }


def _manifest(spec: ModSpec) -> str:
    """Genera il manifest del mod in formato JSON."""
    return json.dumps(spec.to_dict(), indent=2, ensure_ascii=False) + "\n"


def _bepinex_files(spec: ModSpec) -> dict[str, str]:
    """File di un plugin BepInEx (C#)."""
    class_name = (
        "".join(part.capitalize() for part in spec.name.replace("-", "_").split("_"))
        or "Mod"
    )
    source = f"""// {spec.name} v{spec.version}
// {spec.description}
//
// Scheletro generato da DarkGPT: completare la logica del mod.
// Compatibilita': verificare la versione del gioco ({spec.game_version or 'non verificata'}).

using BepInEx;
using UnityEngine;

namespace DarkGPT.Mods
{{
    [BepInPlugin("darkgpt.{spec.name}", "{spec.name}", "{spec.version}")]
    public class {class_name}Plugin : BasePlugin
    {{
        private void Awake()
        {{
            // Punto di ingresso: qui si agganciano gli eventi di gioco.
            Logger.LogInfo("{spec.name} caricato (v{spec.version})");
        }}

        private void OnUpdate()
        {{
            // Logica per frame. Evitare operazioni costose.
        }}
    }}
}}
"""
    project = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.0</TargetFramework>
    <AssemblyName>{spec.name}</AssemblyName>
    <LangVersion>latest</LangVersion>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="BepInEx">
      <HintPath>..\\..\\BepInEx\\core\\BepInEx.dll</HintPath>
    </Reference>
    <Reference Include="UnityEngine.CoreModule">
      <HintPath>..\\..\\BepInEx\\core\\UnityEngine.CoreModule.dll</HintPath>
    </Reference>
  </ItemGroup>
</Project>
"""
    return {
        f"{spec.name}.cs": source,
        f"{spec.name}.csproj": project,
        "manifest.json": _manifest(spec),
    }


def _ue4ss_files(spec: ModSpec) -> dict[str, str]:
    """File di un mod UE4SS (Lua)."""
    init = f"""-- {spec.name} v{spec.version}
-- {spec.description}
-- Scheletro generato da DarkGPT: completare la logica del mod.

RegisterMod({{
    Name = "{spec.name}",
    Author = "{spec.author}",
    Version = "{spec.version}",
    Description = "{spec.description}",
    UE4SSVersion = "3.0.0"
}})
"""
    main = f"""-- Logica principale del mod {spec.name}
-- La registrazione degli eventi dipende dalla versione del gioco:
-- verificarla prima di usare gli hook.

function Main()
    -- RegisterHook("/Script/Engine.PlayerController", "TakeDamage", "OnTakeDamage")
    print("[{spec.name}] caricato")
end
"""
    return {
        "mods.txt": f"{spec.name}\n",
        f"Scripts/{spec.name}/init.lua": init,
        f"Scripts/{spec.name}/main.lua": main,
        "manifest.json": _manifest(spec),
    }


def _godot_files(spec: ModSpec) -> dict[str, str]:
    """File di un addon Godot (GDScript)."""
    plugin_cfg = f"""[plugin]

name="{spec.name}"
description="{spec.description}"
author="{spec.author}"
version="{spec.version}"
script="plugin.gd"
"""
    plugin = f"""# {spec.name} v{spec.version}
# {spec.description}
# Scheletro generato da DarkGPT: completare la logica del mod.
@tool
extends EditorPlugin


func _enter_tree() -> void:
\tprint("[{spec.name}] caricato")


func _exit_tree() -> void:
\tpass
"""
    return {
        "plugin.cfg": plugin_cfg,
        "plugin.gd": plugin,
        "manifest.json": _manifest(spec),
    }


def _python_files(spec: ModSpec) -> dict[str, str]:
    """File di un mod Python generico (usato per prototipi e test)."""
    module = f'''"""{spec.name} v{spec.version}

{spec.description}

Scheletro generato da DarkGPT: completare la logica.
"""

VERSION = "{spec.version}"


def on_load() -> None:
    """Chiamato quando il mod viene caricato."""
    print("[{spec.name}] caricato")


def on_unload() -> None:
    """Chiamato quando il mod viene scaricato."""
    print("[{spec.name}] scaricato")
'''
    return {
        f"{spec.name.replace(' ', '_').lower()}.py": module,
        "manifest.json": _manifest(spec),
    }


_GENERATORS = {
    TARGET_BEPINEX: _bepinex_files,
    TARGET_UE4SS: _ue4ss_files,
    TARGET_GODOT: _godot_files,
    TARGET_PYTHON: _python_files,
}


def generate_mod(
    spec: ModSpec,
    out_dir: str | Path,
    overwrite: bool = False,
) -> list[Path]:
    """Genera lo scaffolding del mod in `out_dir` e restituisce i file creati.

    Non sovrascrive file esistenti, salvo esplicito `overwrite`: un mod non
    deve perdere modifiche per un errore di rigenerazione.
    """
    if spec.target not in _GENERATORS:
        raise ValueError(
            f"target non supportato: {spec.target}. Supportati: {sorted(_GENERATORS)}"
        )
    if not spec.name.strip():
        raise ValueError("il nome del mod e' obbligatorio")

    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for relative, content in _GENERATORS[spec.target](spec).items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not overwrite:
            continue
        path.write_text(content, encoding="utf-8")
        created.append(path)
    return created


def install_instructions(spec: ModSpec, game_dir: str | Path) -> str:
    """Genera le istruzioni di installazione e disinstallazione del mod."""
    game = Path(game_dir)
    if spec.target == TARGET_BEPINEX:
        install = f"1. Copia la cartella del mod in: {game / 'BepInEx' / 'plugins'}"
        uninstall = f"1. Elimina la cartella: {game / 'BepInEx' / 'plugins' / spec.name}"
    elif spec.target == TARGET_UE4SS:
        install = f"1. Copia la cartella in: {game / 'UE4SS' / 'Mods' / spec.name}"
        uninstall = f"1. Elimina la cartella: {game / 'UE4SS' / 'Mods' / spec.name}"
    elif spec.target == TARGET_GODOT:
        install = f"1. Copia la cartella in: {game / 'addons' / spec.name}"
        uninstall = f"1. Elimina la cartella: {game / 'addons' / spec.name}"
    else:
        install = f"1. Copia i file .py in: {game / 'mods'}"
        uninstall = f"1. Elimina i file .py del mod da: {game / 'mods'}"

    return (
        f"Installazione di '{spec.name}' v{spec.version}\n"
        f"{install}\n"
        "2. Avvia il gioco: il mod deve comparire nel log del loader.\n\n"
        f"Disinstallazione\n{uninstall}\n"
        "Nota: i percorsi indicati sono quelli convenzionali del loader; "
        "verificali sulla tua installazione prima di copiare i file."
    )


def sha256_file(path: str | Path) -> str:
    """Calcola l'hash SHA-256 di un file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class BackupEntry:
    """Una voce del backup: file originale, hash e percorso di destinazione."""

    original: str
    backup: str
    sha256: str
    size: int


def backup_files(
    paths: list[str | Path],
    backup_dir: str | Path,
    timestamp: str | None = None,
) -> list[BackupEntry]:
    """Copia i file indicati in una cartella di backup, verificandone l'hash.

    Il backup e' la garanzia di reversibilita': ogni file copiato viene
    riletto e confrontato con l'hash dell'originale.
    """
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    root = Path(backup_dir) / stamp
    root.mkdir(parents=True, exist_ok=True)

    entries: list[BackupEntry] = []
    for index, source in enumerate(paths):
        source_path = Path(source)
        if not source_path.is_file():
            continue
        destination = root / f"{index:03d}_{source_path.name}"
        shutil.copy2(source_path, destination)
        original_hash = sha256_file(source_path)
        backup_hash = sha256_file(destination)
        if original_hash != backup_hash:
            raise OSError(
                f"verifica del backup fallita per {source_path}: "
                f"{original_hash} != {backup_hash}"
            )
        entries.append(
            BackupEntry(
                original=str(source_path),
                backup=str(destination),
                sha256=original_hash,
                size=source_path.stat().st_size,
            )
        )
    write_backup_manifest(entries, root)
    return entries


def write_backup_manifest(entries: list[BackupEntry], backup_dir: str | Path) -> Path:
    """Scrive il manifest del backup (necessario al ripristino)."""
    root = Path(backup_dir)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    payload = [
        {
            "original": entry.original,
            "backup": Path(entry.backup).name,
            "sha256": entry.sha256,
            "size": entry.size,
        }
        for entry in entries
    ]
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest_path


def restore_files(backup_dir: str | Path) -> list[str]:
    """Ripristina i file da una cartella di backup, verificando l'hash.

    Un file il cui hash non corrisponde non viene ripristinato: il backup e'
    trattato come inaffidabile.
    """
    root = Path(backup_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"cartella di backup inesistente: {root}")

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    restored: list[str] = []
    for entry in manifest:
        backup_file = root / entry["backup"]
        if not backup_file.is_file():
            continue
        if sha256_file(backup_file) != entry["sha256"]:
            continue
        destination = Path(entry["original"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_file, destination)
        restored.append(str(destination))
    return restored
