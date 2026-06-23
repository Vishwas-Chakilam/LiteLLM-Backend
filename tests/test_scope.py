"""Tests for healthcare-only query scope detection."""

from __future__ import annotations

import pytest

from app.orchestrator.scope import OUT_OF_SCOPE_MESSAGE, detect_query_scope


class TestQueryScope:
    def test_deploy_on_render_is_out_of_scope(self):
        assert detect_query_scope("how to deploy an application on render") == "out_of_scope"

    def test_healthcare_queries_allowed(self):
        assert detect_query_scope("I have chest pain") == "healthcare"
        assert detect_query_scope("MRI prior authorization for Aetna") == "healthcare"
        assert detect_query_scope("drug interaction metformin and ibuprofen") == "healthcare"

    def test_coding_is_out_of_scope(self):
        assert detect_query_scope("how to write a python fastapi app") == "out_of_scope"

    @pytest.mark.asyncio
    async def test_workflow_rejects_non_healthcare_without_agents(self):
        from app.orchestrator.manager import ManagerAgent

        manager = ManagerAgent()
        state = await manager.execute_workflow("how to deploy an application on render")
        assert state["intent"] == "out_of_scope"
        assert state["agents_used"] == []
        assert "healthcare-only" in state["final_output"].lower()
        assert state["final_output"] == OUT_OF_SCOPE_MESSAGE

    @pytest.mark.asyncio
    async def test_playground_out_of_scope(self, client):
        resp = client.post(
            "/admin/api/playground/run",
            json={"query": "how to deploy an application on render", "mode": "workflow"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "out_of_scope"
        assert data["out_of_scope"] is True
        assert data["agents_used"] == []
        assert "healthcare-only" in (data["final_output"] or "").lower()
