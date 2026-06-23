from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas.agents import AgentDomain


class AppointmentAgent(BaseAgent):
    agent_id = "appointment_agent"
    name = "Appointment Agent"
    domain = AgentDomain.SCHEDULING
    description = "Recommends specialists and assists with appointment scheduling at this hospital."
    capabilities = ["specialist_recommendation", "hospital_lookup", "scheduling"]
    allowed_tools = ["hospital_mcp"]
    preferred_model_task = "reasoning"

    async def execute(self, input_data: dict[str, Any], conversation_id: str | None = None) -> dict[str, Any]:
        query = input_data.get("query", "")
        hospital_slug = input_data.get("hospital_slug", "")

        hospital_info = await self.call_tool(
            "hospital_mcp", "get_hospital_info", {"hospital_slug": hospital_slug}
        )
        departments = await self.call_tool(
            "hospital_mcp", "list_departments", {"hospital_slug": hospital_slug}
        )
        providers = await self.call_tool(
            "hospital_mcp", "list_providers", {"hospital_slug": hospital_slug}
        )

        system = (
            "You are an appointment scheduling assistant for this hospital only. "
            "Use the real department and provider data provided. "
            "JSON: recommended_specialist, urgency, suggested_facilities, "
            "scheduling_steps, notes, hospital_name."
        )
        user = (
            f"Query: {query}\n"
            f"Hospital: {hospital_info}\n"
            f"Departments: {departments}\n"
            f"Providers: {providers}"
        )
        result = self.llm_json(system, user, conversation_id=conversation_id)
        result.setdefault("hospital_name", hospital_info.get("name"))
        return result
