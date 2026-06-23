"""
PyRIT environment helper for adversarial OpenAI target (scorer + attack LLM).

The LiteLLM Render endpoint does NOT need these keys.
These are only for PyRIT's OpenAIChatTarget (adversarial model + scorer).

Set via environment variables OR pass CLI flags to pyrit_redteam_attack.py.

Required:
  OPENAI_CHAT_KEY
  OPENAI_CHAT_MODEL

Optional:
  OPENAI_CHAT_ENDPOINT  (default: https://api.openai.com/v1/chat/completions)
"""

from __future__ import annotations

import os
import sys

from pyrit.prompt_target import OpenAIChatTarget

REQUIRED_VARS = ("OPENAI_CHAT_KEY", "OPENAI_CHAT_MODEL")
DEFAULT_ENDPOINT = "https://api.openai.com/v1/chat/completions"


def _missing_env() -> list[str]:
    return [name for name in REQUIRED_VARS if not os.getenv(name)]


def build_openai_adversarial_target(
    *,
    model_name: str | None = None,
    api_key: str | None = None,
    endpoint: str | None = None,
) -> OpenAIChatTarget:
    """
    Build OpenAIChatTarget from CLI args or environment variables.

    CLI args override env when provided.
    """
    resolved_model = model_name or os.getenv("OPENAI_CHAT_MODEL")
    resolved_key = api_key or os.getenv("OPENAI_CHAT_KEY")
    resolved_endpoint = endpoint or os.getenv("OPENAI_CHAT_ENDPOINT", DEFAULT_ENDPOINT)

    missing = []
    if not resolved_model:
        missing.append("OPENAI_CHAT_MODEL (or --adversarial-model)")
    if not resolved_key:
        missing.append("OPENAI_CHAT_KEY (or --adversarial-key)")

    if missing:
        print("PyRIT adversarial OpenAI target is not configured.", file=sys.stderr)
        print("Set these environment variables (e.g. in ~/.pyrit/.env):", file=sys.stderr)
        print("  OPENAI_CHAT_KEY=sk-...", file=sys.stderr)
        print("  OPENAI_CHAT_MODEL=gpt-4o", file=sys.stderr)
        print("  OPENAI_CHAT_ENDPOINT=https://api.openai.com/v1/chat/completions  (optional)", file=sys.stderr)
        print("", file=sys.stderr)
        print("Or pass CLI flags:", file=sys.stderr)
        print("  --adversarial-key sk-... --adversarial-model gpt-4o", file=sys.stderr)
        print("", file=sys.stderr)
        print(f"Missing: {', '.join(missing)}", file=sys.stderr)
        raise SystemExit(1)

    return OpenAIChatTarget(
        model_name=resolved_model,
        api_key=resolved_key,
        endpoint=resolved_endpoint,
    )
