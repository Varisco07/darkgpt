"""Configurazione centralizzata di DarkGPT.

Tutti i parametri arrivano da variabili d'ambiente con prefisso ``DARKGPT_``
oppure da un file ``.env`` nella root del progetto. I segreti non devono mai
essere scritti nel codice: questo modulo non ne contiene e non li logga.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Radice del repository: backend/app/core/config.py -> ../../..
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Impostazioni applicative lette dall'ambiente."""

    model_config = SettingsConfigDict(
        env_prefix="DARKGPT_",
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server -----------------------------------------------------------
    app_name: str = "DarkGPT"
    app_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    # `NoDecode` impedisce a pydantic-settings di decodificare il valore come
    # JSON prima del validatore: cosi' `.env` puo' contenere un CSV semplice.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Storage ----------------------------------------------------------
    database_url: str = f"sqlite:///{(REPO_ROOT / 'darkgpt.db').as_posix()}"
    sql_echo: bool = False

    # --- AI provider (interfaccia OpenAI-compatible) ----------------------
    # Base URL vuota = nessun provider configurato: la chat usa il provider di
    # fallback dichiarato e la piattaforma non effettua chiamate verso la
    # rete. Se e' impostata solo la API key si presume OpenAI.
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_timeout: float = 60.0
    llm_max_retries: int = 2

    # --- Contesto inviato al provider -------------------------------------
    llm_context_max_chars: int = 24000

    # --- Limiti operativi -------------------------------------------------
    http_max_requests_per_run: int = 50
    http_timeout: float = 15.0
    tool_timeout_default: int = 120
    tool_max_output_bytes: int = 2_000_000
    scan_max_files: int = 2000
    scan_max_file_bytes: int = 5_000_000

    # --- Percorsi ---------------------------------------------------------
    lab_root: Path = REPO_ROOT / "lab"

    # --- Sicurezza --------------------------------------------------------
    # Nessuna auth nell'MVP: l'accesso e' legato al binding su localhost.
    api_key: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accetta una lista, una stringa CSV o un array JSON nell'ambiente."""
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                try:
                    decoded = json.loads(text)
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, list):
                    return [str(item).strip() for item in decoded if str(item).strip()]
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @field_validator("lab_root")
    @classmethod
    def _absolute_lab_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()

    @field_validator("database_url")
    @classmethod
    def _absolute_sqlite_path(cls, value: str) -> str:
        """Rende assoluto il file di un database SQLite indicato con path relativo.

        `sqlite:///./darkgpt.db` dipende dalla directory di lavoro: avviando il
        backend da una cartella diversa si creerebbe un secondo database vuoto.
        Il percorso relativo viene quindi risolto rispetto alla root del repo.
        """
        prefix = "sqlite:///"
        if not value.startswith(prefix):
            return value
        raw = value[len(prefix) :]
        if not raw or raw.startswith(":memory:"):
            return value
        path = Path(raw)
        if path.is_absolute():
            return value
        return f"{prefix}{(REPO_ROOT / path).resolve().as_posix()}"

    @property
    def effective_llm_base_url(self) -> str:
        """Endpoint effettivamente usato dal provider.

        Se la base URL non e' impostata ma la API key c'e', si presume il
        provider OpenAI. Altrimenti non c'e' alcun endpoint: la piattaforma
        resta offline e la chat usa il provider di fallback dichiarato.
        """
        if self.llm_base_url.strip():
            return self.llm_base_url.strip()
        if self.llm_api_key.strip():
            return "https://api.openai.com/v1"
        return ""

    @property
    def llm_configured(self) -> bool:
        """True se esiste un endpoint utilizzabile per il provider LLM."""
        return bool(self.effective_llm_base_url)

    @property
    def llm_uses_mock(self) -> bool:
        """True quando non c'e' un endpoint configurato e si usa il provider mock."""
        return not self.llm_configured


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Restituisce le impostazioni (singleton, cache invalidabile nei test)."""
    return Settings()


def reset_settings_cache() -> None:
    """Pulisce la cache delle impostazioni. Usato dai test."""
    get_settings.cache_clear()
