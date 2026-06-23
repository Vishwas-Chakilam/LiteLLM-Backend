from __future__ import annotations

import logging
from typing import Any

from app.schemas.prior_auth import (
    PriorAuthCreateRequest,
    PriorAuthResponse,
    PriorAuthStatus,
    PriorAuthUpdateRequest,
)
from app.services.supabase.client import get_supabase_factory

logger = logging.getLogger(__name__)

# Simplified payer rules — production would use MCP payer_rules_mcp
PAYER_RULES: dict[str, dict[str, Any]] = {
    "aetna": {
        "mri": {"requires_clinical_notes": True, "requires_prior_treatment": True},
        "surgery": {"requires_second_opinion": False},
    },
    "united": {
        "mri": {"requires_clinical_notes": True, "requires_imaging_history": True},
        "specialty_drug": {"requires_step_therapy": True},
    },
    "cigna": {
        "inpatient": {"requires_utilization_review": True},
    },
}


class PriorAuthService:
    def __init__(self) -> None:
        self._factory = get_supabase_factory()

    def _client(self):
        return self._factory.service_client()

    def create_case(self, request: PriorAuthCreateRequest) -> PriorAuthResponse:
        row = (
            self._client().table("prior_authorizations")
            .insert(
                {
                    "patient_id": request.patient_id,
                    "insurer": request.insurer.lower(),
                    "diagnosis_codes": request.diagnosis_codes,
                    "procedure_codes": request.procedure_codes,
                    "clinical_notes": request.clinical_notes,
                    "status": PriorAuthStatus.PENDING.value,
                }
            )
            .execute()
        )
        return self._to_response(row.data[0])

    def update_status(self, case_id: str, update: PriorAuthUpdateRequest) -> PriorAuthResponse:
        payload = update.model_dump(exclude_none=True)
        if "status" in payload:
            payload["status"] = payload["status"].value if hasattr(payload["status"], "value") else payload["status"]
        row = (
            self._client().table("prior_authorizations")
            .update(payload)
            .eq("id", case_id)
            .execute()
        )
        return self._to_response(row.data[0])

    def get_case(self, case_id: str) -> PriorAuthResponse:
        row = (
            self._client().table("prior_authorizations")
            .select("*")
            .eq("id", case_id)
            .single()
            .execute()
        )
        return self._to_response(row.data)

    def list_by_patient(self, patient_id: str) -> list[PriorAuthResponse]:
        rows = (
            self._client().table("prior_authorizations")
            .select("*")
            .eq("patient_id", patient_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [self._to_response(r) for r in rows.data]

    def fetch_payer_rules(self, insurer: str, procedure_type: str = "mri") -> dict[str, Any]:
        insurer_rules = PAYER_RULES.get(insurer.lower(), {})
        return insurer_rules.get(procedure_type, {"requires_clinical_notes": True})

    def store_document(self, user_id: str, case_id: str, filename: str, content: bytes) -> str:
        path = f"{user_id}/prior-auth/{case_id}/{filename}"
        self._client().storage.from_("prior-auth-documents").upload(path, content)
        return path

    def _to_response(self, data: dict[str, Any]) -> PriorAuthResponse:
        return PriorAuthResponse(
            id=data["id"],
            patient_id=data["patient_id"],
            insurer=data["insurer"],
            diagnosis_codes=data.get("diagnosis_codes") or [],
            procedure_codes=data.get("procedure_codes") or [],
            clinical_notes=data.get("clinical_notes"),
            approval_probability=data.get("approval_probability"),
            status=PriorAuthStatus(data["status"]),
            missing_documents=data.get("missing_documents") or [],
            denial_risk=data.get("denial_risk"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
