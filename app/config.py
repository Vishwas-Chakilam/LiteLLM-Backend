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

    def fast_deployments(self) -> list[dict[str, str]]:
        return _scan_model_keys("FAST")

    def capable_deployments(self) -> list[dict[str, str]]:
        return _scan_model_keys("CAPABLE")

    def data_path(self) -> Path:
        return Path(self.data_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
