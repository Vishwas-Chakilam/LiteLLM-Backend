from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage]
    conversation_id: str | None = None
    model: Literal["fast", "capable", "auto"] = "auto"
    max_tokens: int | None = None
    temperature: float | None = None
    stream: bool = False


class ConversationCreateRequest(BaseModel):
    pass
