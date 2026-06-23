from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas.agents import AgentDomain

EMERGENCY_TRIGGERS = [
    "chest pain",
    "stroke",
    "suicidal",
    "heavy bleeding",
    "can't breathe",
    "cannot breathe",
    "difficulty breathing",
    "unconscious",
    "seizure",
]


class SymptomTriageAgent(BaseAgent):
    agent_id = "symptom_triage_agent"
    name = "Symptom Triage Agent"
    domain = AgentDomain.TRIAGE
    description = "Analyzes symptoms, scores urgency, and recommends specialists."
    capabilities = ["symptom_analysis", "urgency_scoring", "specialist_recommendation", "emergency_detection"]
    allowed_tools = ["pubmed_mcp"]
    preferred_model_task = "triage"

    async def execute(self, input_data: dict[str, Any], conversation_id: str | None = None) -> dict[str, Any]:
        query = input_data.get("query", "")
        query_lower = query.lower()
        emergency = any(t in query_lower for t in EMERGENCY_TRIGGERS)

        if emergency:
            return {
                "severity_score": 10,
                "urgency_level": "emergency",
                "risk_factors": ["potential_emergency_symptoms"],
                "recommendation": (
                    "Seek immediate emergency medical care. Call emergency services (911) "
                    "or go to the nearest emergency department. Do not delay."
                ),
                "emergency": True,
            }

        system = (
            "You are a medical triage assistant. NEVER provide a final diagnosis. "
            "Assess symptom urgency and recommend appropriate care level. "
            "Respond in JSON with keys: severity_score (1-10), urgency_level "
            "(routine/urgent/emergency), risk_factors (list), recommendation (string)."
        )
        result = self.llm_json(system, f"Patient reports: {query}", conversation_id=conversation_id)
        result.setdefault("emergency", False)
        return result
