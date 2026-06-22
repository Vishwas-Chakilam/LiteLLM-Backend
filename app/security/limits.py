from __future__ import annotations

from fastapi import HTTPException

from app.config import Settings, get_settings
from app.models.requests import ChatMessage
from app.services.classifier import estimate_tokens
from app.services.cost_tracker import CostTracker


def enforce_token_limits(
    messages: list[ChatMessage],
    settings: Settings | None = None,
    max_output_tokens: int | None = None,
) -> int:
    settings = settings or get_settings()
    input_tokens = estimate_tokens(messages)
    if input_tokens > settings.max_input_tokens:
        raise HTTPException(
            status_code=400,
            detail=f"Input too large ({input_tokens} tokens, max {settings.max_input_tokens})",
        )

    output_cap = max_output_tokens or settings.max_output_tokens
    if output_cap > settings.max_output_tokens:
        output_cap = settings.max_output_tokens
    return output_cap


def enforce_budgets(
    cost_tracker: CostTracker,
    conversation_cost: float,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    try:
        cost_tracker.check_daily_budget()
        cost_tracker.check_conversation_budget(conversation_cost)
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
