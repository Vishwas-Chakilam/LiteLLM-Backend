from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TesterHealthResponse(BaseModel):
    status: str = "ok"
    mode: str = "tester"


class TesterPatientProfile(BaseModel):
    tester_patient_id: str
    name: str
    insurance_provider: str
    age: int
    allergies: list[str] = Field(default_factory=list)
    is_tester_sandbox: bool = True


class TesterAgentInfo(BaseModel):
    agent_id: str
    name: str
    endpoint: str
    domain: str
    capabilities: list[str] = Field(default_factory=list)


class TesterAgentsResponse(BaseModel):
    agents: list[TesterAgentInfo]
    total: int


class TesterQueryRequest(BaseModel):
    """Tester sends only a query — no conversation_id, no auth."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)


class TesterQueryResponse(BaseModel):
    query: str
    response: str
    agent: str
    agents_used: list[str] = Field(default_factory=list)
    patient: TesterPatientProfile
    workflow_id: str | None = None
    escalated: bool = False
    policy_denied: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
