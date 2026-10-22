"""Test della configurazione: parsing delle variabili d'ambiente e percorsi."""

from __future__ import annotations

from app.core.config import REPO_ROOT, Settings


def test_cors_origins_da_csv() -> None:
    """Una stringa CSV resta supportata (formato consigliato in `.env`)."""
    settings = Settings(cors_origins="http://localhost:3000, http://127.0.0.1:3000")

    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_cors_origins_da_array_json() -> None:
    """Un array JSON viene accettato per compatibilita'."""
    settings = Settings(cors_origins='["http://a:1", "http://b:2"]')

    assert settings.cors_origins == ["http://a:1", "http://b:2"]


def test_sqlite_relativo_risolto_sulla_root() -> None:
    """`sqlite:///./file.db` non deve dipendere dalla directory di lavoro."""
    settings = Settings(database_url="sqlite:///./darkgpt-test.db")

    expected = (REPO_ROOT / "darkgpt-test.db").resolve().as_posix()
    assert settings.database_url == f"sqlite:///{expected}"


def test_sqlite_assoluto_invariato() -> None:
    """Un percorso gia' assoluto (o in-memory) non viene riscritto."""
    absolute = f"sqlite:///{(REPO_ROOT / 'darkgpt.db').as_posix()}"

    assert Settings(database_url=absolute).database_url == absolute
    assert Settings(database_url="sqlite:///:memory:").database_url == "sqlite:///:memory:"


def test_lab_root_relativo_risolto_sulla_root() -> None:
    """La radice del laboratorio segue la stessa regola."""
    settings = Settings(lab_root="lab")

    assert settings.lab_root == (REPO_ROOT / "lab").resolve()
