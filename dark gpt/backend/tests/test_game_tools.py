"""Test dei tool Game Security esposti dal backend."""

from __future__ import annotations

from pathlib import Path

from app.models.enums import ProjectMode, ToolRunStatus
from app.tools.builtin import GAME_ANALYZE_SPEC, GAME_MOD_SCAFFOLD_SPEC
from app.tools.registry import registry
from app.tools.runner import run_tool


def _unity_game(root: Path) -> Path:
    """Crea una cartella con le firme di un gioco Unity."""
    managed = root / "Game_Data" / "Managed"
    managed.mkdir(parents=True, exist_ok=True)
    (managed / "Assembly-CSharp.dll").write_bytes(b"MZ")
    return root


def test_game_tools_are_registered():
    assert registry.has(GAME_ANALYZE_SPEC.name)
    assert registry.has(GAME_MOD_SCAFFOLD_SPEC.name)
    assert registry.availability(GAME_ANALYZE_SPEC.name).status == "available"


def test_game_analyze_detects_engine(session, project, tmp_path):
    """Il tool analizza la cartella indicata e riconosce il motore."""
    project.mode = ProjectMode.LAB
    project.root_path = str(tmp_path)
    session.flush()

    game_dir = _unity_game(tmp_path / "gioco")

    result = run_tool(
        session,
        project,
        GAME_ANALYZE_SPEC.name,
        {"path": str(game_dir)},
    )

    assert result.status is ToolRunStatus.SUCCESS
    assert result.output["engine"] == "Unity"
    assert result.output["suggested_tools"]


def test_game_analyze_denies_path_outside_jail(session, project, tmp_path):
    """Un percorso fuori dalla root del progetto viene negato."""
    project.mode = ProjectMode.LAB
    project.root_path = str(tmp_path / "progetto")
    (tmp_path / "progetto").mkdir()
    session.flush()

    result = run_tool(
        session,
        project,
        GAME_ANALYZE_SPEC.name,
        {"path": str(tmp_path / "altro")},
    )

    assert result.status is ToolRunStatus.DENIED


def test_game_mod_scaffold_requires_confirmation(session, project, tmp_path):
    """La generazione scrive file: senza conferma non parte."""
    project.mode = ProjectMode.LAB
    project.root_path = str(tmp_path)
    session.flush()

    result = run_tool(
        session,
        project,
        GAME_MOD_SCAFFOLD_SPEC.name,
        {"output_dir": str(tmp_path / "mod"), "name": "Dark Demo", "target": "python"},
        confirm=False,
    )

    assert result.status is ToolRunStatus.DENIED
    assert not (tmp_path / "mod").exists()


def test_game_mod_scaffold_creates_files_with_confirmation(session, project, tmp_path):
    project.mode = ProjectMode.LAB
    project.root_path = str(tmp_path)
    session.flush()

    result = run_tool(
        session,
        project,
        GAME_MOD_SCAFFOLD_SPEC.name,
        {
            "output_dir": str(tmp_path / "mod"),
            "name": "Dark Demo",
            "target": "python",
            "author": "tester",
        },
        confirm=True,
    )

    assert result.status is ToolRunStatus.SUCCESS
    assert result.output["created"]
    assert (tmp_path / "mod" / "dark_demo.py").is_file()
    assert "Installazione" in result.output["instructions"]


def test_game_mod_scaffold_is_not_exposed_to_the_model():
    """Il tool che scrive file non deve essere chiamabile dal modello."""
    from app.ai.tools import build_tool_schemas

    names = {schema["function"]["name"] for schema in build_tool_schemas()}
    assert GAME_MOD_SCAFFOLD_SPEC.name not in names
    assert GAME_ANALYZE_SPEC.name in names
