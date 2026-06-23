from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.orchestrator.manager import get_manager
from app.schemas.workflow import WorkflowRunResponse, WorkflowStatus
from app.services.supabase.client import get_supabase_factory

logger = logging.getLogger(__name__)


class WorkflowRunner:
    """Executes and persists multi-agent workflows."""

    def __init__(self) -> None:
        self._manager = get_manager()
        self._factory = get_supabase_factory()

    async def run(
        self,
        workflow_name: str,
        query: str,
        conversation_id: str | None = None,
        patient_context: dict[str, Any] | None = None,
        agents: list[str] | None = None,
    ) -> WorkflowRunResponse:
        workflow_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        if self._factory.configured:
            self._factory.service_client().table("workflow_runs").insert(
                {
                    "id": workflow_id,
                    "conversation_id": conversation_id,
                    "workflow_name": workflow_name,
                    "status": WorkflowStatus.RUNNING.value,
                    "state": {"query": query},
                }
            ).execute()

        try:
            state = await self._manager.execute_workflow(
                query=query,
                conversation_id=conversation_id,
                patient_context=patient_context,
                force_agents=agents,
            )
            status = WorkflowStatus.COMPLETED
            completed_at = datetime.now(timezone.utc)

            if self._factory.configured:
                self._factory.service_client().table("workflow_runs").update(
                    {
                        "status": status.value,
                        "state": dict(state),
                        "completed_at": completed_at.isoformat(),
                    }
                ).eq("id", workflow_id).execute()

            return WorkflowRunResponse(
                id=workflow_id,
                conversation_id=conversation_id,
                workflow_name=workflow_name,
                status=status,
                state=dict(state),
                started_at=started_at,
                completed_at=completed_at,
                final_output=state.get("final_output"),
                agents_used=state.get("agents_used", []),
            )
        except Exception as exc:
            logger.error("Workflow failed: %s", exc)
            if self._factory.configured:
                self._factory.service_client().table("workflow_runs").update(
                    {"status": WorkflowStatus.FAILED.value, "state": {"error": str(exc)}}
                ).eq("id", workflow_id).execute()
            raise

    def get_workflow(self, workflow_id: str) -> WorkflowRunResponse | None:
        if not self._factory.configured:
            return None
        row = (
            self._factory.service_client()
            .table("workflow_runs")
            .select("*")
            .eq("id", workflow_id)
            .limit(1)
            .execute()
        )
        if not row.data:
            return None
        data = row.data[0]
        return WorkflowRunResponse(
            id=data["id"],
            conversation_id=data.get("conversation_id"),
            workflow_name=data["workflow_name"],
            status=WorkflowStatus(data["status"]),
            state=data.get("state") or {},
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            final_output=(data.get("state") or {}).get("final_output"),
            agents_used=(data.get("state") or {}).get("agents_used", []),
        )
