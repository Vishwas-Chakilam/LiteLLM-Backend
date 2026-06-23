from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowRunRequest(BaseModel):
    workflow_name: str = "healthcare_orchestration"
    query: str
    conversation_id: str | None = None
    patient_context: dict[str, Any] | None = None
    agents: list[str] | None = None


class WorkflowRunResponse(BaseModel):
    id: str
    conversation_id: str | None = None
    workflow_name: str
    status: WorkflowStatus
    state: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    final_output: str | None = None
    agents_used: list[str] = Field(default_factory=list)
