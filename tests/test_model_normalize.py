from __future__ import annotations

from app.services.router_service import (
    is_placeholder_key,
    normalize_model_name,
)


def test_normalize_gemini_prefix():
    assert normalize_model_name("gemini-2.5-flash") == "gemini/gemini-2.5-flash"
    assert normalize_model_name("Gemini-3.1-Flash-Lite") == "gemini/gemini-3.1-flash-lite"


def test_normalize_keeps_existing_prefix():
    assert normalize_model_name("groq/llama-3.1-8b-instant") == "groq/llama-3.1-8b-instant"
    assert normalize_model_name("gemini/gemini-2.5-flash") == "gemini/gemini-2.5-flash"


def test_placeholder_key_detection():
    assert is_placeholder_key("sk-your-openai-key") is True
    assert is_placeholder_key("gsk_realkey123") is False
