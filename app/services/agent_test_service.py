from __future__ import annotations

import logging
import time
from typing import Any, Literal

from app.agents import AGENT_MAP, get_agent_instance
from app.orchestrator.manager import get_manager
from app.registry.registry import get_agent_registry
from app.workflows.runner import WorkflowRunner

logger = logging.getLogger(__name__)

SAMPLE_PROMPTS: list[dict[str, str]] = [
    {
        "id": "triage_routine",
        "label": "Routine triage",
        "query": "I have had a mild headache for 2 days, no fever.",
        "suggested_mode": "workflow",
    },
    {
        "id": "triage_emergency",
        "label": "Emergency (chest pain)",
        "query": "I have severe chest pain radiating to my left arm and shortness of breath.",
        "suggested_mode": "workflow",
    },
    {
        "id": "medication",
        "label": "Drug interactions",
        "query": "Can I take ibuprofen with metformin and lisinopril?",
        "suggested_mode": "agent",
        "suggested_agent": "medication_agent",
    },
    {
        "id": "prior_auth",
        "label": "MRI prior auth",
        "query": "Patient needs lumbar MRI authorization. Insurer Aetna. ICD M54.5, CPT 70553. Conservative treatment failed 6 weeks.",
        "suggested_mode": "agent",
        "suggested_agent": "prior_authorization_agent",
    },
    {
        "id": "multi_agent",
        "label": "Multi-agent workflow",
        "query": "Patient needs MRI authorization and is reporting chest pain.",
        "suggested_mode": "workflow",
    },
    {
        "id": "lab",
        "label": "Lab analysis",
        "query": "My CBC shows hemoglobin 9.2 g/dL and WBC 14,000. What does this mean?",
        "suggested_mode": "agent",
        "suggested_agent": "lab_analysis_agent",
    },
    {
        "id": "insurance",
        "label": "Insurance coverage",
        "query": "Does my United Healthcare plan cover specialist visits without referral?",
        "suggested_mode": "agent",
        "suggested_agent": "insurance_agent",
    },
]


class AgentTestService:
    """Run agent health checks and playground tests from the admin console."""

    def list_samples(self) -> list[dict[str, str]]:
        return SAMPLE_PROMPTS

    def health_check(self) -> dict[str, Any]:
        registry = get_agent_registry()
        registered = {a.agent_id for a in registry.list_agents()}
        agents: list[dict[str, Any]] = []
        all_ok = True

        for agent_id, cls in AGENT_MAP.items():
            entry: dict[str, Any] = {
                "agent_id": agent_id,
                "name": cls.name,
                "domain": cls.domain.value,
                "registered": agent_id in registered,
                "instantiable": False,
                "status": "unknown",
            }
            try:
                instance = cls()
                entry["instantiable"] = True
                entry["capabilities"] = instance.capabilities
                entry["tools"] = instance.allowed_tools
                if agent_id in registered:
                    entry["status"] = "ready"
                else:
                    entry["status"] = "not_registered"
                    all_ok = False
            except Exception as exc:
                entry["status"] = "error"
                entry["error"] = str(exc)
                all_ok = False
            agents.append(entry)

        return {
            "healthy": all_ok,
            "agent_count": len(agents),
            "ready_count": sum(1 for a in agents if a["status"] == "ready"),
            "agents": agents,
        }

    async def run_playground(
        self,
        query: str,
        mode: Literal["workflow", "agent", "health"] = "workflow",
        agent_id: str | None = None,
        patient_context: dict[str, Any] | None = None,
        demo_patient_index: int | None = None,
    ) -> dict[str, Any]:
        if mode == "health":
            result = self.health_check()
            result["mode"] = "health"
            return result

        start = time.perf_counter()
        from app.services.context_builder import build_agent_context

        effective_demo = demo_patient_index
        if effective_demo is None and not patient_context:
            effective_demo = 0
        ctx = build_agent_context(
            user=None,
            extra=patient_context,
            demo_patient_index=effective_demo,
        )

        if mode == "agent":
            if not agent_id:
                raise ValueError("agent_id is required for single-agent mode")
            return await self._run_single_agent(query, agent_id, ctx, start)

        return await self._run_workflow(query, ctx, start, agent_id)

    async def _run_single_agent(
        self,
        query: str,
        agent_id: str,
        ctx: dict[str, Any],
        start: float,
    ) -> dict[str, Any]:
        instance = get_agent_instance(agent_id)
        if not instance:
            raise ValueError(f"Unknown agent: {agent_id}")

        input_data = {"query": query, "patient_context": ctx, **ctx}
        agent_start = time.perf_counter()
        try:
            output = await instance.run(input_data)
            status = "success"
            error = None
        except Exception as exc:
            output = {}
            status = "failed"
            error = str(exc)
            logger.error("Playground agent %s failed: %s", agent_id, exc)

        agent_ms = int((time.perf_counter() - agent_start) * 1000)
        total_ms = int((time.perf_counter() - start) * 1000)

        return {
            "mode": "agent",
            "success": status == "success",
            "duration_ms": total_ms,
            "query": query,
            "agent_id": agent_id,
            "agents_used": [agent_id] if status == "success" else [],
            "selected_agents": [agent_id],
            "agent_results": [
                {
                    "agent_id": agent_id,
                    "name": instance.name,
                    "status": status,
                    "duration_ms": agent_ms,
                    "output": output,
                    "error": error,
                }
            ],
            "final_output": _format_agent_output(output) if status == "success" else None,
            "emergency": bool(output.get("emergency")),
            "errors": [error] if error else [],
        }

    async def _run_workflow(
        self,
        query: str,
        ctx: dict[str, Any],
        start: float,
        force_agent: str | None = None,
    ) -> dict[str, Any]:
        force_agents = [force_agent] if force_agent else None

        try:
            runner = WorkflowRunner()
            wf = await runner.run(
                workflow_name="admin_playground",
                query=query,
                patient_context=ctx,
                agents=force_agents,
            )
            state = wf.state
        except Exception as exc:
            total_ms = int((time.perf_counter() - start) * 1000)
            return {
                "mode": "workflow",
                "success": False,
                "duration_ms": total_ms,
                "query": query,
                "intent": None,
                "urgency": None,
                "selected_agents": force_agents or [],
                "agents_used": [],
                "agent_results": [],
                "final_output": None,
                "emergency": False,
                "errors": [str(exc)],
            }

        agent_results = []
        for aid, output in state.get("agent_outputs", {}).items():
            agent_results.append(
                {
                    "agent_id": aid,
                    "status": "failed" if output.get("error") else "success",
                    "output": output,
                    "error": output.get("error"),
                }
            )

        total_ms = int((time.perf_counter() - start) * 1000)
        out_of_scope = state.get("out_of_scope", False) or state.get("intent") == "out_of_scope"

        return {
            "mode": "workflow",
            "success": not out_of_scope,
            "duration_ms": total_ms,
            "query": query,
            "intent": state.get("intent"),
            "urgency": state.get("urgency"),
            "out_of_scope": out_of_scope,
            "selected_agents": state.get("selected_agents", []),
            "agents_used": state.get("agents_used", []),
            "agent_results": agent_results,
            "final_output": state.get("final_output") or wf.final_output,
            "emergency": state.get("emergency", False),
            "workflow_id": wf.id,
            "session_id": state.get("session_id"),
            "errors": [],
        }


def _format_agent_output(output: dict[str, Any]) -> str:
    for key in ("recommendation", "raw_response", "summary", "disclaimer"):
        if output.get(key):
            return str(output[key])
    import json

    return json.dumps(output, indent=2)
