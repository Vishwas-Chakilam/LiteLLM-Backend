from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user
from app.schemas.auth import UserProfile
from app.schemas.chat import ChatRequest, ChatResponse, SenderType
from app.schemas.prior_auth import PriorAuthCreateRequest, PriorAuthResponse, PriorAuthUpdateRequest
from app.schemas.workflow import WorkflowRunRequest, WorkflowRunResponse
from app.config import get_settings
from app.orchestrator.manager import get_manager
from app.services.supabase.audit_service import AuditService
from app.services.supabase.client import get_supabase_factory
from app.services.supabase.conversation_service import ConversationService
from app.services.supabase.patient_service import PatientService
from app.services.supabase.prior_auth_service import PriorAuthService
from app.workflows.runner import WorkflowRunner

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Healthcare Platform"])


from app.services.context_builder import build_agent_context


def _store_message_safe(
    conversation_id: str,
    sender_type: SenderType,
    message: str,
    metadata: dict | None = None,
) -> None:
    if not get_supabase_factory().configured:
        return
    try:
        ConversationService().store_message(
            conversation_id=conversation_id,
            sender_type=sender_type,
            message=message,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning("Failed to store message: %s", exc)


def _resolve_conversation(
    user: UserProfile | None,
    conversation_id: str | None,
    session_id: str | None,
) -> tuple[str, str]:
    sid = session_id or str(uuid.uuid4())
    if not user or not get_supabase_factory().configured:
        return conversation_id or str(uuid.uuid4()), sid

    conv_service = ConversationService()
    if conversation_id:
        return conversation_id, sid

    existing = conv_service.fetch_by_session(user.id, sid) if session_id else None
    if existing:
        return existing.id, existing.session_id

    conv = conv_service.create_conversation(user.id, session_id=sid)
    return conv.id, conv.session_id


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> ChatResponse:
    runner = WorkflowRunner()
    audit = AuditService()
    user_id = user.id if user else "anonymous"
    patient_ctx = build_agent_context(user, body.patient_context, body.demo_patient_index)

    conversation_id, session_id = _resolve_conversation(user, body.conversation_id, body.session_id)

    _store_message_safe(
        conversation_id,
        SenderType.USER,
        body.message,
        metadata={"user_id": user_id},
    )

    workflow = await runner.run(
        workflow_name="healthcare_chat",
        query=body.message,
        conversation_id=conversation_id,
        patient_context=patient_ctx,
    )

    _store_message_safe(
        conversation_id,
        SenderType.ASSISTANT,
        workflow.final_output or "",
        metadata={"agents_used": workflow.agents_used, "workflow_id": workflow.id},
    )

    if user and get_supabase_factory().configured:
        try:
            audit.log_action(user_id, "chat_completed", "conversation", conversation_id)
        except Exception:
            pass

    return ChatResponse(
        conversation_id=conversation_id,
        session_id=session_id,
        message=workflow.final_output or "",
        agents_used=workflow.agents_used,
        workflow_id=workflow.id,
        metadata=workflow.state,
        escalated=workflow.state.get("emergency", False),
    )


@router.post("/workflow/run", response_model=WorkflowRunResponse)
async def run_workflow(
    body: WorkflowRunRequest,
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> WorkflowRunResponse:
    runner = WorkflowRunner()
    ctx = build_agent_context(user, body.patient_context, getattr(body, "demo_patient_index", None))
    return await runner.run(
        workflow_name=body.workflow_name,
        query=body.query,
        conversation_id=body.conversation_id,
        patient_context=ctx,
        agents=body.agents,
    )


@router.get("/workflow/{workflow_id}", response_model=WorkflowRunResponse)
async def get_workflow(
    workflow_id: str,
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> WorkflowRunResponse:
    runner = WorkflowRunner()
    result = runner.get_workflow(workflow_id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Workflow not found")
    return result


@router.post("/prior-auth", response_model=PriorAuthResponse)
async def create_prior_auth(
    body: PriorAuthCreateRequest,
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> PriorAuthResponse:
    if not get_supabase_factory().configured:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Supabase required for prior auth")

    prior_auth = PriorAuthService()
    audit = AuditService()
    manager = get_manager()

    case = prior_auth.create_case(body)
    state = await manager.execute_workflow(
        query=body.clinical_notes or "Prior authorization request",
        patient_context={
            "patient_id": body.patient_id,
            "insurer": body.insurer,
            "diagnosis_codes": body.diagnosis_codes,
            "procedure_codes": body.procedure_codes,
            **(body.patient_data or {}),
        },
        force_agents=["prior_authorization_agent", "compliance_safety_agent"],
    )

    pa_output = state.get("agent_outputs", {}).get("prior_authorization_agent", {})
    if pa_output:
        case = prior_auth.update_status(
            case.id,
            PriorAuthUpdateRequest(
                approval_probability=pa_output.get("approval_probability"),
                missing_documents=pa_output.get("missing_documents"),
                denial_risk=pa_output.get("denial_risk"),
            ),
        )
        case.payer_requirements = pa_output.get("payer_requirements", [])
        case.next_steps = pa_output.get("next_steps", [])

    if user:
        audit.log_prior_auth(user.id, case.id)

    return case


@router.patch("/prior-auth/{case_id}", response_model=PriorAuthResponse)
async def update_prior_auth(
    case_id: str,
    body: PriorAuthUpdateRequest,
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> PriorAuthResponse:
    return PriorAuthService().update_status(case_id, body)


@router.get("/prior-auth/{case_id}", response_model=PriorAuthResponse)
async def get_prior_auth(
    case_id: str,
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> PriorAuthResponse:
    return PriorAuthService().get_case(case_id)
