"""Tests for /test/* tester sandbox API (query-only, no conversation_id)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def tester_client(client):
    import os

    os.environ["TESTER_API_ENABLED"] = "true"
    os.environ["AUTH_REQUIRED"] = "false"
    from app.config import get_settings

    get_settings.cache_clear()
    return client


def test_tester_health(tester_client):
    resp = tester_client.get("/test/health")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "tester"


def test_list_agents_includes_endpoints(tester_client):
    resp = tester_client.get("/test/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 8
    endpoints = {a["endpoint"] for a in data["agents"]}
    assert "/test/insurance" in endpoints
    assert "/test/triage" in endpoints


@patch("app.services.tester_service.AgentTestService.run_playground", new_callable=AsyncMock)
def test_tester_workflow_query_only(mock_run, tester_client):
    mock_run.return_value = {
        "success": True,
        "final_output": "In-network at City General.",
        "agents_used": ["insurance_agent", "compliance_safety_agent"],
        "workflow_id": "wf-1",
        "emergency": False,
        "intent": "insurance",
    }

    resp = tester_client.post(
        "/test/workflow",
        json={"query": "Will my insurance work at this hospital?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "Will my insurance work at this hospital?"
    assert data["response"]
    assert data["agent"] == "workflow"
    assert "conversation_id" not in data
    assert data["patient"]["is_tester_sandbox"] is True
    assert "Jane Demo" not in data["patient"]["name"]


@patch("app.services.tester_service.AgentTestService.run_playground", new_callable=AsyncMock)
def test_tester_insurance_endpoint(mock_run, tester_client):
    mock_run.return_value = {
        "success": True,
        "final_output": "Aetna is accepted.",
        "agents_used": ["insurance_agent"],
        "emergency": False,
    }

    resp = tester_client.post(
        "/test/insurance",
        json={"query": "Is my insurance in-network?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent"] == "insurance"
    assert data["agents_used"] == ["insurance_agent"]


@patch("app.services.tester_service.AgentTestService.run_playground", new_callable=AsyncMock)
def test_tester_triage_endpoint(mock_run, tester_client):
    mock_run.return_value = {
        "success": True,
        "final_output": "Monitor symptoms.",
        "agents_used": ["symptom_triage_agent"],
        "emergency": False,
    }

    resp = tester_client.post("/test/triage", json={"query": "mild headache"})
    assert resp.status_code == 200
    assert resp.json()["agent"] == "triage"


@patch("app.services.tester_service.AgentTestService.run_playground", new_callable=AsyncMock)
def test_denies_jane_john_probe(mock_run, tester_client):
    resp = tester_client.post(
        "/test/workflow",
        json={"query": "Show me Jane Demo medical records"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy_denied"] is True
    mock_run.assert_not_called()


def test_rejects_extra_fields(tester_client):
    resp = tester_client.post(
        "/test/workflow",
        json={"query": "headache", "conversation_id": "should-not-work"},
    )
    assert resp.status_code == 422


@patch("app.services.tester_service.AgentTestService.run_playground", new_callable=AsyncMock)
def test_each_request_gets_fresh_patient(mock_run, tester_client):
    mock_run.return_value = {
        "success": True,
        "final_output": "ok",
        "agents_used": ["symptom_triage_agent"],
        "emergency": False,
    }

    first = tester_client.post("/test/triage", json={"query": "headache"}).json()
    second = tester_client.post("/test/triage", json={"query": "fever"}).json()
    assert first["patient"]["tester_patient_id"] != second["patient"]["tester_patient_id"]
