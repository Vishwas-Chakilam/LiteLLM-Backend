from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas.agents import AgentDomain


class MedicationAgent(BaseAgent):
    agent_id = "medication_agent"
    name = "Medication Agent"
    domain = AgentDomain.MEDICATION
    description = "Provides drug information, interactions, and contraindications. Never prescribes."
    capabilities = ["drug_info", "interactions", "contraindications", "side_effects"]
    allowed_tools = ["drug_database_mcp"]
    preferred_model_task = "medication"

    async def execute(self, input_data: dict[str, Any], conversation_id: str | None = None) -> dict[str, Any]:
        query = input_data.get("query", "")
        drugs = input_data.get("medications", [])

        drug_info = None
        interactions = None
        if drugs:
            interactions = await self.call_tool(
                "drug_database_mcp", "interactions", {"drugs": drugs}
            )
        drug_name = drugs[0] if drugs else query
        drug_info = await self.call_tool("drug_database_mcp", "drug_info", {"drug": drug_name})

        system = (
            "You are a medication information assistant. NEVER prescribe medications. "
            "NEVER override physician decisions. Provide educational information only. "
            "Respond in JSON: drug_info, interactions, contraindications, side_effects, disclaimer."
        )
        user = f"Query: {query}\nKnown drug data: {drug_info}\nInteractions: {interactions}"
        result = self.llm_json(system, user, conversation_id=conversation_id)
        result["disclaimer"] = (
            "This is educational information only. Consult your healthcare provider "
            "before making any medication changes."
        )
        return result
