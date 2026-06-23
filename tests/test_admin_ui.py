"""Tests for admin dashboard UI and API."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch


class TestAdminUI:
    def test_admin_page_loads(self, client):
        resp = client.get("/admin")
        assert resp.status_code == 200
        assert "Admin Console" in resp.text
        assert "Agent Playground" in resp.text

    def test_admin_static_css(self, client):
        resp = client.get("/admin/static/admin.css")
        assert resp.status_code == 200
        assert "playground-layout" in resp.text

    def test_admin_stats_api(self, client):
        resp = client.get("/admin/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "daily_spend_usd" in data
        assert "registered_agents" in data

    def test_admin_agents_api(self, client):
        resp = client.get("/admin/api/agents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_admin_agents_health(self, client):
        resp = client.get("/admin/api/agents/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "healthy" in data
        assert data["agent_count"] >= 8
        assert len(data["agents"]) >= 8

    def test_playground_samples(self, client):
        resp = client.get("/admin/api/playground/samples")
        assert resp.status_code == 200
        samples = resp.json()
        assert len(samples) >= 5
        assert "query" in samples[0]

    def test_playground_health_mode(self, client):
        resp = client.post("/admin/api/playground/run", json={"mode": "health"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("healthy") is not None or data.get("agents")

    def test_playground_workflow_mock(self, client):
        with patch("app.services.agent_test_service.WorkflowRunner") as mock_runner:
            from app.schemas.workflow import WorkflowRunResponse, WorkflowStatus

            instance = mock_runner.return_value
            instance.run = AsyncMock(
                return_value=WorkflowRunResponse(
                    id="wf-test",
                    workflow_name="admin_playground",
                    status=WorkflowStatus.COMPLETED,
                    final_output="Test response from workflow.",
                    agents_used=["symptom_triage_agent"],
                    state={
                        "intent": "triage",
                        "urgency": "routine",
                        "selected_agents": ["symptom_triage_agent", "compliance_safety_agent"],
                        "agents_used": ["symptom_triage_agent", "compliance_safety_agent"],
                        "agent_outputs": {
                            "symptom_triage_agent": {"severity_score": 3, "recommendation": "Rest"},
                        },
                        "emergency": False,
                        "final_output": "Test response from workflow.",
                    },
                )
            )
            with patch("app.services.agent_test_service.get_manager") as mock_mgr:
                mock_mgr.return_value.classify_intent.return_value = {
                    "intent": "triage",
                    "urgency": "routine",
                }
                mock_mgr.return_value.select_agents.return_value = ["symptom_triage_agent"]
                resp = client.post(
                    "/admin/api/playground/run",
                    json={"query": "mild headache", "mode": "workflow"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["final_output"] == "Test response from workflow."

    def test_admin_cost_api(self, client):
        resp = client.get("/admin/api/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert "daily_spend_usd" in data
        assert "conversations" in data

    def test_root_links_admin(self, client):
        resp = client.get("/")
        assert resp.json().get("admin") == "/admin"
