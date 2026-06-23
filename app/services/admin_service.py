from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.registry.registry import get_agent_registry
from app.services.cost_tracker import get_cost_tracker
from app.services.history_store import HistoryStore
from app.services.supabase.client import get_supabase_factory

logger = logging.getLogger(__name__)


class AdminService:
    """Aggregates platform data for the admin dashboard."""

    def __init__(self) -> None:
        self._factory = get_supabase_factory()

    def _client(self):
        return self._factory.service_client()

    def _table(self, name: str, limit: int = 50, order: str = "created_at", desc: bool = True) -> list[dict[str, Any]]:
        if not self._factory.configured:
            return []
        try:
            q = self._client().table(name).select("*").order(order, desc=desc).limit(limit)
            return q.execute().data or []
        except Exception as exc:
            logger.warning("Admin fetch %s failed: %s", name, exc)
            return []

    def dashboard_stats(self) -> dict[str, Any]:
        settings = get_settings()
        tracker = get_cost_tracker()
        file_conversations = len(HistoryStore().list_conversations())
        registry_agents = len(get_agent_registry().list_agents())

        stats: dict[str, Any] = {
            "supabase_configured": self._factory.configured,
            "daily_spend_usd": round(tracker.daily_spend(), 4),
            "daily_budget_usd": settings.daily_budget_usd,
            "file_conversations": file_conversations,
            "registered_agents": registry_agents,
            "users": 0,
            "conversations": 0,
            "messages": 0,
            "prior_authorizations": 0,
            "workflow_runs": 0,
            "audit_logs": 0,
            "active_agents": 0,
        }

        if not self._factory.configured:
            return stats

        counts = [
            ("users", "users"),
            ("conversations", "conversations"),
            ("messages", "messages"),
            ("prior_authorizations", "prior_authorizations"),
            ("workflow_runs", "workflow_runs"),
            ("audit_logs", "audit_logs"),
        ]
        for key, table in counts:
            try:
                row = self._client().table(table).select("id", count="exact").limit(0).execute()
                stats[key] = row.count or 0
            except Exception:
                pass

        try:
            row = (
                self._client()
                .table("agent_registry")
                .select("id", count="exact")
                .eq("is_active", True)
                .limit(0)
                .execute()
            )
            stats["active_agents"] = row.count or registry_agents
        except Exception:
            stats["active_agents"] = registry_agents

        return stats

    def list_users(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._table("users", limit=limit, order="created_at")

    def update_user_role(self, user_id: str, role: str) -> dict[str, Any]:
        if not self._factory.configured:
            raise RuntimeError("Supabase not configured")
        row = self._client().table("users").update({"role": role}).eq("id", user_id).execute()
        if not row.data:
            raise ValueError("User not found")
        return row.data[0]

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._table("conversations", limit=limit, order="updated_at")

    def list_messages(self, conversation_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if not self._factory.configured:
            return []
        try:
            return (
                self._client()
                .table("messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at")
                .limit(limit)
                .execute()
                .data
                or []
            )
        except Exception as exc:
            logger.warning("Admin messages fetch failed: %s", exc)
            return []

    def list_agents(self) -> list[dict[str, Any]]:
        db_agents = self._table("agent_registry", limit=100, order="priority", desc=True)
        if db_agents:
            return db_agents
        return [a.model_dump() for a in get_agent_registry().list_agents()]

    def list_prior_auth(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._table("prior_authorizations", limit=limit, order="updated_at")

    def list_workflows(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._table("workflow_runs", limit=limit, order="started_at")

    def list_audit_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._table("audit_logs", limit=limit)

    def list_agent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._table("agent_execution_logs", limit=limit)

    def list_tool_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._table("tool_logs", limit=limit)

    def list_assignments(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._table("doctor_patient_assignments", limit=limit, order="assigned_at")

    def create_assignment(self, doctor_id: str, patient_id: str) -> dict[str, Any]:
        if not self._factory.configured:
            raise RuntimeError("Supabase not configured")
        row = (
            self._client()
            .table("doctor_patient_assignments")
            .insert({"doctor_id": doctor_id, "patient_id": patient_id})
            .execute()
        )
        return row.data[0]

    def list_patient_profiles(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._table("patient_profiles", limit=limit)

    def cost_summary(self) -> dict[str, Any]:
        settings = get_settings()
        tracker = get_cost_tracker()
        store = HistoryStore()
        conversations = [
            {
                "conversation_id": m.conversation_id,
                "turn_count": m.turn_count,
                "total_cost_usd": m.total_cost_usd,
                "updated_at": m.updated_at,
            }
            for m in store.list_conversations()
        ]
        return {
            "daily_spend_usd": tracker.daily_spend(),
            "daily_budget_usd": settings.daily_budget_usd,
            "conversation_count": len(conversations),
            "conversations": conversations,
        }
