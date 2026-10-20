"""Configuracao via variaveis de ambiente / arquivo .env (sem aspas nos valores!)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _default_db_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "Mixxx" / "mixxxdb.sqlite"
    return Path.home() / ".mixxx" / "mixxxdb.sqlite"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip().strip('"').strip("'")


@dataclass
class Config:
    # --- ponte MIDI ---
    midi_port_hint: str = field(default_factory=lambda: _env("AUTODJ_MIDI_PORT", "AutoDJ"))
    # --- biblioteca do Mixxx (somente leitura) ---
    db_path: Path = field(default_factory=lambda: Path(_env("AUTODJ_DB", str(_default_db_path()))))
    # --- IA: auto | gemini | ollama | off ---
    ai_backend: str = field(default_factory=lambda: _env("AUTODJ_AI_BACKEND", "auto").lower())
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY"))
    gemini_model: str = field(default_factory=lambda: _env("AUTODJ_GEMINI_MODEL"))
    ollama_url: str = field(default_factory=lambda: _env("AUTODJ_OLLAMA_URL", "http://localhost:11434/v1"))
    ollama_model: str = field(default_factory=lambda: _env("AUTODJ_OLLAMA_MODEL", "gemma3"))
    ai_timeout_s: float = field(default_factory=lambda: float(_env("AUTODJ_AI_TIMEOUT", "25")))
    # --- servidor web ---
    host: str = field(default_factory=lambda: _env("AUTODJ_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("AUTODJ_PORT", "8765")))
    token: str = field(default_factory=lambda: _env("AUTODJ_TOKEN"))
    # --- comportamento do DJ ---
    profiles_path: Path = field(default_factory=lambda: ROOT / "profiles.json")
    max_overlap_s: float = field(default_factory=lambda: float(_env("AUTODJ_MAX_OVERLAP", "20")))
    sim: bool = False
    sim_speed: float = 20.0

    @property
    def is_lan(self) -> bool:
        return self.host not in ("127.0.0.1", "localhost", "::1")

    def ensure_token_for_lan(self) -> None:
        """Expor na rede local sem token seria deixar qualquer um no wifi mexer no som."""
        if self.is_lan and not self.token:
            self.token = secrets.token_urlsafe(6)
