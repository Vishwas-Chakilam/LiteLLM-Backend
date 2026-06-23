from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas.agents import AgentDomain


class MedicalRecordsAgent(BaseAgent):
    agent_id = "medical_records_agent"
    name = "Medical Records Agent"
    domain = AgentDomain.MEDICAL_RECORDS
    description = "Summarizes EHR data, extracts diagnoses, and builds timelines."
    capabilities = ["ehr_summary", "diagnosis_extraction", "timeline", "missing_data_detection"]
    preferred_model_task = "medical_records"

    async def execute(self, input_data: dict[str, Any], conversation_id: str | None = None) -> dict[str, Any]:
        records = input_data.get("medical_records", input_data.get("records", []))
        patient = input_data.get("patient_profile") or input_data.get("patient_context", {})
        query = input_data.get("query", "")

        system = (
            "You are a medical records analyst. Summarize records, extract key diagnoses, "
            "build a timeline, and identify missing data. Never diagnose. "
            "JSON: summary, diagnoses, timeline, missing_data, key_findings."
        )
        user = f"Query: {query}\nPatient: {patient}\nRecords: {records}"
        return self.llm_json(system, user, conversation_id=conversation_id)
