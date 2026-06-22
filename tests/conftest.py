from __future__ import annotations

import os
from pathlib import Path

import pytest

# Set test env before app imports
os.environ.setdefault("FAST_MODEL_1", "gpt-4o-mini")
os.environ.setdefault("FAST_API_KEY_1", "sk-test-fast")
os.environ.setdefault("CAPABLE_MODEL_1", "gpt-4o")
os.environ.setdefault("CAPABLE_API_KEY_1", "sk-test-capable")
os.environ.setdefault("DAILY_BUDGET_USD", "100")
os.environ.setdefault("PER_CONVERSATION_BUDGET_USD", "10")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")


@pytest.fixture
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "conversations"
    data_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    from app.config import get_settings

    get_settings.cache_clear()
    return data_dir


@pytest.fixture
def client(tmp_data_dir: Path, monkeypatch: pytest.MonkeyPatch):
    from app.config import get_settings
    from app.services.cost_tracker import _cost_tracker
    from app.services.router_service import reset_router_service

    get_settings.cache_clear()
    reset_router_service()
    import app.services.cost_tracker as ct

    ct._cost_tracker = None

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
    reset_router_service()
    ct._cost_tracker = None
