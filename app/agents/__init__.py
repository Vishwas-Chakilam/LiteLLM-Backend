from __future__ import annotations

from app.agents.appointment import AppointmentAgent
from app.agents.compliance_safety import ComplianceSafetyAgent
from app.agents.insurance import InsuranceAgent
from app.agents.lab_analysis import LabAnalysisAgent
from app.agents.medical_records import MedicalRecordsAgent
from app.agents.medication import MedicationAgent
from app.agents.prior_authorization import PriorAuthorizationAgent
from app.agents.triage import SymptomTriageAgent
from app.registry.registry import get_agent_registry

AGENT_CLASSES = [
    SymptomTriageAgent,
    MedicationAgent,
    LabAnalysisAgent,
    MedicalRecordsAgent,
    AppointmentAgent,
    InsuranceAgent,
    PriorAuthorizationAgent,
    ComplianceSafetyAgent,
]

AGENT_MAP = {cls.agent_id: cls for cls in AGENT_CLASSES}


def bootstrap_agents() -> None:
    """Register all built-in healthcare agents in the registry."""
    registry = get_agent_registry()
    for cls in AGENT_CLASSES:
        agent = cls()
        registry.register_agent(agent.to_registration())


def get_agent_instance(agent_id: str):
    cls = AGENT_MAP.get(agent_id)
    if not cls:
        return None
    return cls()
