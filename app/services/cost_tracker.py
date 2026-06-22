from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

from app.config import Settings, get_settings


class CostTracker(CustomLogger):
    """LiteLLM callback + persistent daily spend tracking."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._lock = threading.Lock()
        self._daily_spend: float = 0.0
        self._daily_date: date = date.today()
        self._cost_log = self.settings.data_path().parent / "cost_log.jsonl"
        self._cost_log.parent.mkdir(parents=True, exist_ok=True)
        self._load_daily_spend()

    def _load_daily_spend(self) -> None:
        if not self._cost_log.exists():
            return
        today = date.today()
        total = 0.0
        for line in self._cost_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("date") == today.isoformat():
                total += float(entry.get("cost_usd", 0))
        self._daily_spend = total
        self._daily_date = today

    def _roll_date_if_needed(self) -> None:
        today = date.today()
        if today != self._daily_date:
            self._daily_spend = 0.0
            self._daily_date = today

    def log_success_event(self, kwargs, response_obj, start_time, end_time) -> None:
        cost = float(kwargs.get("response_cost") or 0.0)
        metadata = kwargs.get("litellm_params", {}).get("metadata", {}) or {}
        conversation_id = metadata.get("conversation_id")
        model = kwargs.get("model") or "unknown"
        self.record_cost(cost, conversation_id=conversation_id, model=model)

    def record_cost(
        self,
        cost_usd: float,
        *,
        conversation_id: str | None = None,
        model: str | None = None,
    ) -> None:
        with self._lock:
            self._roll_date_if_needed()
            self._daily_spend = round(self._daily_spend + cost_usd, 8)
            entry = {
                "date": date.today().isoformat(),
                "cost_usd": cost_usd,
                "conversation_id": conversation_id,
                "model": model,
            }
            with self._cost_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

    def daily_spend(self) -> float:
        with self._lock:
            self._roll_date_if_needed()
            return self._daily_spend

    def check_daily_budget(self) -> None:
        if self.daily_spend() >= self.settings.daily_budget_usd:
            raise RuntimeError(
                f"Daily budget exceeded (${self.settings.daily_budget_usd:.2f})"
            )

    def check_conversation_budget(self, conversation_cost: float) -> None:
        if conversation_cost >= self.settings.per_conversation_budget_usd:
            raise RuntimeError(
                f"Conversation budget exceeded "
                f"(${self.settings.per_conversation_budget_usd:.2f})"
            )


_cost_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker:
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker
