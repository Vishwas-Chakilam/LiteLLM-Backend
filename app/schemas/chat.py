from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class SenderType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    AGENT = "agent"
    SYSTEM = "system"


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    session_id: str | None = None
    patient_context: dict[str, Any] | None = None
    demo_patient_index: int | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    session_id: str
    message: str
    agents_used: list[str] = Field(default_factory=list)
    workflow_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    escalated: bool = False


class MessageRecord(BaseModel):
    id: str
    conversation_id: str
    sender_type: SenderType
    sender_agent_id: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationRecord(BaseModel):
    id: str
    user_id: str
    session_id: str
    title: str | None = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConversationHistoryResponse(BaseModel):
    conversation: ConversationRecord
    messages: list[MessageRecord]
