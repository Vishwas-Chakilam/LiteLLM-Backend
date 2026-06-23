"""Tests for the healthcare multi-agent platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents import AGENT_MAP, bootstrap_agents
from app.agents.triage import SymptomTriageAgent
from app.registry.registry import AgentRegistry
from app.schemas.agents import AgentDomain, AgentRegistration


@pytest.fixture
def registry():
    from app.registry.registry import AgentRegistry

    return AgentRegistry()


@pytest.fixture
def triage_agent():
    agent = SymptomTriageAgent()
    agent.llm_json = MagicMock(
        return_value={
            "severity_score": 3,
            "urgency_level": "routine",
            "risk_factors": [],
            "recommendation": "Schedule a routine visit.",
        }
    )
    return agent


class TestAgentRegistry:
    def test_register_and_get_agent(self, registry):
        reg = AgentRegistration(
            agent_id="test_agent",
            name="Test Agent",
            domain=AgentDomain.TRIAGE,
            capabilities=["symptom_analysis"],
        )
        record = registry.register_agent(reg)
        assert record.agent_id == "test_agent"
        fetched = registry.get_agent("test_agent")
        assert fetched is not None
        assert fetched.domain == AgentDomain.TRIAGE

    def test_find_best_agent(self, registry):
        registry.register_agent(
            AgentRegistration(
                agent_id="pa_agent",
                name="PA",
                domain=AgentDomain.PRIOR_AUTHORIZATION,
                capabilities=["prior_authorization", "icd_validation"],
                priority=5,
            )
        )
        best = registry.find_best_agent("MRI prior authorization needed")
        assert best is not None
        assert best.agent_id == "pa_agent"

    def test_find_agents_by_capability(self, registry):
        registry.register_agent(
            AgentRegistration(
                agent_id="lab_agent",
                name="Lab",
                domain=AgentDomain.LAB_ANALYSIS,
                capabilities=["cbc_analysis"],
            )
        )
        agents = registry.find_agents_by_capability("cbc_analysis")
        assert len(agents) == 1


class TestSymptomTriageAgent:
    @pytest.mark.asyncio
    async def test_emergency_detection(self, triage_agent):
        triage_agent.llm_json = MagicMock()
        result = await triage_agent.run({"query": "I have severe chest pain"})
        assert result["emergency"] is True
        assert result["urgency_level"] == "emergency"
        triage_agent.llm_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_routine_triage(self, triage_agent):
        result = await triage_agent.run({"query": "mild headache for 2 days"})
        assert result["severity_score"] == 3
        assert result["urgency_level"] == "routine"


class TestBootstrap:
    def test_all_agents_registered(self):
        from app.registry.registry import get_agent_registry

        get_agent_registry()._cache.clear()
        bootstrap_agents()
        agents = get_agent_registry().list_agents()
        assert len(agents) >= len(AGENT_MAP)

    def test_agent_map_complete(self):
        expected = {
            "symptom_triage_agent",
            "medication_agent",
            "lab_analysis_agent",
            "medical_records_agent",
            "appointment_agent",
            "insurance_agent",
            "prior_authorization_agent",
            "compliance_safety_agent",
        }
        assert set(AGENT_MAP.keys()) == expected


class TestManagerAgent:
    @pytest.mark.asyncio
    async def test_select_agents_prior_auth(self):
        from app.orchestrator.manager import ManagerAgent

        manager = ManagerAgent()
        agents = manager.select_agents(
            "Patient needs MRI authorization and has chest pain",
            {"intent": "prior_auth", "urgency": "urgent"},
        )
        assert "prior_authorization_agent" in agents
        assert "symptom_triage_agent" in agents
        assert "compliance_safety_agent" in agents

    @pytest.mark.asyncio
    async def test_execute_workflow_emergency(self):
        from app.orchestrator.manager import ManagerAgent

        manager = ManagerAgent()
        with (
            patch.object(manager, "classify_intent", return_value={"intent": "triage", "urgency": "emergency"}),
            patch.object(manager, "_synthesize", return_value="Seek emergency care"),
            patch("app.orchestrator.manager.get_agent_instance") as mock_get,
        ):
            triage = SymptomTriageAgent()
            triage.run = AsyncMock(
                return_value={
                    "severity_score": 10,
                    "urgency_level": "emergency",
                    "recommendation": "Call 911",
                    "emergency": True,
                }
            )
            safety = MagicMock()
            safety.run = AsyncMock(return_value={"safe": True, "escalate": True})

            def agent_factory(agent_id):
                if agent_id == "symptom_triage_agent":
                    return triage
                if agent_id == "compliance_safety_agent":
                    return safety
                return None

            mock_get.side_effect = agent_factory
            state = await manager.execute_workflow("severe chest pain radiating to arm")
        assert state["emergency"] is True
        assert "symptom_triage_agent" in state["agents_used"]


class TestHealthcareAPI:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_list_agents(self, client):
        bootstrap_agents()
        resp = client.get("/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= len(AGENT_MAP)

    def test_chat_endpoint(self, client):
        with patch("app.workflows.runner.WorkflowRunner.run") as mock_run:
            from app.schemas.workflow import WorkflowRunResponse, WorkflowStatus

            mock_run.return_value = WorkflowRunResponse(
                id="wf-1",
                workflow_name="healthcare_chat",
                status=WorkflowStatus.COMPLETED,
                final_output="This is a test response.",
                agents_used=["symptom_triage_agent"],
                state={"emergency": False, "session_id": "sess-1"},
            )
            resp = client.post("/chat", json={"message": "I have a headache"})
            assert resp.status_code == 200
            body = resp.json()
            assert body["message"] == "This is a test response."
            assert "symptom_triage_agent" in body["agents_used"]
