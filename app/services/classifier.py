from __future__ import annotations

import tiktoken

from app.models.requests import ChatMessage
from app.models.responses import ConversationMeta

COMPLEX_KEYWORDS = (
    "analyze",
    "step by step",
    "explain in detail",
    "comprehensive",
    "architecture",
    "debug",
    "refactor",
    "implement",
    "write code",
    "```",
)


def estimate_tokens(messages: list[ChatMessage], model: str = "gpt-4o-mini") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    total = 0
    for msg in messages:
        total += 4
        total += len(encoding.encode(msg.content))
    total += 2
    return total


def pick_tier(
    messages: list[ChatMessage],
    meta: ConversationMeta | None,
    override: str = "auto",
) -> str:
    if override == "capable":
        return "capable"
    if override == "fast":
        return "fast"

    tokens = estimate_tokens(messages)
    if tokens > 500:
        return "capable"
    if meta and meta.turn_count >= 6:
        return "capable"

    last_user = next((m.content.lower() for m in reversed(messages) if m.role == "user"), "")
    if any(keyword in last_user for keyword in COMPLEX_KEYWORDS):
        return "capable"

    return "fast"
