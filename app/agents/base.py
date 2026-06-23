from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from app.llm.gateway import LLMGateway, get_llm_gateway
from app.mcp.client import MCPToolClient
from app.schemas.agents import AgentDomain, AgentRegistration
from app.services.supabase.audit_service import AuditService

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all healthcare agents."""

    agent_id: str = "base_agent"
    name: str = "Base Agent"
    domain: AgentDomain = AgentDomain.COMPLIANCE
    description: str = ""
    capabilities: list[str] = []
    allowed_tools: list[str] = []
    preferred_model_task: str = "reasoning"
    safety_level: str = "standard"
    version: str = "1.0.0"

    def __init__(
        self,
        llm: LLMGateway | None = None,
        mcp: MCPToolClient | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._llm = llm or get_llm_gateway()
        self._mcp = mcp or MCPToolClient()
        self._audit = audit or AuditService()

    def to_registration(self) -> AgentRegistration:
        return AgentRegistration(
            agent_id=self.agent_id,
            name=self.name,
            display_name=self.name,
            domain=self.domain,
            description=self.description,
            capabilities=self.capabilities,
            tools=self.allowed_tools,
            preferred_model=self.preferred_model_task,
            safety_level=self.safety_level,  # type: ignore[arg-type]
            version=self.version,
        )

    async def run(
        self,
        input_data: dict[str, Any],
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            output = await self.execute(input_data, conversation_id)
            elapsed = int((time.perf_counter() - start) * 1000)
            self._audit.log_agent_execution(
                conversation_id=conversation_id,
                agent_id=self.agent_id,
                input_data=input_data,
                output_data=output,
                execution_time_ms=elapsed,
                status="success",
            )
            return output
        except Exception as exc:
            elapsed = int((time.perf_counter() - start) * 1000)
            self._audit.log_agent_execution(
                conversation_id=conversation_id,
                agent_id=self.agent_id,
                input_data=input_data,
                output_data={"error": str(exc)},
                execution_time_ms=elapsed,
                status="failed",
            )
            raise

    @abstractmethod
    async def execute(
        self,
        input_data: dict[str, Any],
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        ...

    async def call_tool(self, server_id: str, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        if server_id not in self.allowed_tools and self.allowed_tools:
            raise PermissionError(f"Agent {self.agent_id} not allowed to use {server_id}")
        return await self._mcp.invoke(server_id, tool_name, params, agent_id=self.agent_id)

    def llm_json(
        self,
        system: str,
        user: str,
        task: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        result = self._llm.call_model(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            task=task or self.preferred_model_task,
            conversation_id=conversation_id,
        )
        content = result["content"]
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except json.JSONDecodeError:
            return {"raw_response": content, "model": result.get("model")}
