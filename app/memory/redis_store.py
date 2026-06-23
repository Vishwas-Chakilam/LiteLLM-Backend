from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]


class RedisSessionStore:
    """Short-term session and workflow state memory."""

    def __init__(self) -> None:
        settings = get_settings()
        self._ttl = settings.redis_session_ttl_seconds
        self._client: Any = None
        if redis is not None:
            try:
                self._client = redis.from_url(settings.redis_url, decode_responses=True)
                self._client.ping()
            except Exception as exc:
                logger.warning("Redis unavailable, using in-memory fallback: %s", exc)
                self._client = None
        self._memory: dict[str, str] = {}

    @property
    def available(self) -> bool:
        return self._client is not None

    def _key(self, namespace: str, session_id: str) -> str:
        return f"healthcare:{namespace}:{session_id}"

    def set(self, namespace: str, session_id: str, data: dict[str, Any]) -> None:
        key = self._key(namespace, session_id)
        payload = json.dumps(data)
        if self._client:
            self._client.setex(key, self._ttl, payload)
        else:
            self._memory[key] = payload

    def get(self, namespace: str, session_id: str) -> dict[str, Any] | None:
        key = self._key(namespace, session_id)
        if self._client:
            raw = self._client.get(key)
        else:
            raw = self._memory.get(key)
        if not raw:
            return None
        return json.loads(raw)

    def append_history(self, session_id: str, role: str, content: str) -> list[dict[str, str]]:
        state = self.get("session", session_id) or {"history": []}
        state["history"].append({"role": role, "content": content})
        self.set("session", session_id, state)
        return state["history"]

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        state = self.get("session", session_id)
        return state.get("history", []) if state else []

    def set_workflow_state(self, workflow_id: str, state: dict[str, Any]) -> None:
        self.set("workflow", workflow_id, state)

    def get_workflow_state(self, workflow_id: str) -> dict[str, Any] | None:
        return self.get("workflow", workflow_id)


@lru_cache
def get_session_store() -> RedisSessionStore:
    return RedisSessionStore()
