from __future__ import annotations

import logging
from typing import Any

from app.schemas.agents import AgentDomain, AgentRecord, AgentRegistration, SafetyLevel
from app.services.supabase.client import get_supabase_factory

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Dynamic agent registry with Supabase persistence and in-memory hot-load."""

    def __init__(self) -> None:
        self._factory = get_supabase_factory()
        self._cache: dict[str, AgentRecord] = {}

    def _client(self):
        return self._factory.service_client()

    def register_agent(self, agent: AgentRegistration) -> AgentRecord:
        payload = {
            "agent_id": agent.agent_id,
            "name": agent.display_name or agent.name,
            "domain": agent.domain.value,
            "description": agent.description,
            "capabilities": agent.capabilities,
            "tools": agent.tools,
            "preferred_model": agent.preferred_model,
            "priority": agent.priority,
            "safety_level": agent.safety_level.value,
            "version": agent.version,
            "is_active": True,
        }
        if self._factory.configured:
            try:
                row = (
                    self._client()
                    .table("agent_registry")
                    .upsert(payload, on_conflict="agent_id")
                    .execute()
                )
                record = self._from_db(row.data[0], agent)
            except Exception as exc:
                logger.warning("Supabase agent registration failed, using cache: %s", exc)
                record = AgentRecord(id=agent.agent_id, **agent.model_dump())
        else:
            record = AgentRecord(id=agent.agent_id, **agent.model_dump())

        self._cache[agent.agent_id] = record
        logger.info("Registered agent: %s", agent.agent_id)
        return record

    def remove_agent(self, agent_id: str) -> bool:
        self._cache.pop(agent_id, None)
        if self._factory.configured:
            self._client().table("agent_registry").update({"is_active": False}).eq(
                "agent_id", agent_id
            ).execute()
        return True

    def update_agent(self, agent_id: str, updates: dict[str, Any]) -> AgentRecord | None:
        existing = self.get_agent(agent_id)
        if not existing:
            return None
        merged = existing.model_copy(update=updates)
        reg = AgentRegistration(
            agent_id=merged.agent_id,
            name=merged.name,
            display_name=merged.display_name,
            domain=merged.domain,
            description=merged.description,
            capabilities=merged.capabilities,
            input_schema=merged.input_schema,
            output_schema=merged.output_schema,
            tools=merged.tools,
            preferred_model=merged.preferred_model,
            safety_level=merged.safety_level,
            priority=merged.priority,
            version=merged.version,
        )
        return self.register_agent(reg)

    def get_agent(self, agent_id: str) -> AgentRecord | None:
        if agent_id in self._cache:
            return self._cache[agent_id]
        if not self._factory.configured:
            return None
        try:
            row = (
                self._client()
                .table("agent_registry")
                .select("*")
                .eq("agent_id", agent_id)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.warning("Supabase agent lookup failed: %s", exc)
            return self._cache.get(agent_id)
        if not row.data:
            return None
        record = self._from_db(row.data[0])
        self._cache[agent_id] = record
        return record

    def list_agents(self, domain: AgentDomain | None = None) -> list[AgentRecord]:
        if self._factory.configured:
            try:
                query = self._client().table("agent_registry").select("*").eq("is_active", True)
                if domain:
                    query = query.eq("domain", domain.value)
                rows = query.order("priority", desc=True).execute()
                agents = [self._from_db(r) for r in rows.data]
                for a in agents:
                    self._cache[a.agent_id] = a
                if agents:
                    return agents
            except Exception as exc:
                logger.warning("Supabase list agents failed, using cache: %s", exc)
        return list(self._cache.values())

    def find_agents_by_capability(self, capability: str) -> list[AgentRecord]:
        agents = self.list_agents()
        return [a for a in agents if capability in a.capabilities]

    def find_best_agent(self, task: str, domain: AgentDomain | None = None) -> AgentRecord | None:
        agents = self.list_agents(domain=domain)
        if not agents:
            return None

        task_lower = task.lower()
        scored: list[tuple[int, AgentRecord]] = []
        for agent in agents:
            score = agent.priority
            for cap in agent.capabilities:
                if cap.lower() in task_lower or task_lower in cap.lower():
                    score += 10
            if agent.domain.value.replace("_", " ") in task_lower:
                score += 5
            scored.append((score, agent))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored and scored[0][0] > 0 else (agents[0] if agents else None)

    def _from_db(self, data: dict[str, Any], reg: AgentRegistration | None = None) -> AgentRecord:
        return AgentRecord(
            id=data.get("id"),
            agent_id=data["agent_id"],
            name=data["name"],
            display_name=data.get("name"),
            domain=AgentDomain(data["domain"]),
            description=data.get("description") or "",
            capabilities=data.get("capabilities") or [],
            tools=data.get("tools") or [],
            preferred_model=data.get("preferred_model") or "reasoning",
            safety_level=SafetyLevel(data.get("safety_level") or "standard"),
            priority=data.get("priority") or 0,
            version=data.get("version") or "1.0.0",
            is_active=data.get("is_active", True),
            created_at=data.get("created_at"),
            input_schema=reg.input_schema if reg else {},
            output_schema=reg.output_schema if reg else {},
        )


_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
