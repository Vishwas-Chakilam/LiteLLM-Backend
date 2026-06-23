from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache
from typing import Any

import litellm

from app.config import get_settings
from app.services.router_service import get_router_service

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    CHEAP = "cheap"
    REASONING = "reasoning"
    PREMIUM = "premium"


TASK_MODEL_MAP: dict[str, ModelTier] = {
    "classification": ModelTier.CHEAP,
    "extraction": ModelTier.CHEAP,
    "formatting": ModelTier.CHEAP,
    "triage": ModelTier.REASONING,
    "prior_authorization": ModelTier.REASONING,
    "medical_records": ModelTier.REASONING,
    "lab_analysis": ModelTier.REASONING,
    "medication": ModelTier.REASONING,
    "compliance": ModelTier.PREMIUM,
    "safety": ModelTier.PREMIUM,
    "synthesis": ModelTier.PREMIUM,
}


class LLMGateway:
    """LiteLLM wrapper with task-based model routing."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._router = get_router_service()

    def tier_for_task(self, task: str) -> str:
        tier = TASK_MODEL_MAP.get(task, ModelTier.REASONING)
        if tier == ModelTier.CHEAP:
            return self._settings.cheap_model
        if tier == ModelTier.PREMIUM:
            return self._settings.premium_model
        return self._settings.reasoning_model

    def call_model(
        self,
        messages: list[dict[str, str]],
        task: str = "reasoning",
        max_tokens: int | None = None,
        temperature: float = 0.2,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        tier = self.tier_for_task(task)
        max_out = max_tokens or self._settings.max_output_tokens
        try:
            response = self._router.completion(
                tier=tier,
                messages=messages,
                conversation_id=conversation_id or "agent",
                max_tokens=max_out,
                temperature=temperature,
            )
            content = self._router.extract_content(response)
            prompt_tokens, completion_tokens, cost, model_used = self._router.extract_usage(response)
            return {
                "content": content,
                "model": model_used,
                "tier": tier,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cost_usd": cost,
                },
            }
        except Exception as exc:
            logger.error("LLM call failed for task=%s: %s", task, exc)
            raise

    async def acall_model(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.call_model(*args, **kwargs)

    def structured_prompt(self, system: str, user: str, task: str = "reasoning") -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]


@lru_cache
def get_llm_gateway() -> LLMGateway:
    return LLMGateway()
