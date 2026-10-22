"""Test del modulo Game Security: analyzer, mod creator, memory lab, multiplayer."""

from __future__ import annotations

import json

import pytest

from game.analyzer import (
    ENGINE_CUSTOM,
    ENGINE_GODOT,
    ENGINE_UNITY,
    ENGINE_UNREAL,
    analyze_directory,
    suggest_tools,
)
from game.memory_lab import (
    allocate_state,
    describe,
    field_offsets,
    scan_for_value,
    write_value,
)
from game.mod_creator import (
    TARGET_BEPINEX,
    TARGET_GODOT,
    TARGET_PYTHON,
    TARGET_UE4SS,
    ModSpec,
    backup_files,
    generate_mod,
    install_instructions,
    restore_files,
)
from game.multiplayer import (
    ActionSpec,
    ArchitectureManifest,
    MovementAction,
    analyze_architecture,
    validate_movement,
)


# ---------------------------------------------------------------------------
# Game Analyzer
# ---------------------------------------------------------------------------


def test_detects_unity(tmp_path):
    (tmp_path / "Game_Data" / "Managed").mkdir(parents=True)
    (tmp_path / "Game_Data" / "Managed" / "Assembly-CSharp.dll").write_bytes(b"MZ")

    info = analyze_directory(tmp_path)
    assert info.engine == ENGINE_UNITY
    assert info.modding_feasibility == "parziale"


def test_detects_unreal_and_version(tmp_path):
    build = tmp_path / "Game" / "Engine" / "Build"
    build.mkdir(parents=True)
    (build / "Build.version").write_text(
        '{"MajorVersion": 5, "MinorVersion": 3, "PatchVersion": 2}', encoding="utf-8"
    )

    info = analyze_directory(tmp_path)
    assert info.engine == ENGINE_UNREAL
    assert info.engine_version == "5"


def test_detects_godot_project(tmp_path):
    (tmp_path / "project.godot").write_text("config_version=5\n", encoding="utf-8")

    info = analyze_directory(tmp_path)
    assert info.engine == ENGINE_GODOT
    assert info.engine_version == "5"


def test_detects_modding_framework(tmp_path):
    (tmp_path / "BepInEx" / "plugins").mkdir(parents=True)
    (tmp_path / "BepInEx" / "plugins" / "MyMod.dll").write_bytes(b"MZ")

    info = analyze_directory(tmp_path)
    assert "BepInEx" in info.modding_frameworks
    assert info.modding_feasibility == "supportato"


def test_unknown_engine_is_reported_not_guessed(tmp_path):
    (tmp_path / "file.txt").write_text("niente di riconoscibile", encoding="utf-8")

    info = analyze_directory(tmp_path)
    assert info.engine == ENGINE_CUSTOM
    assert any("non riconosciuto" in note for note in info.notes)
    # Nessun dato viene inventato sulla versione.
    assert info.engine_version == ""


def test_missing_path_is_handled(tmp_path):
    info = analyze_directory(tmp_path / "inesistente")
    assert info.engine == ENGINE_CUSTOM
    assert info.notes


def test_suggested_tools_depend_on_engine(tmp_path):
    (tmp_path / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    suggestions = suggest_tools(analyze_directory(tmp_path))
    assert any("Godot" in item for item in suggestions)


def test_saved_and_config_files_are_detected(tmp_path):
    (tmp_path / "game.ini").write_text("[video]\n", encoding="utf-8")
    (tmp_path / "savegame01.dat").write_text("dati", encoding="utf-8")

    info = analyze_directory(tmp_path)
    assert "game.ini" in info.config_files
    assert "savegame01.dat" in info.save_files


# ---------------------------------------------------------------------------
# Mod Creator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("target", "expected_suffix"),
    [
        (TARGET_BEPINEX, ".cs"),
        (TARGET_UE4SS, ".lua"),
        (TARGET_GODOT, ".gd"),
        (TARGET_PYTHON, ".py"),
    ],
)
def test_generate_mod_creates_expected_files(tmp_path, target, expected_suffix):
    spec = ModSpec(name="Dark Demo", target=target, description="mod di prova")
    created = generate_mod(spec, tmp_path / "mod")

    assert created
    assert any(path.suffix == expected_suffix for path in created)
    assert any(path.name == "manifest.json" for path in created)


def test_generated_manifest_is_valid_json(tmp_path):
    spec = ModSpec(name="Dark Demo", target=TARGET_PYTHON)
    generate_mod(spec, tmp_path / "mod")
    manifest = json.loads((tmp_path / "mod" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "Dark Demo"
    assert manifest["target"] == TARGET_PYTHON


def test_generate_mod_does_not_overwrite_by_default(tmp_path):
    spec = ModSpec(name="Dark Demo", target=TARGET_PYTHON)
    generate_mod(spec, tmp_path / "mod")
    (tmp_path / "mod" / "dark_demo.py").write_text("# modificato a mano", encoding="utf-8")

    second = generate_mod(spec, tmp_path / "mod")
    assert second == []
    assert (tmp_path / "mod" / "dark_demo.py").read_text(encoding="utf-8") == (
        "# modificato a mano"
    )


def test_generate_mod_rejects_unknown_target(tmp_path):
    with pytest.raises(ValueError):
        generate_mod(ModSpec(name="X", target="inesistente"), tmp_path / "mod")


def test_install_instructions_mention_install_and_uninstall(tmp_path):
    text = install_instructions(ModSpec(name="Dark Demo"), tmp_path)
    assert "Installazione" in text
    assert "Disinstallazione" in text
    assert "verificali" in text


def test_backup_and_restore_roundtrip(tmp_path):
    original = tmp_path / "game.ini"
    original.write_text("[video]\nfullscreen=1\n", encoding="utf-8")

    entries = backup_files([original], tmp_path / "backups", timestamp="t1")
    assert len(entries) == 1
    assert entries[0].sha256

    original.write_text("corrotto\n", encoding="utf-8")
    restored = restore_files(tmp_path / "backups" / "t1")

    assert restored == [str(original)]
    assert original.read_text(encoding="utf-8") == "[video]\nfullscreen=1\n"


def test_restore_skips_tampered_backup(tmp_path):
    original = tmp_path / "game.ini"
    original.write_text("originale\n", encoding="utf-8")
    entries = backup_files([original], tmp_path / "backups", timestamp="t1")

    with open(entries[0].backup, "w", encoding="utf-8") as handle:
        handle.write("manomesso\n")

    original.write_text("cambiato\n", encoding="utf-8")
    restored = restore_files(tmp_path / "backups" / "t1")

    assert restored == []
    assert original.read_text(encoding="utf-8") == "cambiato\n"


# ---------------------------------------------------------------------------
# Memory Research Lab
# ---------------------------------------------------------------------------


def test_allocate_and_describe_state():
    handle = allocate_state(health=75, ammo=12)
    state = describe(handle)

    assert state["fields"]["salute"]["value"] == 75
    assert state["fields"]["munizioni"]["value"] == 12
    assert state["base_address"] > 0
    assert state["size_bytes"] > 0


def test_scan_finds_value_with_verified_offset():
    handle = allocate_state(health=42)
    candidates = scan_for_value(handle, 42)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.field == "health"
    assert candidate.verified is True
    assert candidate.offset == field_offsets()["health"]


def test_scan_returns_nothing_for_absent_value():
    handle = allocate_state(health=100)
    assert scan_for_value(handle, 9999) == []


def test_write_value_is_verified_by_reread():
    handle = allocate_state(ammo=30)
    assert write_value(handle, "ammo", 999) is True
    assert handle.state.ammo == 999


def test_write_value_rejects_unknown_field():
    handle = allocate_state()
    with pytest.raises(KeyError):
        write_value(handle, "campo_inesistente", 1)


# ---------------------------------------------------------------------------
# Multiplayer Security Research
# ---------------------------------------------------------------------------


def test_architecture_analysis_flags_unvalidated_action():
    manifest = ArchitectureManifest(
        game="Gioco di prova",
        actions=[
            ActionSpec(
                name="fire",
                client_sent_fields=["damage", "target_id"],
                server_validated=False,
            )
        ],
    )
    findings = analyze_architecture(manifest)
    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert "fire" in findings[0].title


def test_architecture_analysis_flags_conflicting_authority():
    manifest = ArchitectureManifest(
        game="Gioco di prova",
        actions=[
            ActionSpec(
                name="move",
                client_sent_fields=["position"],
                server_validated=True,
                authoritative_fields=["position"],
            )
        ],
    )
    findings = analyze_architecture(manifest)
    assert any(finding.severity == "CRITICAL" for finding in findings)


def test_architecture_analysis_flags_unencrypted_transport():
    manifest = ArchitectureManifest(game="G", transport="UDP", encrypted=False)
    findings = analyze_architecture(manifest)
    assert any(finding.category == "Transport Security" for finding in findings)


def test_sound_architecture_produces_no_findings():
    manifest = ArchitectureManifest(
        game="Gioco corretto",
        actions=[
            ActionSpec(
                name="move",
                client_sent_fields=["desired_velocity"],
                server_validated=True,
                authoritative_fields=["position", "velocity"],
            )
        ],
    )
    assert analyze_architecture(manifest) == []


def test_validate_movement_accepts_plausible_action():
    action = MovementAction(x=0.3, y=0.0, z=0.0, dt_ms=50)
    result = validate_movement(action)
    assert result.accepted is True
    assert result.corrected is not None


def test_validate_movement_rejects_teleport():
    action = MovementAction(x=500.0, y=0.0, z=0.0, dt_ms=50)
    result = validate_movement(action)
    assert result.accepted is False
    assert "non plausibile" in result.reason


def test_validate_movement_rejects_impossible_delta():
    action = MovementAction(x=0.0, y=0.0, z=0.0, dt_ms=0)
    result = validate_movement(action)
    assert result.accepted is False
    assert "delta temporale" in result.reason
