from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PriorAuthStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    INCOMPLETE = "incomplete"


class PriorAuthCreateRequest(BaseModel):
    patient_id: str
    insurer: str
    diagnosis_codes: list[str] = Field(default_factory=list)
    procedure_codes: list[str] = Field(default_factory=list)
    clinical_notes: str = ""
    patient_data: dict[str, Any] | None = None


class PriorAuthUpdateRequest(BaseModel):
    status: PriorAuthStatus | None = None
    approval_probability: float | None = None
    missing_documents: list[str] | None = None
    denial_risk: str | None = None
    clinical_notes: str | None = None


class PriorAuthResponse(BaseModel):
    id: str
    patient_id: str
    insurer: str
    diagnosis_codes: list[str] = Field(default_factory=list)
    procedure_codes: list[str] = Field(default_factory=list)
    clinical_notes: str | None = None
    approval_probability: float | None = None
    status: PriorAuthStatus
    missing_documents: list[str] = Field(default_factory=list)
    denial_risk: str | None = None
    payer_requirements: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PriorAuthAgentOutput(BaseModel):
    approval_probability: float
    missing_documents: list[str] = Field(default_factory=list)
    payer_requirements: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    denial_risk: str = "medium"
