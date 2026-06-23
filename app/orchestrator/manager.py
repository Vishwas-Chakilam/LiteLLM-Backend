from __future__ import annotations

import logging
import uuid
from typing import Any, TypedDict

from app.agents import get_agent_instance
from app.agents.triage import EMERGENCY_TRIGGERS
from app.llm.gateway import get_llm_gateway
from app.memory.redis_store import get_session_store
from app.registry.registry import get_agent_registry
from app.schemas.agents import AgentDomain
from app.services.supabase.audit_service import AuditService
from app.orchestrator.scope import OUT_OF_SCOPE_MESSAGE, detect_query_scope

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict, total=False):
    query: str
    conversation_id: str | None
    session_id: str
    patient_context: dict[str, Any]
    intent: str
    urgency: str
    selected_agents: list[str]
    agent_outputs: dict[str, Any]
    emergency: bool
    final_output: str
    agents_used: list[str]


class ManagerAgent:
    """Orchestrator: intent classification, task decomposition, agent coordination."""

    def __init__(self) -> None:
        self._llm = get_llm_gateway()
        self._registry = get_agent_registry()
        self._audit = AuditService()
        self._memory = get_session_store()

    def classify_intent(self, query: str) -> dict[str, Any]:
        query_lower = query.lower()
        emergency = any(t in query_lower for t in EMERGENCY_TRIGGERS)

        result = self._llm.call_model(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify healthcare query intent. This platform is HEALTHCARE ONLY. "
                        "If the query is not about health, medicine, patients, insurance, or "
                        "clinical workflows, set intent to out_of_scope. "
                        "Return JSON with: "
                        "intent (triage|medication|lab|records|appointment|insurance|"
                        "prior_auth|general|out_of_scope), "
                        "is_healthcare (bool), "
                        "urgency (routine|urgent|emergency), "
                        "tasks (list of subtasks), multi_agent (bool)."
                    ),
                },
                {"role": "user", "content": query},
            ],
            task="classification",
        )
        try:
            import json

            content = result["content"]
            if "```" in content:
                content = content.split("```")[1].replace("json", "", 1)
            parsed = json.loads(content.strip())
        except Exception:
            parsed = {"intent": "general", "urgency": "routine", "tasks": [query], "multi_agent": False}

        if emergency:
            parsed["urgency"] = "emergency"

        # Rule-based scope check overrides LLM misclassification
        if detect_query_scope(query) == "out_of_scope":
            parsed["intent"] = "out_of_scope"
            parsed["is_healthcare"] = False
        elif parsed.get("intent") == "out_of_scope" or parsed.get("is_healthcare") is False:
            parsed["intent"] = "out_of_scope"
        else:
            parsed.setdefault("is_healthcare", True)

        return parsed

    def select_agents(self, query: str, intent_data: dict[str, Any]) -> list[str]:
        if intent_data.get("intent") == "out_of_scope":
            return []

        selected: list[str] = []
        intent = intent_data.get("intent", "general")
        urgency = intent_data.get("urgency", "routine")

        intent_agent_map = {
            "triage": "symptom_triage_agent",
            "medication": "medication_agent",
            "lab": "lab_analysis_agent",
            "records": "medical_records_agent",
            "appointment": "appointment_agent",
            "insurance": "insurance_agent",
            "prior_auth": "prior_authorization_agent",
        }

        if urgency == "emergency":
            selected.append("symptom_triage_agent")

        primary = intent_agent_map.get(intent)
        if primary:
            selected.append(primary)
        else:
            best = self._registry.find_best_agent(query)
            if best:
                selected.append(best.agent_id)

        query_lower = query.lower()
        if any(k in query_lower for k in ["authorization", "prior auth", "mri approval", "cpt", "icd"]):
            if "prior_authorization_agent" not in selected:
                selected.append("prior_authorization_agent")
        if any(k in query_lower for k in ["insurance", "coverage", "in-network", "in network", "valid at", "hospital"]):
            if "insurance_agent" not in selected:
                selected.append("insurance_agent")
        if any(k in query_lower for k in ["chest pain", "symptom", "pain", "fever"]):
            if "symptom_triage_agent" not in selected:
                selected.append("symptom_triage_agent")

        selected.append("compliance_safety_agent")
        return list(dict.fromkeys(selected))

    async def execute_workflow(
        self,
        query: str,
        conversation_id: str | None = None,
        session_id: str | None = None,
        patient_context: dict[str, Any] | None = None,
        force_agents: list[str] | None = None,
    ) -> WorkflowState:
        sid = session_id or str(uuid.uuid4())
        ctx = patient_context or {}

        if not force_agents and detect_query_scope(query) == "out_of_scope":
            state: WorkflowState = {
                "query": query,
                "conversation_id": conversation_id,
                "session_id": sid,
                "patient_context": ctx,
                "intent": "out_of_scope",
                "urgency": "n/a",
                "selected_agents": [],
                "agent_outputs": {},
                "emergency": False,
                "agents_used": [],
                "final_output": OUT_OF_SCOPE_MESSAGE,
                "out_of_scope": True,
            }
            self._memory.set_workflow_state(sid, dict(state))
            return state

        intent_data = self.classify_intent(query)

        if intent_data.get("intent") == "out_of_scope":
            state = {
                "query": query,
                "conversation_id": conversation_id,
                "session_id": sid,
                "patient_context": ctx,
                "intent": "out_of_scope",
                "urgency": "n/a",
                "selected_agents": [],
                "agent_outputs": {},
                "emergency": False,
                "agents_used": [],
                "final_output": OUT_OF_SCOPE_MESSAGE,
                "out_of_scope": True,
            }
            self._memory.set_workflow_state(sid, dict(state))
            return state

        agents = force_agents or self.select_agents(query, intent_data)

        state: WorkflowState = {
            "query": query,
            "conversation_id": conversation_id,
            "session_id": sid,
            "patient_context": ctx,
            "intent": intent_data.get("intent", "general"),
            "urgency": intent_data.get("urgency", "routine"),
            "selected_agents": agents,
            "agent_outputs": {},
            "emergency": intent_data.get("urgency") == "emergency",
            "agents_used": [],
        }

        for agent_id in agents:
            if agent_id == "compliance_safety_agent":
                continue
            instance = get_agent_instance(agent_id)
            if not instance:
                continue
            input_data = {"query": query, "patient_context": ctx, **ctx}
            try:
                output = await instance.run(input_data, conversation_id)
                state["agent_outputs"][agent_id] = output
                state["agents_used"].append(agent_id)
                if output.get("emergency"):
                    state["emergency"] = True
            except Exception as exc:
                logger.error("Agent %s failed: %s", agent_id, exc)
                state["agent_outputs"][agent_id] = {"error": str(exc)}

        safety = get_agent_instance("compliance_safety_agent")
        if safety:
            safety_input = {
                "query": query,
                "content": self._aggregate_outputs(state),
                "agent_outputs": state["agent_outputs"],
                "emergency": state.get("emergency", False),
            }
            safety_result = await safety.run(safety_input, conversation_id)
            state["agent_outputs"]["compliance_safety_agent"] = safety_result
            state["agents_used"].append("compliance_safety_agent")

        state["final_output"] = self._synthesize(state)

        if state.get("emergency") and conversation_id:
            self._audit.log_emergency_escalation(
                user_id=ctx.get("user_id", ""),
                conversation_id=conversation_id,
                reason=query[:200],
            )

        self._memory.set_workflow_state(sid, dict(state))
        return state

    def _aggregate_outputs(self, state: WorkflowState) -> str:
        parts = []
        for agent_id, output in state.get("agent_outputs", {}).items():
            parts.append(f"[{agent_id}]: {output}")
        return "\n".join(parts)

    def _synthesize(self, state: WorkflowState) -> str:
        if state.get("intent") == "out_of_scope" or state.get("out_of_scope"):
            return OUT_OF_SCOPE_MESSAGE

        if state.get("emergency"):
            triage = state.get("agent_outputs", {}).get("symptom_triage_agent", {})
            if triage.get("recommendation"):
                return triage["recommendation"]

        result = self._llm.call_model(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Synthesize healthcare agent outputs into a clear, safe patient-facing response. "
                        "This platform is HEALTHCARE ONLY. If the user query is not health-related, "
                        "do not answer it — say you only handle healthcare topics. "
                        "Never diagnose. Never prescribe. Include disclaimers. Be concise."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Query: {state['query']}\nAgent outputs: {state.get('agent_outputs', {})}",
                },
            ],
            task="synthesis",
            conversation_id=state.get("conversation_id"),
        )
        return result["content"]


_manager: ManagerAgent | None = None


def get_manager() -> ManagerAgent:
    global _manager
    if _manager is None:
        _manager = ManagerAgent()
    return _manager
