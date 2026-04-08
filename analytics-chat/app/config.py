"""Centralised application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DBConfig:
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "analytics")
    user: str = os.getenv("POSTGRES_USER", "postgres")
    password: str = os.getenv("POSTGRES_PASSWORD", "")

    @property
    def url(self) -> str:
        return (
            f"postgresql+psycopg2://{quote_plus(self.user)}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass(frozen=True)
class LLMConfig:
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("LLM_MODEL", "gpt-4o")
    base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))


@dataclass(frozen=True)
class AppConfig:
    db: DBConfig = field(default_factory=DBConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    query_timeout_seconds: int = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))
    max_result_rows: int = int(os.getenv("MAX_RESULT_ROWS", "10000"))
    display_rows: int = int(os.getenv("DISPLAY_ROWS", "500"))
    sample_rows: int = int(os.getenv("SAMPLE_ROWS", "5"))

    artifacts_dir: Path = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))


def get_config() -> AppConfig:
    """Return a fresh AppConfig (re-reads env on every call)."""
    return AppConfig()
