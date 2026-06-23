from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas.agents import AgentDomain
from app.services.context_builder import resolve_insurer


class PriorAuthorizationAgent(BaseAgent):
    agent_id = "prior_authorization_agent"
    name = "Prior Authorization Agent"
    domain = AgentDomain.PRIOR_AUTHORIZATION
    description = "Manages prior authorization workflows including payer rules and documentation."
    capabilities = [
        "icd_validation",
        "cpt_matching",
        "payer_rule_engine",
        "document_completeness",
        "approval_probability",
    ]
    allowed_tools = ["hospital_mcp", "payer_rules_mcp", "icd_lookup_mcp", "cpt_lookup_mcp"]
    preferred_model_task = "prior_authorization"
    safety_level = "high"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        from app.services.supabase.prior_auth_service import PriorAuthService

        self._prior_auth = PriorAuthService()

    async def execute(self, input_data: dict[str, Any], conversation_id: str | None = None) -> dict[str, Any]:
        patient_data = input_data.get("patient_profile") or input_data.get("patient_data", {})
        if not isinstance(patient_data, dict):
            patient_data = {}
        diagnosis_codes = input_data.get("diagnosis_codes", [])
        procedure_codes = input_data.get("procedure_codes", [])
        insurer = resolve_insurer(input_data) or patient_data.get("insurance_provider", "")
        hospital_slug = input_data.get("hospital_slug", "")
        clinical_notes = input_data.get("clinical_notes", input_data.get("query", ""))
        procedure_type = input_data.get("procedure_type", "mri")

        validated_icd = []
        for code in diagnosis_codes:
            result = await self.call_tool("icd_lookup_mcp", "lookup_icd", {"code": code})
            validated_icd.append(result)

        validated_cpt = []
        for code in procedure_codes:
            result = await self.call_tool("cpt_lookup_mcp", "lookup_cpt", {"code": code})
            validated_cpt.append(result)

        payer_rules = await self.call_tool(
            "hospital_mcp",
            "get_hospital_payer_rules",
            {"insurer": insurer, "procedure_type": procedure_type, "hospital_slug": hospital_slug},
        )
        generic_rules = await self.call_tool(
            "payer_rules_mcp",
            "get_payer_rules",
            {"insurer": insurer, "procedure": procedure_type, "hospital_slug": hospital_slug},
        )
        db_rules = self._prior_auth.fetch_payer_rules(insurer, procedure_type)

        missing_documents = []
        if (payer_rules.get("requires_clinical_notes") or generic_rules.get("requires_clinical_notes")) and not clinical_notes:
            missing_documents.append("clinical_notes")
        if payer_rules.get("requires_prior_treatment"):
            missing_documents.append("prior_treatment_documentation")
        if payer_rules.get("requires_imaging_history"):
            missing_documents.append("imaging_history")
        if payer_rules.get("requires_step_therapy"):
            missing_documents.append("step_therapy_documentation")

        system = (
            "You are a prior authorization specialist. Assess approval likelihood based on "
            "clinical data, codes, and payer rules. NEVER guarantee approval. "
            "JSON: approval_probability (0-1), missing_documents, payer_requirements, "
            "next_steps, denial_risk (low/medium/high), clinical_rationale."
        )
        user = (
            f"Insurer: {insurer}\nProcedure: {procedure_type}\n"
            f"ICD codes: {validated_icd}\nCPT codes: {validated_cpt}\n"
            f"Payer rules: {payer_rules}\nDB rules: {db_rules}\n"
            f"Clinical notes: {clinical_notes}\nPatient: {patient_data}\n"
            f"Already missing: {missing_documents}"
        )
        result = self.llm_json(system, user, conversation_id=conversation_id)

        result.setdefault("missing_documents", missing_documents)
        result.setdefault("payer_requirements", list(db_rules.keys()) if db_rules else [])
        result.setdefault("approval_probability", 0.5 if not missing_documents else 0.3)
        result.setdefault("denial_risk", "high" if missing_documents else "medium")
        result.setdefault("next_steps", ["Submit complete documentation to payer"])
        return result
