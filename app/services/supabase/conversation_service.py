from __future__ import annotations

import logging
import uuid
from typing import Any

from app.schemas.chat import (
    ConversationHistoryResponse,
    ConversationRecord,
    ConversationStatus,
    MessageRecord,
    SenderType,
)
from app.services.supabase.client import get_supabase_factory

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(self) -> None:
        self._factory = get_supabase_factory()

    def _client(self):
        return self._factory.service_client()

    def create_conversation(
        self,
        user_id: str,
        title: str | None = None,
        session_id: str | None = None,
    ) -> ConversationRecord:
        sid = session_id or str(uuid.uuid4())
        row = (
            self._client().table("conversations")
            .insert(
                {
                    "user_id": user_id,
                    "session_id": sid,
                    "title": title or "New conversation",
                    "status": ConversationStatus.ACTIVE.value,
                }
            )
            .execute()
        )
        return self._to_conversation(row.data[0])

    def store_message(
        self,
        conversation_id: str,
        sender_type: SenderType,
        message: str,
        sender_agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        row = (
            self._client().table("messages")
            .insert(
                {
                    "conversation_id": conversation_id,
                    "sender_type": sender_type.value,
                    "sender_agent_id": sender_agent_id,
                    "message": message,
                    "metadata": metadata or {},
                }
            )
            .execute()
        )
        return self._to_message(row.data[0])

    def fetch_history(self, conversation_id: str, limit: int = 100) -> ConversationHistoryResponse:
        conv = (
            self._client().table("conversations")
            .select("*")
            .eq("id", conversation_id)
            .single()
            .execute()
        )
        messages = (
            self._client().table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return ConversationHistoryResponse(
            conversation=self._to_conversation(conv.data),
            messages=[self._to_message(m) for m in messages.data],
        )

    def fetch_by_session(self, user_id: str, session_id: str) -> ConversationRecord | None:
        row = (
            self._client().table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not row.data:
            return None
        return self._to_conversation(row.data[0])

    def update_status(self, conversation_id: str, status: ConversationStatus) -> None:
        self._client().table("conversations").update({"status": status.value}).eq(
            "id", conversation_id
        ).execute()

    def _to_conversation(self, data: dict[str, Any]) -> ConversationRecord:
        return ConversationRecord(
            id=data["id"],
            user_id=data["user_id"],
            session_id=data["session_id"],
            title=data.get("title"),
            status=ConversationStatus(data["status"]),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def _to_message(self, data: dict[str, Any]) -> MessageRecord:
        return MessageRecord(
            id=data["id"],
            conversation_id=data["conversation_id"],
            sender_type=SenderType(data["sender_type"]),
            sender_agent_id=data.get("sender_agent_id"),
            message=data["message"],
            metadata=data.get("metadata") or {},
            created_at=data["created_at"],
        )
