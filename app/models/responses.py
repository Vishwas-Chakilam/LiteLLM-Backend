from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatChoiceMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: UsageInfo
    conversation_id: str
    tier: str
    model_used: str
    estimated_cost_usd: float = 0.0


class ConversationCreateResponse(BaseModel):
    conversation_id: str
    created_at: str


class TurnRecord(BaseModel):
    turn: int
    timestamp: str
    tier: str
    model: str
    role: str
    content: str
    cost_usd: float = 0.0


class ConversationMeta(BaseModel):
    conversation_id: str
    created_at: str
    updated_at: str
    turn_count: int = 0
    total_cost_usd: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    last_tier: str | None = None
    last_model: str | None = None


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    meta: ConversationMeta
    transcript: str
    messages: list[dict[str, str]]


class CostSummaryResponse(BaseModel):
    daily_spend_usd: float
    daily_budget_usd: float
    conversation_count: int
    conversations: list[dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
