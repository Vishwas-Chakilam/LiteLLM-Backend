from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

import litellm
from fastapi import FastAPI, HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.models.requests import ChatCompletionRequest, ChatMessage
from app.models.responses import (
    ChatChoice,
    ChatChoiceMessage,
    ChatCompletionResponse,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationMeta,
    CostSummaryResponse,
    HealthResponse,
    UsageInfo,
)
from app.security.limits import enforce_budgets, enforce_token_limits
from app.services.classifier import pick_tier
from app.services.cost_tracker import get_cost_tracker
from app.services.history_store import HistoryStore
from app.services.router_service import get_router_service
from app.services.system_prompt import prepare_messages_for_llm, resolve_system_prompt

limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.data_path().mkdir(parents=True, exist_ok=True)
    cost_tracker = get_cost_tracker()
    litellm.callbacks = [cost_tracker]
    try:
        get_router_service()
    except Exception as exc:
        logger.warning("Router not ready at startup: %s", exc)
    yield


app = FastAPI(
    title="LiteLLM Chat API",
    description="Multi-key LiteLLM backend with conversation history for PyRIT testing",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _history() -> HistoryStore:
    return HistoryStore()


def _latest_user_message(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    raise HTTPException(status_code=400, detail="At least one user message is required")

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.get("/v1/conversations", response_model=list[ConversationMeta])
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def list_conversations(request: Request) -> list[ConversationMeta]:
    return _history().list_conversations()


@app.post("/v1/conversations", response_model=ConversationCreateResponse)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def create_conversation(request: Request) -> ConversationCreateResponse:
    store = _history()
    conversation_id, meta = store.create_conversation()
    return ConversationCreateResponse(
        conversation_id=conversation_id,
        created_at=meta.created_at,
    )


@app.get("/v1/conversations/{conversation_id}", response_model=ConversationDetailResponse)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def get_conversation(
    request: Request,
    conversation_id: str,
) -> ConversationDetailResponse:
    store = _history()
    try:
        meta, transcript, messages = store.get_detail(conversation_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ConversationDetailResponse(
        conversation_id=conversation_id,
        meta=meta,
        transcript=transcript,
        messages=messages,
    )


@app.get("/v1/conversations/{conversation_id}/messages")
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def get_conversation_messages(request: Request, conversation_id: str):
    store = _history()
    try:
        _, _, messages = store.get_detail(conversation_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"conversation_id": conversation_id, "messages": messages}


@app.get("/v1/admin/cost", response_model=CostSummaryResponse)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def admin_cost(request: Request) -> CostSummaryResponse:
    settings = get_settings()
    tracker = get_cost_tracker()
    store = _history()
    conversations = [
        {
            "conversation_id": m.conversation_id,
            "turn_count": m.turn_count,
            "total_cost_usd": m.total_cost_usd,
            "updated_at": m.updated_at,
        }
        for m in store.list_conversations()
    ]
    return CostSummaryResponse(
        daily_spend_usd=tracker.daily_spend(),
        daily_budget_usd=settings.daily_budget_usd,
        conversation_count=len(conversations),
        conversations=conversations,
    )


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
) -> ChatCompletionResponse:
    if body.stream:
        raise HTTPException(status_code=400, detail="Streaming is not supported")

    store = _history()
    tracker = get_cost_tracker()
    router = get_router_service()

    conversation_id = body.conversation_id
    meta = None
    if conversation_id:
        try:
            meta = store.get_meta(conversation_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        conversation_id, meta = store.create_conversation()

    enforce_budgets(tracker, meta.total_cost_usd if meta else 0.0)
    max_tokens = enforce_token_limits(body.messages, max_output_tokens=body.max_tokens)

    tier = pick_tier(body.messages, meta, override=body.model)
    user_content = _latest_user_message(body.messages)

    settings = get_settings()
    system_prompt = resolve_system_prompt(
        settings.system_prompt,
        settings.system_prompt_enabled,
    )
    history_messages = store.parse_messages(store.read_transcript(conversation_id))
    llm_messages = prepare_messages_for_llm(
        history_messages,
        body.messages,
        system_prompt,
    )

    try:
        response = router.completion(
            tier=tier,
            messages=llm_messages,
            conversation_id=conversation_id,
            max_tokens=max_tokens,
            temperature=body.temperature,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM provider error: {exc}") from exc

    assistant_content = router.extract_content(response)
    prompt_tokens, completion_tokens, cost, model_used = router.extract_usage(response)

    store.append_turn(
        conversation_id,
        user_content=user_content,
        assistant_content=assistant_content,
        tier=tier,
        model=model_used,
        cost_usd=cost,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

    total_tokens = prompt_tokens + completion_tokens
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=tier,
        choices=[
            ChatChoice(
                message=ChatChoiceMessage(content=assistant_content),
            )
        ],
        usage=UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        ),
        conversation_id=conversation_id,
        tier=tier,
        model_used=model_used,
        estimated_cost_usd=round(cost, 8),
    )
