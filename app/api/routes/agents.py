from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.auth import get_auth_service, get_current_user
from app.registry.registry import get_agent_registry
from app.schemas.agents import AgentListResponse, AgentRecord, AgentRegistration
from app.schemas.auth import AuthResponse, LoginRequest, SignupRequest, UserProfile, UserRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["Agent Registry"])


@router.post("/register", response_model=AgentRecord)
async def register_agent(
    body: AgentRegistration,
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> AgentRecord:
    if user:
        get_auth_service().validate_role(user, {UserRole.ADMIN, UserRole.DOCTOR})
    return get_agent_registry().register_agent(body)


@router.get("", response_model=AgentListResponse)
async def list_agents(
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> AgentListResponse:
    agents = get_agent_registry().list_agents()
    return AgentListResponse(agents=agents, total=len(agents))


@router.get("/{agent_id}", response_model=AgentRecord)
async def get_agent(
    agent_id: str,
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> AgentRecord:
    agent = get_agent_registry().get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}")
async def remove_agent(
    agent_id: str,
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> dict:
    if user:
        get_auth_service().validate_role(user, {UserRole.ADMIN})
    get_agent_registry().remove_agent(agent_id)
    return {"removed": agent_id}
