from __future__ import annotations

import logging
from typing import Any

from app.schemas.patient import MedicalRecordResponse, PatientProfileResponse, PatientProfileUpdate, RecordType
from app.services.supabase.client import get_supabase_factory

logger = logging.getLogger(__name__)


class PatientService:
    def __init__(self) -> None:
        self._factory = get_supabase_factory()

    def _client(self):
        return self._factory.service_client()

    def get_profile_by_user(self, user_id: str) -> PatientProfileResponse | None:
        row = (
            self._client().table("patient_profiles")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not row.data:
            return None
        return self._to_profile(row.data[0])

    def get_profile(self, profile_id: str) -> PatientProfileResponse:
        row = (
            self._client().table("patient_profiles")
            .select("*")
            .eq("id", profile_id)
            .single()
            .execute()
        )
        return self._to_profile(row.data)

    def get_or_create_profile(self, user_id: str) -> PatientProfileResponse:
        existing = self.get_profile_by_user(user_id)
        if existing:
            return existing
        row = (
            self._client().table("patient_profiles")
            .insert({"user_id": user_id})
            .execute()
        )
        return self._to_profile(row.data[0])

    def update_profile(self, user_id: str, update: PatientProfileUpdate) -> PatientProfileResponse:
        profile = self.get_or_create_profile(user_id)
        payload = update.model_dump(exclude_none=True)
        if not payload:
            return profile
        row = (
            self._client().table("patient_profiles")
            .update(payload)
            .eq("user_id", user_id)
            .execute()
        )
        return self._to_profile(row.data[0])

    def get_records(self, patient_id: str) -> list[MedicalRecordResponse]:
        rows = (
            self._client().table("medical_records")
            .select("*")
            .eq("patient_id", patient_id)
            .order("uploaded_at", desc=True)
            .execute()
        )
        return [self._to_record(r) for r in rows.data]

    def add_record(
        self,
        patient_id: str,
        record_type: RecordType,
        file_url: str | None = None,
        summary: str | None = None,
        structured_data: dict[str, Any] | None = None,
    ) -> MedicalRecordResponse:
        row = (
            self._client().table("medical_records")
            .insert(
                {
                    "patient_id": patient_id,
                    "record_type": record_type.value,
                    "file_url": file_url,
                    "summary": summary,
                    "structured_data": structured_data or {},
                }
            )
            .execute()
        )
        return self._to_record(row.data[0])

    def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        result = self._client().storage.from_(bucket).create_signed_url(path, expires_in)
        return result.get("signedURL") or result.get("signedUrl", "")

    def _to_profile(self, data: dict[str, Any]) -> PatientProfileResponse:
        return PatientProfileResponse(
            id=data["id"],
            user_id=data["user_id"],
            age=data.get("age"),
            gender=data.get("gender"),
            medical_history=data.get("medical_history") or [],
            allergies=data.get("allergies") or [],
            current_medications=data.get("current_medications") or [],
            insurance_provider=data.get("insurance_provider"),
            emergency_contact=data.get("emergency_contact") or {},
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def _to_record(self, data: dict[str, Any]) -> MedicalRecordResponse:
        return MedicalRecordResponse(
            id=data["id"],
            patient_id=data["patient_id"],
            record_type=RecordType(data["record_type"]),
            file_url=data.get("file_url"),
            summary=data.get("summary"),
            structured_data=data.get("structured_data") or {},
            uploaded_at=data.get("uploaded_at"),
        )
