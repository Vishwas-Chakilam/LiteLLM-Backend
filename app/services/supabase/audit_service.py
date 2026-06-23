from __future__ import annotations

import logging
from typing import Any

from app.services.supabase.client import get_supabase_factory

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self) -> None:
        self._factory = get_supabase_factory()

    def _client(self):
        if not self._factory.configured:
            return None
        return self._factory.service_client()

    def log_action(
        self,
        user_id: str | None,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "audit action=%s user=%s resource=%s/%s",
            action,
            user_id,
            resource_type,
            resource_id,
        )
        client = self._client()
        if not client:
            return {"action": action, "logged": False}
        row = (
            client.table("audit_logs")
            .insert(
                {
                    "user_id": user_id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "metadata": metadata or {},
                }
            )
            .execute()
        )
        return row.data[0]

    def log_patient_access(self, user_id: str, patient_id: str) -> None:
        self.log_action(
            user_id=user_id,
            action="patient_data_accessed",
            resource_type="patient_profile",
            resource_id=patient_id,
        )

    def log_prior_auth(self, user_id: str, case_id: str, action: str = "prior_auth_submitted") -> None:
        self.log_action(
            user_id=user_id,
            action=action,
            resource_type="prior_authorization",
            resource_id=case_id,
        )

    def log_emergency_escalation(self, user_id: str, conversation_id: str, reason: str) -> None:
        self.log_action(
            user_id=user_id,
            action="emergency_escalation_triggered",
            resource_type="conversation",
            resource_id=conversation_id,
            metadata={"reason": reason},
        )

    def log_tool_invocation(
        self,
        agent_id: str,
        tool_name: str,
        request: dict[str, Any],
        response: dict[str, Any],
        status: str = "success",
    ) -> None:
        client = self._client()
        if not client:
            return
        client.table("tool_logs").insert(
            {
                "agent_id": agent_id,
                "tool_name": tool_name,
                "request": request,
                "response": response,
                "status": status,
            }
        ).execute()

    def log_agent_execution(
        self,
        conversation_id: str | None,
        agent_id: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        execution_time_ms: int,
        status: str = "success",
    ) -> None:
        client = self._client()
        if not client:
            return
        client.table("agent_execution_logs").insert(
            {
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "input": input_data,
                "output": output_data,
                "execution_time_ms": execution_time_ms,
                "status": status,
            }
        ).execute()
