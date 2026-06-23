from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentDomain(str, Enum):
    TRIAGE = "triage"
    MEDICATION = "medication"
    PRIOR_AUTHORIZATION = "prior_authorization"
    LAB_ANALYSIS = "lab_analysis"
    MEDICAL_RECORDS = "medical_records"
    INSURANCE = "insurance"
    SCHEDULING = "scheduling"
    COMPLIANCE = "compliance"
    EMERGENCY = "emergency"
    BILLING = "billing"


class SafetyLevel(str, Enum):
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"
    CRITICAL = "critical"


class AgentRegistration(BaseModel):
    agent_id: str
    name: str
    display_name: str | None = None
    domain: AgentDomain
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)
    preferred_model: str = "reasoning"
    safety_level: SafetyLevel = SafetyLevel.STANDARD
    priority: int = 0
    version: str = "1.0.0"


class AgentRecord(AgentRegistration):
    id: str | None = None
    is_active: bool = True
    created_at: datetime | None = None


class AgentExecutionRequest(BaseModel):
    agent_id: str
    input: dict[str, Any]
    conversation_id: str | None = None


class AgentExecutionResult(BaseModel):
    agent_id: str
    output: dict[str, Any]
    execution_time_ms: int
    status: str = "success"


class AgentListResponse(BaseModel):
    agents: list[AgentRecord]
    total: int
