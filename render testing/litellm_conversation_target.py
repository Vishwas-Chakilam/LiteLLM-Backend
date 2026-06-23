"""
LiteLLM Conversation-Aware PyRIT Target
=======================================

Custom PromptTarget for:
  POST https://litellm-chat-api.onrender.com/v1/chat/completions

Why this exists:
  Plain HTTPTarget cannot parse conversation_id from a response and re-inject
  it into the next request body. This target stores the server-returned
  conversation_id after each turn so multi-turn PyRIT attacks work correctly.

Tester setup:
  pip install pyrit httpx
  Configure OpenAI (or other) credentials for the adversarial model + scorer
  in ~/.pyrit/.env — see pyrit_redteam_attack.py

Usage:
  from litellm_conversation_target import LiteLLMConversationTarget

  target = LiteLLMConversationTarget(
      url="https://litellm-chat-api.onrender.com/v1/chat/completions",
      model="fast",
  )
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from pyrit.models import Message, MessagePiece
from pyrit.prompt_target import PromptTarget

logger = logging.getLogger(__name__)

DEFAULT_URL = "https://litellm-chat-api.onrender.com/v1/chat/completions"
DEFAULT_TIMEOUT = 120.0  # Render free tier cold starts can be slow


class LiteLLMConversationTarget(PromptTarget):
    """
    PyRIT target for the LiteLLM BankAssist / chat API with multi-turn memory.

    - Turn 1: omits conversation_id (server creates one)
    - Turn 2+: sends stored conversation_id from previous response
    - Returns assistant text from choices[0].message.content
    """

    def __init__(
        self,
        *,
        url: str = DEFAULT_URL,
        model: str = "fast",
        timeout: float = DEFAULT_TIMEOUT,
        max_requests_per_minute: Optional[int] = None,
    ) -> None:
        super().__init__(max_requests_per_minute=max_requests_per_minute)
        self._url = url.rstrip("/")
        if not self._url.endswith("/v1/chat/completions"):
            # Allow base URL like https://host — append path if missing
            if self._url.endswith("/"):
                self._url = self._url + "v1/chat/completions"
            else:
                self._url = self._url + "/v1/chat/completions"

        self._model = model
        self._timeout = timeout
        self._litellm_conversation_id: str | None = None

    @property
    def conversation_id(self) -> str | None:
        """Server-side conversation UUID (for debugging / logging)."""
        return self._litellm_conversation_id

    def reset_conversation(self) -> None:
        """Start a fresh server conversation on the next prompt."""
        self._litellm_conversation_id = None

    # PyRIT >= 0.14: override internal hook used by send_prompt_async
    async def _send_prompt_to_target_async(self, *, message: Message) -> list[Message]:
        user_text = self._extract_user_text(message)
        reply_text, meta = await self._call_litellm(user_text)

        logger.info(
            "LiteLLM reply | conv=%s | tier=%s | model=%s",
            meta.get("conversation_id"),
            meta.get("tier"),
            meta.get("model_used"),
        )

        response_piece = MessagePiece(
            role="assistant",
            original_value=reply_text,
        )
        # Preserve conversation linkage in PyRIT memory if available
        if message.message_pieces:
            response_piece.conversation_id = message.message_pieces[0].conversation_id
            response_piece.prompt_target_identifier = message.message_pieces[0].prompt_target_identifier

        return [Message(message_pieces=[response_piece])]

    def _extract_user_text(self, message: Message) -> str:
        if not message.message_pieces:
            raise ValueError("Empty message — no prompt to send.")

        # Use converted_value (after PyRIT converters) or fall back to original
        piece = message.message_pieces[-1]
        text = piece.converted_value or piece.original_value
        if not text or not str(text).strip():
            raise ValueError("User prompt text is empty.")
        return str(text).strip()

    async def _call_litellm(self, user_text: str) -> tuple[str, dict[str, Any]]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": user_text}],
            "stream": False,
        }
        if self._litellm_conversation_id:
            payload["conversation_id"] = self._litellm_conversation_id

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._url, json=payload)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"LiteLLM API error {response.status_code}: {response.text[:500]}"
                )
            data = response.json()

        # Store server conversation id for next turn
        self._litellm_conversation_id = data.get("conversation_id", self._litellm_conversation_id)

        try:
            reply = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LiteLLM response shape: {data}") from exc

        if not reply:
            raise RuntimeError("LiteLLM returned empty assistant content.")

        meta = {
            "conversation_id": data.get("conversation_id"),
            "tier": data.get("tier"),
            "model_used": data.get("model_used"),
            "estimated_cost_usd": data.get("estimated_cost_usd"),
        }
        return str(reply), meta
