from __future__ import annotations

import logging
from typing import Any

from litellm import Router

from app.config import Settings, get_settings
from app.services.cost_tracker import get_cost_tracker

logger = logging.getLogger(__name__)

# Friendly names from .env -> LiteLLM provider/model strings
GEMINI_ALIASES: dict[str, str] = {
    "gemini-3.5-flash": "gemini/gemini-2.5-flash",
    "gemini-3.1-flash-lite": "gemini/gemini-3.1-flash-lite",
}

PLACEHOLDER_KEY_PATTERNS = (
    "your-openai-key",
    "sk-your-",
    "gsk_...",
    "sk-ant-...",
    "change-me",
)


def normalize_model_name(model: str) -> str:
    model = model.strip()
    if "/" in model:
        return model

    lowered = model.lower()
    if lowered in GEMINI_ALIASES:
        return GEMINI_ALIASES[lowered]
    if lowered.startswith("gemini-"):
        return f"gemini/{lowered}"
    return model


def is_placeholder_key(api_key: str) -> bool:
    key = api_key.strip().lower()
    return any(pattern in key for pattern in PLACEHOLDER_KEY_PATTERNS)


def _deployment_is_valid(model: str, api_key: str) -> bool:
    if is_placeholder_key(api_key):
        logger.warning("Skipping deployment with placeholder API key for model=%s", model)
        return False
    try:
        import litellm

        litellm.get_llm_provider(model=model, api_key=api_key)
        return True
    except Exception as exc:
        logger.warning("Skipping invalid deployment model=%s: %s", model, exc)
        return False


def _build_model_list(settings: Settings) -> list[dict[str, Any]]:
    model_list: list[dict[str, Any]] = []

    for dep in settings.fast_deployments():
        model = normalize_model_name(dep["model"])
        api_key = dep["api_key"]
        if not _deployment_is_valid(model, api_key):
            continue
        model_list.append(
            {
                "model_name": "fast",
                "litellm_params": {
                    "model": model,
                    "api_key": api_key,
                },
            }
        )

    for dep in settings.capable_deployments():
        model = normalize_model_name(dep["model"])
        api_key = dep["api_key"]
        if not _deployment_is_valid(model, api_key):
            continue
        model_list.append(
            {
                "model_name": "capable",
                "litellm_params": {
                    "model": model,
                    "api_key": api_key,
                },
            }
        )

    if not model_list:
        raise RuntimeError(
            "No valid model deployments configured. Check FAST_MODEL_N/FAST_API_KEY_N "
            "and CAPABLE_MODEL_N/CAPABLE_API_KEY_N in .env (use gemini/ prefix for Gemini)."
        )

    return model_list

class RouterService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.cost_tracker = get_cost_tracker()
        model_list = _build_model_list(self.settings)

        fallbacks: list[dict[str, list[str]]] = []
        has_fast = any(m["model_name"] == "fast" for m in model_list)
        has_capable = any(m["model_name"] == "capable" for m in model_list)
        if has_fast and has_capable:
            fallbacks.append({"fast": ["capable"]})

        self.router = Router(
            model_list=model_list,
            routing_strategy=self.settings.routing_strategy,
            num_retries=self.settings.num_retries,
            allowed_fails=self.settings.allowed_fails,
            cooldown_time=self.settings.cooldown_time,
            fallbacks=fallbacks,
            context_window_fallbacks=fallbacks if fallbacks else None,
            set_verbose=False,
        )

    def completion(
        self,
        *,
        tier: str,
        messages: list[dict[str, str]],
        conversation_id: str,
        max_tokens: int,
        temperature: float | None = None,
    ) -> Any:
        params: dict[str, Any] = {
            "model": tier,
            "messages": messages,
            "max_tokens": max_tokens,
            "metadata": {"conversation_id": conversation_id},
        }
        if temperature is not None:
            params["temperature"] = temperature

        return self.router.completion(**params)

    def extract_usage(self, response: Any) -> tuple[int, int, float, str]:
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        model_used = getattr(response, "model", tier_default(response))
        try:
            from litellm import completion_cost

            cost = float(completion_cost(completion_response=response) or 0.0)
        except Exception:
            cost = 0.0
        return prompt_tokens, completion_tokens, cost, model_used

    def extract_content(self, response: Any) -> str:
        choice = response.choices[0]
        message = choice.message
        content = getattr(message, "content", None)
        return content or ""


def tier_default(response: Any) -> str:
    return getattr(response, "model", "unknown")


_router_service: RouterService | None = None


def get_router_service() -> RouterService:
    global _router_service
    if _router_service is None:
        _router_service = RouterService()
    return _router_service


def reset_router_service() -> None:
    """Test helper to rebuild router after env changes."""
    global _router_service
    _router_service = None
