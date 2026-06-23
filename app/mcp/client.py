from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.services.hospital_data_service import get_hospital_service
from app.services.supabase.audit_service import AuditService

logger = logging.getLogger(__name__)


class MCPToolClient:
    """Client for MCP server tool invocations."""

    HOSPITAL_TOOLS = {
        "get_hospital_info",
        "get_accepted_insurers",
        "check_insurance_accepted",
        "list_departments",
        "list_providers",
        "list_services",
        "get_hospital_payer_rules",
        "get_lab_reference_range",
    }

    def __init__(self) -> None:
        self._settings = get_settings()
        self._servers = self._load_config()
        self._audit = AuditService()
        self._hospital = get_hospital_service()

    def _load_config(self) -> dict[str, dict[str, Any]]:
        path = Path(self._settings.mcp_servers_config)
        if not path.exists():
            return self._default_servers()
        data = json.loads(path.read_text(encoding="utf-8"))
        return {**self._default_servers(), **data}

    def _default_servers(self) -> dict[str, dict[str, Any]]:
        return {
            "hospital_mcp": {
                "internal": True,
                "tools": list(self.HOSPITAL_TOOLS),
            },
            "icd_lookup_mcp": {"url": "http://localhost:8101", "tools": ["lookup_icd"]},
            "cpt_lookup_mcp": {"url": "http://localhost:8102", "tools": ["lookup_cpt"]},
            "payer_rules_mcp": {"url": "http://localhost:8103", "tools": ["get_payer_rules"]},
            "drug_database_mcp": {"url": "http://localhost:8104", "tools": ["drug_info", "interactions"]},
            "lab_reference_mcp": {"url": "http://localhost:8105", "tools": ["reference_range"]},
            "pubmed_mcp": {"url": "http://localhost:8106", "tools": ["search"]},
        }

    def list_tools(self, server_id: str) -> list[str]:
        server = self._servers.get(server_id, {})
        return server.get("tools", [])

    async def invoke(
        self,
        server_id: str,
        tool_name: str,
        params: dict[str, Any],
        agent_id: str = "system",
    ) -> dict[str, Any]:
        server = self._servers.get(server_id, {})

        if server_id == "hospital_mcp" or server.get("internal"):
            result = self._hospital_tool(tool_name, params)
            self._audit.log_tool_invocation(agent_id, tool_name, params, result)
            return result

        if not server or not server.get("url"):
            result = self._mock_tool(server_id, tool_name, params)
            self._audit.log_tool_invocation(agent_id, tool_name, params, result)
            return result

        url = f"{server['url']}/tools/{tool_name}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=params)
                resp.raise_for_status()
                result = resp.json()
                self._audit.log_tool_invocation(agent_id, tool_name, params, result)
                return result
        except Exception as exc:
            logger.warning("MCP tool %s/%s failed, using mock: %s", server_id, tool_name, exc)
            result = self._mock_tool(server_id, tool_name, params)
            self._audit.log_tool_invocation(agent_id, tool_name, params, result, status="fallback")
            return result

    def _hospital_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        slug = params.get("hospital_slug") or self._settings.hospital_slug
        svc = self._hospital

        if tool_name == "get_hospital_info":
            return svc.get_hospital_info(slug)
        if tool_name == "get_accepted_insurers":
            return {"insurers": svc.get_accepted_insurers(slug), "hospital_slug": slug}
        if tool_name == "check_insurance_accepted":
            return svc.check_insurance_accepted(params.get("insurer", ""), slug)
        if tool_name == "list_departments":
            return {"departments": svc.list_departments(slug), "hospital_slug": slug}
        if tool_name == "list_providers":
            return {
                "providers": svc.list_providers(params.get("specialty"), slug),
                "hospital_slug": slug,
            }
        if tool_name == "list_services":
            return {"services": svc.list_services(slug), "hospital_slug": slug}
        if tool_name == "get_hospital_payer_rules":
            return svc.get_hospital_payer_rules(
                params.get("insurer", ""),
                params.get("procedure_type", "general"),
                slug,
            )
        if tool_name == "get_lab_reference_range":
            return svc.get_lab_reference_range(params.get("marker", ""), slug)

        return {"error": f"Unknown hospital tool: {tool_name}"}

    def _mock_tool(self, server_id: str, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Offline fallbacks — hospital tools always use Supabase/JSON via _hospital_tool."""
        if server_id == "hospital_mcp" or tool_name in self.HOSPITAL_TOOLS:
            return self._hospital_tool(tool_name, params)

        if tool_name == "lookup_icd":
            code = params.get("code", "")
            return {"code": code, "description": f"ICD-10 description for {code}", "valid": bool(code)}
        if tool_name == "lookup_cpt":
            code = params.get("code", "")
            return {"code": code, "description": f"CPT procedure for {code}", "valid": bool(code)}
        if tool_name == "get_payer_rules":
            insurer = params.get("insurer", "")
            procedure = params.get("procedure", "general")
            slug = params.get("hospital_slug") or self._settings.hospital_slug
            rules = self._hospital.get_hospital_payer_rules(insurer, procedure, slug)
            return {"insurer": insurer, "procedure": procedure, **rules}
        if tool_name == "drug_info":
            return {"name": params.get("drug", ""), "class": "unknown", "warnings": []}
        if tool_name == "interactions":
            return {"drugs": params.get("drugs", []), "interactions": [], "severity": "none"}
        if tool_name == "reference_range":
            marker = params.get("marker", "")
            slug = params.get("hospital_slug") or self._settings.hospital_slug
            return self._hospital.get_lab_reference_range(marker, slug)
        if tool_name == "search":
            return {"query": params.get("query", ""), "results": []}
        return {"server": server_id, "tool": tool_name, "status": "mock"}
