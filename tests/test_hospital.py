"""Tests for hospital master data (Option 1: Supabase + MCP tools)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.hospital_data_service import HospitalDataService


@pytest.fixture
def hospital_svc():
    return HospitalDataService()


class TestHospitalDataService:
    def test_get_hospital_info_fallback(self, hospital_svc):
        info = hospital_svc.get_hospital_info("city_general")
        assert info["name"] == "City General Hospital"
        assert info["slug"] == "city_general"

    def test_get_accepted_insurers(self, hospital_svc):
        plans = hospital_svc.get_accepted_insurers()
        assert len(plans) >= 5
        ids = [p["insurer_id"] for p in plans]
        assert "aetna" in ids
        assert "united" in ids

    def test_check_insurance_aetna_in_network(self, hospital_svc):
        result = hospital_svc.check_insurance_accepted("aetna")
        assert result["accepted"] is True
        assert result["in_network"] is True
        assert "City General" in result["hospital"]

    def test_check_insurance_humana_out_of_network(self, hospital_svc):
        result = hospital_svc.check_insurance_accepted("humana")
        assert result["in_network"] is False

    def test_check_insurance_missing_insurer(self, hospital_svc):
        result = hospital_svc.check_insurance_accepted("")
        assert result["accepted"] is False

    def test_list_departments(self, hospital_svc):
        depts = hospital_svc.list_departments()
        assert any("Emergency" in d["name"] for d in depts)

    def test_list_providers_cardiology(self, hospital_svc):
        providers = hospital_svc.list_providers("Cardiology")
        assert len(providers) >= 1

    def test_get_hospital_payer_rules(self, hospital_svc):
        rules = hospital_svc.get_hospital_payer_rules("aetna", "mri")
        assert rules.get("requires_clinical_notes") is True

    def test_get_lab_reference_range(self, hospital_svc):
        ref = hospital_svc.get_lab_reference_range("hemoglobin")
        assert ref["low"] == 12.0
        assert ref["high"] == 17.5

    def test_context_snapshot(self, hospital_svc):
        snap = hospital_svc.get_context_snapshot()
        assert snap["hospital_name"] == "City General Hospital"
        assert len(snap["accepted_insurers"]) >= 5


class TestHospitalMCP:
    @pytest.mark.asyncio
    async def test_hospital_mcp_check_insurance(self):
        from app.mcp.client import MCPToolClient

        client = MCPToolClient()
        result = await client.invoke(
            "hospital_mcp",
            "check_insurance_accepted",
            {"insurer": "aetna"},
            agent_id="test",
        )
        assert result["in_network"] is True

    @pytest.mark.asyncio
    async def test_insurance_agent_with_hospital_context(self):
        from app.agents.insurance import InsuranceAgent

        agent = InsuranceAgent()
        agent.llm_json = lambda *a, **k: {
            "eligibility_status": "likely_covered",
            "in_network": True,
        }
        result = await agent.run(
            {
                "query": "Will my insurance be valid at this hospital?",
                "insurer": "aetna",
                "insurance_provider": "aetna",
                "hospital_slug": "city_general",
                "hospital_name": "City General Hospital",
            }
        )
        assert result.get("in_network") is True
        assert result.get("coverage_check", {}).get("accepted") is True


class TestInsuranceWorkflow:
    @pytest.mark.asyncio
    async def test_workflow_insurance_question(self):
        from app.agents.compliance_safety import ComplianceSafetyAgent
        from app.agents.insurance import InsuranceAgent
        from app.orchestrator.manager import ManagerAgent

        manager = ManagerAgent()
        ins_agent = InsuranceAgent()
        ins_agent.llm_json = lambda *a, **k: {"eligibility_status": "likely_covered"}
        comp = ComplianceSafetyAgent()
        comp.llm_json = lambda *a, **k: {"safe": True}

        with (
            patch.object(manager, "classify_intent", return_value={"intent": "insurance", "urgency": "routine"}),
            patch.object(manager, "_synthesize", return_value="Aetna is in-network at City General Hospital."),
            patch("app.orchestrator.manager.get_agent_instance") as mock_get,
        ):
            mock_get.side_effect = lambda aid: {
                "insurance_agent": ins_agent,
                "compliance_safety_agent": comp,
            }.get(aid)

            state = await manager.execute_workflow(
                "Will my insurance be valid at this hospital?",
                patient_context={
                    "insurer": "aetna",
                    "insurance_provider": "aetna",
                    "hospital_slug": "city_general",
                    "hospital_name": "City General Hospital",
                },
            )
        assert "insurance_agent" in state["agents_used"]
        ins_out = state["agent_outputs"].get("insurance_agent", {})
        assert ins_out.get("in_network") is True or ins_out.get("coverage_check", {}).get("in_network") is True
