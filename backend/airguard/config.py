"""Runtime configuration, read from the environment and the repo's `.env` / `.env.local` files."""

from __future__ import annotations

import functools
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

    openaq_api_key: str = ""
    firms_map_key: str = ""

    routing_provider: str = "osrm"
    osrm_base_url: str = "https://routing.openstreetmap.de"
    ors_api_key: str = ""
    geocoder_url: str = "https://photon.komoot.io"
    contact_email: str = ""

    model_dir: str = "backend/models"
    model_version: str = ""

    llm_backend: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:1.7b"
    bedrock_model_id: str = "amazon.nova-2-lite-v1:0"
    aws_region: str = "us-east-1"
    agent_rate_limit_per_min: int = 8

    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    demo_snapshot: str = ""

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def model_path(self) -> Path:
        p = Path(self.model_dir)
        return p if p.is_absolute() else REPO_ROOT / p

    @property
    def user_agent(self) -> str:
        contact = f" ({self.contact_email})" if self.contact_email else ""
        return f"AirGuard/0.1 (+https://github.com/airguard){contact}"


@functools.lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
