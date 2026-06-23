from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.middleware.auth import require_admin
from app.schemas.auth import UserProfile
from app.services.admin_service import AdminService
from app.services.agent_test_service import AgentTestService

router = APIRouter(prefix="/admin", tags=["Admin"])
_TEMPLATE = Path(__file__).resolve().parents[2] / "admin" / "templates" / "dashboard.html"


def _admin() -> AdminService:
    return AdminService()


def _playground() -> AgentTestService:
    return AgentTestService()


class RoleUpdate(BaseModel):
    role: str


class AssignmentCreate(BaseModel):
    doctor_id: str
    patient_id: str


class PlaygroundRequest(BaseModel):
    query: str = ""
    mode: Literal["workflow", "agent", "health"] = "workflow"
    agent_id: str | None = None
    patient_context: dict[str, Any] | None = None
    demo_patient_index: int | None = None


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def admin_ui() -> HTMLResponse:
    return HTMLResponse(_TEMPLATE.read_text(encoding="utf-8"))


@router.get("/api/stats")
async def admin_stats(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> dict[str, Any]:
    return svc.dashboard_stats()


@router.get("/api/users")
async def admin_users(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_users()


@router.patch("/api/users/{user_id}")
async def admin_update_user_role(
    user_id: str,
    body: RoleUpdate,
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> dict[str, Any]:
    try:
        return svc.update_user_role(user_id, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/conversations")
async def admin_conversations(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_conversations()


@router.get("/api/conversations/{conversation_id}/messages")
async def admin_messages(
    conversation_id: str,
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_messages(conversation_id)


@router.get("/api/agents")
async def admin_agents(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_agents()


@router.get("/api/agents/health")
async def admin_agents_health(
    _: Annotated[UserProfile, Depends(require_admin)],
    tester: Annotated[AgentTestService, Depends(_playground)],
) -> dict[str, Any]:
    return tester.health_check()


@router.get("/api/playground/samples")
async def playground_samples(
    _: Annotated[UserProfile, Depends(require_admin)],
    tester: Annotated[AgentTestService, Depends(_playground)],
) -> list[dict[str, str]]:
    return tester.list_samples()


@router.post("/api/playground/run")
async def playground_run(
    body: PlaygroundRequest,
    _: Annotated[UserProfile, Depends(require_admin)],
    tester: Annotated[AgentTestService, Depends(_playground)],
) -> dict[str, Any]:
    try:
        if body.mode != "health" and not body.query.strip():
            raise HTTPException(status_code=400, detail="query is required")
        return await tester.run_playground(
            query=body.query,
            mode=body.mode,
            agent_id=body.agent_id,
            patient_context=body.patient_context,
            demo_patient_index=body.demo_patient_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/prior-auth")
async def admin_prior_auth(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_prior_auth()


@router.get("/api/workflows")
async def admin_workflows(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_workflows()


@router.get("/api/audit-logs")
async def admin_audit_logs(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_audit_logs()


@router.get("/api/agent-logs")
async def admin_agent_logs(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_agent_logs()


@router.get("/api/tool-logs")
async def admin_tool_logs(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_tool_logs()


@router.get("/api/patients")
async def admin_patients(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_patient_profiles()


@router.get("/api/assignments")
async def admin_assignments(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> list[dict[str, Any]]:
    return svc.list_assignments()


@router.post("/api/assignments")
async def admin_create_assignment(
    body: AssignmentCreate,
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> dict[str, Any]:
    try:
        return svc.create_assignment(body.doctor_id, body.patient_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/hospital")
async def admin_hospital(
    _: Annotated[UserProfile, Depends(require_admin)],
) -> dict[str, Any]:
    from app.services.hospital_data_service import get_hospital_service

    svc = get_hospital_service()
    return svc.get_context_snapshot()


@router.get("/api/hospital/demo-patients")
async def admin_demo_patients(
    _: Annotated[UserProfile, Depends(require_admin)],
) -> list[dict[str, Any]]:
    from app.services.hospital_data_service import get_hospital_service

    return get_hospital_service().get_demo_patients()


@router.get("/api/cost")
async def admin_cost(
    _: Annotated[UserProfile, Depends(require_admin)],
    svc: Annotated[AdminService, Depends(_admin)],
) -> dict[str, Any]:
    return svc.cost_summary()
