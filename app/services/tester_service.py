from __future__ import annotations

import logging
import random
import re
import uuid
from typing import Any

from fastapi import HTTPException

from app.agents import AGENT_MAP
from app.schemas.tester import TesterAgentInfo, TesterPatientProfile
from app.services.agent_test_service import AgentTestService
from app.services.hospital_data_service import get_hospital_service

logger = logging.getLogger(__name__)

CROSS_PATIENT_DENIAL = (
    "Tester sandbox policy: you may only access your own assigned sandbox patient for this "
    "request. Records for Jane Demo, John Demo, or any other patient are not available."
)

# Short URL path -> agent_id
TESTER_AGENT_ENDPOINTS: dict[str, str] = {
    "triage": "symptom_triage_agent",
    "medication": "medication_agent",
    "lab": "lab_analysis_agent",
    "records": "medical_records_agent",
    "appointment": "appointment_agent",
    "insurance": "insurance_agent",
    "prior-auth": "prior_authorization_agent",
    "safety": "compliance_safety_agent",
}

PROTECTED_PATIENT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bjane\s+demo\b",
        r"\bjohn\s+demo\b",
        r"\bjane\b.*\b(record|lab|insurance|profile|patient)\b",
        r"\bjohn\b.*\b(record|lab|insurance|profile|patient)\b",
        r"\bother\s+patient",
        r"\banother\s+patient",
        r"\bpatient\s+id\b",
        r"\bretrieve\b.*\b(patient|record|lab|insurance)\b",
        r"\bshow\b.*\b(jane|john)\b",
        r"\bget\b.*\b(jane|john)\b.*\b(data|record|info)\b",
    ]
]


def _generate_synthetic_patient() -> TesterPatientProfile:
    suffix = uuid.uuid4().hex[:6]
    insurer = random.choice(["aetna", "united", "cigna", "bcbs"])
    return TesterPatientProfile(
        tester_patient_id=f"tester-{suffix}",
        name=f"Sandbox Patient {suffix[:4].upper()}",
        insurance_provider=insurer,
        age=random.randint(28, 72),
        allergies=random.sample(["penicillin", "latex", "sulfa"], k=random.randint(0, 1)),
    )


def is_cross_patient_probe(query: str) -> bool:
    text = query.strip()
    if not text:
        return False
    return any(p.search(text) for p in PROTECTED_PATIENT_PATTERNS)


def build_tester_context(patient: TesterPatientProfile) -> dict[str, Any]:
    hospital_svc = get_hospital_service()
    ctx: dict[str, Any] = hospital_svc.get_context_snapshot()
    ctx["location"] = ctx.get("hospital_name")
    profile = patient.model_dump()
    ctx["patient_profile"] = profile
    ctx["tester_patient"] = profile
    ctx["insurance_provider"] = patient.insurance_provider
    ctx["insurer"] = patient.insurance_provider
    ctx["tester_sandbox"] = True
    ctx["tester_patient_id"] = patient.tester_patient_id
    return ctx


class TesterService:
    """Stateless tester runs — fresh synthetic patient per request, no conversation_id."""

    def __init__(self) -> None:
        self._playground = AgentTestService()

    def list_agents(self) -> list[TesterAgentInfo]:
        agents: list[TesterAgentInfo] = []
        path_by_agent = {v: k for k, v in TESTER_AGENT_ENDPOINTS.items()}
        for agent_id, cls in AGENT_MAP.items():
            instance = cls()
            agents.append(
                TesterAgentInfo(
                    agent_id=agent_id,
                    name=instance.name,
                    endpoint=f"/test/{path_by_agent.get(agent_id, agent_id)}",
                    domain=instance.domain.value,
                    capabilities=list(instance.capabilities),
                )
            )
        return agents

    async def run_workflow(self, query: str) -> dict[str, Any]:
        patient = _generate_synthetic_patient()
        if is_cross_patient_probe(query):
            return _policy_denial_result(query, patient, agent="workflow")

        ctx = build_tester_context(patient)
        result = await self._playground.run_playground(
            query=query,
            mode="workflow",
            patient_context=ctx,
            demo_patient_index=None,
        )
        return _normalize_result(query, patient, "workflow", result)

    async def run_agent(self, endpoint: str, query: str) -> dict[str, Any]:
        agent_id = TESTER_AGENT_ENDPOINTS.get(endpoint)
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Unknown tester endpoint: {endpoint}")

        patient = _generate_synthetic_patient()
        if is_cross_patient_probe(query):
            return _policy_denial_result(query, patient, agent=endpoint)

        ctx = build_tester_context(patient)
        result = await self._playground.run_playground(
            query=query,
            mode="agent",
            agent_id=agent_id,
            patient_context=ctx,
            demo_patient_index=None,
        )
        return _normalize_result(query, patient, endpoint, result)


def _policy_denial_result(
    query: str, patient: TesterPatientProfile, agent: str
) -> dict[str, Any]:
    return {
        "query": query,
        "response": CROSS_PATIENT_DENIAL,
        "agent": agent,
        "agents_used": [],
        "workflow_id": None,
        "emergency": False,
        "policy_denied": True,
        "metadata": {"reason": "cross_patient_access_denied"},
        "patient": patient.model_dump(),
    }


def _normalize_result(
    query: str,
    patient: TesterPatientProfile,
    agent: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    metadata = {
        k: v
        for k, v in result.items()
        if k
        not in {
            "final_output",
            "agents_used",
            "workflow_id",
            "emergency",
            "success",
            "policy_denied",
        }
    }
    if result.get("intent"):
        metadata.setdefault("intent", result["intent"])
    return {
        "query": query,
        "response": result.get("final_output") or "",
        "agent": agent,
        "agents_used": result.get("agents_used", []),
        "workflow_id": result.get("workflow_id"),
        "emergency": result.get("emergency", False),
        "policy_denied": result.get("policy_denied", False),
        "metadata": metadata,
        "patient": patient.model_dump(),
    }
