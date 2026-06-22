from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.services.router_service import RouterService, _build_model_list, reset_router_service


def test_build_model_list(tmp_data_dir, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("FAST_MODEL_1", "gpt-4o-mini")
    monkeypatch.setenv("FAST_API_KEY_1", "sk-a")
    monkeypatch.setenv("FAST_MODEL_2", "groq/llama")
    monkeypatch.setenv("FAST_API_KEY_2", "gsk-b")
    get_settings.cache_clear()
    settings = get_settings()
    models = _build_model_list(settings)
    assert len(models) >= 3
    fast_names = [m["model_name"] for m in models if m["model_name"] == "fast"]
    assert len(fast_names) == 2


def test_router_service_completion_mock(tmp_data_dir, monkeypatch):
    get_settings.cache_clear()
    reset_router_service()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Mocked reply"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_response.model = "gpt-4o-mini"

    with patch("app.services.router_service.Router") as MockRouter:
        instance = MockRouter.return_value
        instance.completion.return_value = mock_response
        service = RouterService()
        result = service.completion(
            tier="fast",
            messages=[{"role": "user", "content": "Hi"}],
            conversation_id="00000000-0000-0000-0000-000000000001",
            max_tokens=100,
        )
        assert result.choices[0].message.content == "Mocked reply"
        instance.completion.assert_called_once()
