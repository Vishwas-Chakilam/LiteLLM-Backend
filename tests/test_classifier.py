from __future__ import annotations

import pytest

from app.config import get_settings
from app.models.requests import ChatMessage
from app.services.classifier import estimate_tokens, pick_tier
from app.services.history_store import HistoryStore


def test_estimate_tokens():
    messages = [ChatMessage(role="user", content="Hello world")]
    tokens = estimate_tokens(messages)
    assert tokens > 0


def test_pick_tier_fast_by_default():
    messages = [ChatMessage(role="user", content="Hi")]
    assert pick_tier(messages, None, override="auto") == "fast"


def test_pick_tier_capable_on_override():
    messages = [ChatMessage(role="user", content="Hi")]
    assert pick_tier(messages, None, override="capable") == "capable"


def test_pick_tier_capable_on_long_input():
    long_text = "word " * 600
    messages = [ChatMessage(role="user", content=long_text)]
    assert pick_tier(messages, None, override="auto") == "capable"


def test_pick_tier_capable_on_keywords():
    messages = [ChatMessage(role="user", content="Please analyze this step by step")]
    assert pick_tier(messages, None, override="auto") == "capable"


def test_history_create_and_append(tmp_data_dir):
    get_settings.cache_clear()
    store = HistoryStore()
    conv_id, meta = store.create_conversation()
    assert meta.turn_count == 0

    store.append_turn(
        conv_id,
        user_content="Hello",
        assistant_content="Hi there",
        tier="fast",
        model="gpt-4o-mini",
        cost_usd=0.001,
        prompt_tokens=5,
        completion_tokens=3,
    )
    meta = store.get_meta(conv_id)
    assert meta.turn_count == 1
    assert meta.total_cost_usd == 0.001

    messages = store.parse_messages(store.read_transcript(conv_id))
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"


def test_history_invalid_id(tmp_data_dir):
    get_settings.cache_clear()
    store = HistoryStore()
    with pytest.raises(ValueError):
        store.get_meta("not-a-uuid")
