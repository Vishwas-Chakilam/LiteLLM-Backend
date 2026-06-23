from __future__ import annotations

import re
from typing import Any

from app.agents.base import BaseAgent
from app.schemas.agents import AgentDomain

PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b\d{16}\b"),  # credit card
    re.compile(r"\b[A-Z]{2}\d{6,10}\b"),  # MRN-like
]

UNSAFE_PATTERNS = [
    "definitely have",
    "you have cancer",
    "stop taking all",
    "ignore your doctor",
    "no need to see",
]


class ComplianceSafetyAgent(BaseAgent):
    agent_id = "compliance_safety_agent"
    name = "Compliance & Safety Agent"
    domain = AgentDomain.COMPLIANCE
    description = "HIPAA compliance, safety validation, PII redaction, and escalation."
    capabilities = ["hipaa_check", "safety_validation", "pii_redaction", "escalation"]
    preferred_model_task = "compliance"
    safety_level = "critical"

    async def execute(self, input_data: dict[str, Any], conversation_id: str | None = None) -> dict[str, Any]:
        content = input_data.get("content", input_data.get("query", ""))
        agent_outputs = input_data.get("agent_outputs", [])

        pii_detected = []
        redacted = content
        for pattern in PII_PATTERNS:
            if pattern.search(content):
                pii_detected.append(pattern.pattern)
                redacted = pattern.sub("[REDACTED]", redacted)

        unsafe_flags = [p for p in UNSAFE_PATTERNS if p in content.lower()]
        emergency = input_data.get("emergency", False)

        system = (
            "You are a healthcare compliance and safety reviewer. Check for HIPAA violations, "
            "unsafe medical advice, hallucinations, and emergency situations. "
            "JSON: safe (bool), issues (list), redacted_content, escalate (bool), "
            "compliance_notes, recommendations."
        )
        user = f"Content to review:\n{content}\nAgent outputs: {agent_outputs}\nPII found: {pii_detected}"
        result = self.llm_json(system, user, conversation_id=conversation_id)

        result.setdefault("safe", not unsafe_flags and not pii_detected)
        result.setdefault("issues", unsafe_flags)
        result.setdefault("redacted_content", redacted)
        result.setdefault("escalate", emergency or bool(unsafe_flags))
        result.setdefault("pii_detected", bool(pii_detected))
        return result
