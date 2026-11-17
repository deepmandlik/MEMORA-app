from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "memora.db"


def _env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


@dataclass(frozen=True)
class ProviderSettings:
    name: str
    api_key: str | None
    base_url: str | None
    model: str | None
    timeout_seconds: float = 45.0

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    @property
    def endpoint(self) -> str:
        if not self.base_url:
            raise ValueError(f"{self.name} base URL is not configured")
        return f"{self.base_url.rstrip('/')}/chat/completions"


@dataclass(frozen=True)
class Settings:
    db_path: Path
    primary: ProviderSettings
    backup: ProviderSettings

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BACKEND_DIR.parent / ".env")
        load_dotenv(BACKEND_DIR / ".env", override=True)
        timeout = float(os.getenv("AIAND_TIMEOUT_SECONDS", "45"))
        return cls(
            db_path=Path(_env("MEMORA_DB_PATH") or DEFAULT_DB_PATH).expanduser(),
            primary=ProviderSettings(
                name="ai&",
                api_key=_env("AIAND_API_KEY"),
                base_url=_env("AIAND_BASE_URL"),
                model=_env("AIAND_MODEL"),
                timeout_seconds=timeout,
            ),
            backup=ProviderSettings(
                name="backup",
                api_key=_env("BACKUP_API_KEY"),
                base_url=_env("BACKUP_BASE_URL") or _env("BACKUP_URL"),
                model=_env("BACKUP_MODEL"),
                timeout_seconds=timeout,
            ),
        )

