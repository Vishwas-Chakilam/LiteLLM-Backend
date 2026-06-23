from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RecordType(str, Enum):
    BLOOD_REPORT = "blood_report"
    XRAY = "xray"
    PRESCRIPTION = "prescription"
    DISCHARGE_SUMMARY = "discharge_summary"


class PatientProfileUpdate(BaseModel):
    age: int | None = None
    gender: str | None = None
    medical_history: list[Any] | None = None
    allergies: list[str] | None = None
    current_medications: list[Any] | None = None
    insurance_provider: str | None = None
    emergency_contact: dict[str, Any] | None = None


class PatientProfileResponse(BaseModel):
    id: str
    user_id: str
    age: int | None = None
    gender: str | None = None
    medical_history: list[Any] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    current_medications: list[Any] = Field(default_factory=list)
    insurance_provider: str | None = None
    emergency_contact: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MedicalRecordResponse(BaseModel):
    id: str
    patient_id: str
    record_type: RecordType
    file_url: str | None = None
    summary: str | None = None
    structured_data: dict[str, Any] = Field(default_factory=dict)
    uploaded_at: datetime | None = None
