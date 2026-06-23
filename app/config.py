from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


def _scan_model_keys(prefix: str) -> list[dict[str, str]]:
    """Load numbered MODEL_N / API_KEY_N pairs from environment."""
    deployments: list[dict[str, str]] = []
    index = 1
    while True:
        model = os.getenv(f"{prefix}_MODEL_{index}")
        api_key = os.getenv(f"{prefix}_API_KEY_{index}")
        if not model and not api_key:
            break
        if model and api_key:
            deployments.append({"model": model, "api_key": api_key})
        index += 1
    return deployments


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LiteLLM router
    routing_strategy: str = "simple-shuffle"
    num_retries: int = 2
    allowed_fails: int = 3
    cooldown_time: float = 60.0
    daily_budget_usd: float = 10.0
    per_conversation_budget_usd: float = 0.50
    max_input_tokens: int = 8000
    max_output_tokens: int = 2000
    rate_limit_per_minute: int = 30
    data_dir: str = "data/conversations"
    system_prompt_enabled: bool = True
    system_prompt: str | None = None

    # Healthcare platform models
    cheap_model: str = "fast"
    reasoning_model: str = "capable"
    premium_model: str = "capable"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_session_ttl_seconds: int = 86400

    # Vector DB (Chroma)
    chroma_persist_dir: str = "data/chroma"
    medical_rag_enabled: bool = True

    # Auth
    auth_required: bool = True
    jwt_algorithm: str = "HS256"

    # MCP
    mcp_servers_config: str = "config/mcp_servers.json"

    # Single-hospital deployment
    hospital_slug: str = "city_general"
    hospital_data_file: str = "config/hospital/city_general.json"

    # Tester sandbox API (no auth, synthetic patients only)
    tester_api_enabled: bool = True

    def fast_deployments(self) -> list[dict[str, str]]:
        return _scan_model_keys("FAST")

    def capable_deployments(self) -> list[dict[str, str]]:
        return _scan_model_keys("CAPABLE")

    def data_path(self) -> Path:
        return Path(self.data_dir)

    def chroma_path(self) -> Path:
        return Path(self.chroma_persist_dir)

    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
