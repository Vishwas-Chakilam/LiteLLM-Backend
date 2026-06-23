from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas.agents import AgentDomain
from app.services.context_builder import resolve_insurer


class InsuranceAgent(BaseAgent):
    agent_id = "insurance_agent"
    name = "Insurance Agent"
    domain = AgentDomain.INSURANCE
    description = "Handles eligibility, benefits verification, and coverage at this hospital."
    capabilities = ["eligibility", "benefits_verification", "coverage_explanation", "in_network_check"]
    allowed_tools = ["hospital_mcp", "payer_rules_mcp"]
    preferred_model_task = "reasoning"

    async def execute(self, input_data: dict[str, Any], conversation_id: str | None = None) -> dict[str, Any]:
        query = input_data.get("query", "")
        insurer = resolve_insurer(input_data)
        hospital_slug = input_data.get("hospital_slug", "")
        hospital_name = input_data.get("hospital_name", "")

        hospital_info = await self.call_tool(
            "hospital_mcp", "get_hospital_info", {"hospital_slug": hospital_slug}
        )
        coverage_check = await self.call_tool(
            "hospital_mcp",
            "check_insurance_accepted",
            {"insurer": insurer, "hospital_slug": hospital_slug},
        )
        accepted = await self.call_tool(
            "hospital_mcp", "get_accepted_insurers", {"hospital_slug": hospital_slug}
        )
        payer_rules = await self.call_tool(
            "payer_rules_mcp",
            "get_payer_rules",
            {"insurer": insurer, "procedure": "general", "hospital_slug": hospital_slug},
        )

        system = (
            "You are an insurance benefits assistant for a single hospital. "
            "Use the hospital insurance acceptance data provided — do not guess. "
            "If insurer is missing, state that clearly and list accepted insurers. "
            "JSON: eligibility_status, insurer, hospital, in_network, benefits_summary, "
            "coverage_details, limitations, next_steps."
        )
        user = (
            f"Query: {query}\n"
            f"Patient insurer: {insurer or 'not specified'}\n"
            f"Hospital: {hospital_name or hospital_info.get('name', '')}\n"
            f"Coverage check: {coverage_check}\n"
            f"Accepted insurers: {accepted}\n"
            f"Payer rules: {payer_rules}"
        )
        result = self.llm_json(system, user, conversation_id=conversation_id)
        result.setdefault("insurer", insurer)
        result.setdefault("hospital", hospital_name or hospital_info.get("name"))
        result.setdefault("in_network", coverage_check.get("in_network", False))
        result.setdefault("coverage_check", coverage_check)
        return result
