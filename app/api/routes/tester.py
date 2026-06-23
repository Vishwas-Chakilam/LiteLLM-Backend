from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.schemas.tester import (
    TesterAgentsResponse,
    TesterHealthResponse,
    TesterPatientProfile,
    TesterQueryRequest,
    TesterQueryResponse,
)
from app.services.tester_service import TESTER_AGENT_ENDPOINTS, TesterService

router = APIRouter(prefix="/test", tags=["Tester"])


def _svc() -> TesterService:
    return TesterService()


def _ensure_enabled() -> None:
    if not get_settings().tester_api_enabled:
        raise HTTPException(status_code=404, detail="Tester API is disabled")


def _to_response(data: dict) -> TesterQueryResponse:
    patient = data["patient"]
    if isinstance(patient, dict):
        patient = TesterPatientProfile(**patient)
    return TesterQueryResponse(
        query=data["query"],
        response=data.get("response") or "",
        agent=data["agent"],
        agents_used=data.get("agents_used", []),
        patient=patient,
        workflow_id=data.get("workflow_id"),
        escalated=bool(data.get("emergency")),
        policy_denied=bool(data.get("policy_denied")),
        metadata=data.get("metadata") or {},
    )


@router.get("/health", response_model=TesterHealthResponse)
async def tester_health() -> TesterHealthResponse:
    _ensure_enabled()
    return TesterHealthResponse()


@router.get("/agents", response_model=TesterAgentsResponse)
async def list_tester_agents(
    svc: Annotated[TesterService, Depends(_svc)],
) -> TesterAgentsResponse:
    """List agents and their dedicated tester endpoints."""
    _ensure_enabled()
    agents = svc.list_agents()
    return TesterAgentsResponse(agents=agents, total=len(agents))


@router.post("/workflow", response_model=TesterQueryResponse)
async def tester_workflow(
    body: TesterQueryRequest,
    svc: Annotated[TesterService, Depends(_svc)],
) -> TesterQueryResponse:
    """
    Multi-agent orchestration. Send only `query` — no auth, no conversation_id.

    The orchestrator picks agents automatically based on your query.
    """
    _ensure_enabled()
    data = await svc.run_workflow(body.query)
    return _to_response(data)


def _register_agent_routes() -> None:
    for endpoint in TESTER_AGENT_ENDPOINTS:

        async def _handler(
            body: TesterQueryRequest,
            svc: Annotated[TesterService, Depends(_svc)],
            _endpoint: str = endpoint,
        ) -> TesterQueryResponse:
            _ensure_enabled()
            data = await svc.run_agent(_endpoint, body.query)
            return _to_response(data)

        _handler.__name__ = f"tester_{endpoint.replace('-', '_')}"
        _handler.__doc__ = (
            f"Run the **{endpoint}** agent directly. Body: `{{\"query\": \"...\"}}` only."
        )
        router.post(
            f"/{endpoint}",
            response_model=TesterQueryResponse,
            summary=f"Agent: {endpoint}",
        )(_handler)


_register_agent_routes()
