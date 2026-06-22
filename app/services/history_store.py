from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

from app.config import Settings, get_settings
from app.models.responses import ConversationMeta, TurnRecord

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HistoryStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base = self.settings.data_path()
        self.base.mkdir(parents=True, exist_ok=True)

    def _txt_path(self, conversation_id: str) -> Path:
        return self.base / f"{conversation_id}.txt"

    def _meta_path(self, conversation_id: str) -> Path:
        return self.base / f"{conversation_id}.meta.json"

    def _lock_path(self, conversation_id: str) -> Path:
        return self.base / f"{conversation_id}.lock"

    def validate_id(self, conversation_id: str) -> None:
        if not UUID_RE.match(conversation_id):
            raise ValueError("Invalid conversation_id format")

    def create_conversation(self) -> tuple[str, ConversationMeta]:
        conversation_id = str(uuid.uuid4())
        now = _utc_now()
        meta = ConversationMeta(
            conversation_id=conversation_id,
            created_at=now,
            updated_at=now,
        )
        self._write_meta(conversation_id, meta)
        self._txt_path(conversation_id).write_text("", encoding="utf-8")
        return conversation_id, meta

    def exists(self, conversation_id: str) -> bool:
        self.validate_id(conversation_id)
        return self._meta_path(conversation_id).exists()

    def get_meta(self, conversation_id: str) -> ConversationMeta:
        self.validate_id(conversation_id)
        path = self._meta_path(conversation_id)
        if not path.exists():
            raise FileNotFoundError(f"Conversation {conversation_id} not found")
        return ConversationMeta.model_validate_json(path.read_text(encoding="utf-8"))

    def _write_meta(self, conversation_id: str, meta: ConversationMeta) -> None:
        self._meta_path(conversation_id).write_text(
            meta.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def read_transcript(self, conversation_id: str) -> str:
        self.validate_id(conversation_id)
        path = self._txt_path(conversation_id)
        if not path.exists():
            raise FileNotFoundError(f"Conversation {conversation_id} not found")
        return path.read_text(encoding="utf-8")

    def parse_messages(self, transcript: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        blocks = re.split(r"=== turn \d+ .*? ===\n", transcript)
        role_pattern = re.compile(r"\[(user|assistant|system)\]\n", re.MULTILINE)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            matches = list(role_pattern.finditer(block))
            for i, match in enumerate(matches):
                role = match.group(1)
                start = match.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
                content = block[start:end].strip()
                if content:
                    messages.append({"role": role, "content": content})
        return messages

    def append_turn(
        self,
        conversation_id: str,
        *,
        user_content: str,
        assistant_content: str,
        tier: str,
        model: str,
        cost_usd: float,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> ConversationMeta:
        self.validate_id(conversation_id)
        lock = FileLock(str(self._lock_path(conversation_id)))
        with lock:
            meta = self.get_meta(conversation_id)
            turn = meta.turn_count + 1
            now = _utc_now()
            header = f"=== turn {turn} | {now} | tier={tier} | model={model} ===\n"
            block = (
                f"{header}[user]\n{user_content}\n\n"
                f"[assistant]\n{assistant_content}\n\n"
            )
            txt_path = self._txt_path(conversation_id)
            with txt_path.open("a", encoding="utf-8") as f:
                f.write(block)

            meta.turn_count = turn
            meta.updated_at = now
            meta.total_cost_usd = round(meta.total_cost_usd + cost_usd, 8)
            meta.total_prompt_tokens += prompt_tokens
            meta.total_completion_tokens += completion_tokens
            meta.last_tier = tier
            meta.last_model = model
            self._write_meta(conversation_id, meta)
            return meta

    def list_conversations(self) -> list[ConversationMeta]:
        results: list[ConversationMeta] = []
        for path in sorted(self.base.glob("*.meta.json")):
            results.append(
                ConversationMeta.model_validate_json(path.read_text(encoding="utf-8"))
            )
        return results

    def get_detail(self, conversation_id: str) -> tuple[ConversationMeta, str, list[dict[str, str]]]:
        meta = self.get_meta(conversation_id)
        transcript = self.read_transcript(conversation_id)
        messages = self.parse_messages(transcript)
        return meta, transcript, messages
