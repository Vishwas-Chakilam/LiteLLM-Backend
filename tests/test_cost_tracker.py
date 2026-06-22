from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.services.cost_tracker import CostTracker


def test_cost_tracker_daily_spend(tmp_data_dir, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATA_DIR", str(tmp_data_dir))
    tracker = CostTracker()
    tracker.record_cost(0.05, conversation_id="abc", model="gpt-4o-mini")
    tracker.record_cost(0.03, conversation_id="abc", model="gpt-4o-mini")
    assert tracker.daily_spend() == pytest.approx(0.08)


def test_cost_tracker_daily_budget_exceeded(tmp_data_dir, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("DAILY_BUDGET_USD", "0.10")
    get_settings.cache_clear()
    tracker = CostTracker()
    tracker.record_cost(0.11)
    with pytest.raises(RuntimeError, match="Daily budget"):
        tracker.check_daily_budget()


def test_cost_tracker_conversation_budget(tmp_data_dir, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("PER_CONVERSATION_BUDGET_USD", "0.25")
    get_settings.cache_clear()
    tracker = CostTracker()
    with pytest.raises(RuntimeError, match="Conversation budget"):
        tracker.check_conversation_budget(0.30)
