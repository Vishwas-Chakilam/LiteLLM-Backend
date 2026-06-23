from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas.agents import AgentDomain


class LabAnalysisAgent(BaseAgent):
    agent_id = "lab_analysis_agent"
    name = "Lab Analysis Agent"
    domain = AgentDomain.LAB_ANALYSIS
    description = "Interprets lab results and identifies abnormal markers."
    capabilities = ["cbc_analysis", "blood_report", "abnormal_markers", "lab_explanation"]
    allowed_tools = ["hospital_mcp", "lab_reference_mcp"]
    preferred_model_task = "lab_analysis"

    async def execute(self, input_data: dict[str, Any], conversation_id: str | None = None) -> dict[str, Any]:
        query = input_data.get("query", "")
        lab_data = input_data.get("lab_results", {})
        markers = lab_data.get("markers", []) if isinstance(lab_data, dict) else []

        hospital_slug = input_data.get("hospital_slug", "")
        references = {}
        for marker in markers[:10]:
            name = marker if isinstance(marker, str) else marker.get("name", "")
            if name:
                references[name] = await self.call_tool(
                    "hospital_mcp",
                    "get_lab_reference_range",
                    {"marker": name, "hospital_slug": hospital_slug},
                )

        system = (
            "You are a lab result interpretation assistant. Explain values in plain language. "
            "Flag abnormal markers. NEVER diagnose conditions. "
            "JSON keys: summary, abnormal_markers, explanations, follow_up_recommended."
        )
        user = f"Query: {query}\nLab data: {lab_data}\nReference ranges: {references}"
        return self.llm_json(system, user, conversation_id=conversation_id)
