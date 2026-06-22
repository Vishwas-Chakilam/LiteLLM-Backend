#!/usr/bin/env python3
"""
Interactive CLI chat against LiteLLM Chat API.

Usage:
    pip install -r requirements.txt
    python chat_cli.py
    python chat_cli.py --url http://127.0.0.1:8000
    python chat_cli.py --url https://litellm-chat-api.onrender.com --model fast
"""

from __future__ import annotations

import argparse
import sys

import httpx

DEFAULT_URL = "https://litellm-chat-api.onrender.com"
TIMEOUT = 120.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Interactive chat CLI for LiteLLM API")
    p.add_argument("--url", default=DEFAULT_URL, help="API base URL")
    p.add_argument("--model", default="fast", choices=["fast", "capable", "auto"])
    p.add_argument("--conversation-id", default=None, help="Resume existing conversation")
    return p.parse_args()


def chat(client: httpx.Client, conversation_id: str | None, model: str, text: str) -> tuple[str, str]:
    payload: dict = {
        "messages": [{"role": "user", "content": text}],
        "model": model,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    r = client.post("/v1/chat/completions", json=payload)
    r.raise_for_status()
    data = r.json()
    reply = data["choices"][0]["message"]["content"]
    conv_id = data["conversation_id"]
    tier = data.get("tier", "?")
    used = data.get("model_used", "?")
    cost = data.get("estimated_cost_usd", 0)
    meta = f"[tier={tier} | {used} | ${cost:.6f}]"
    return reply, conv_id, meta


def main() -> int:
    args = parse_args()
    base = args.url.rstrip("/")
    conversation_id = args.conversation_id

    print(f"LiteLLM Chat CLI")
    print(f"URL: {base}")
    print(f"Model: {args.model}")
    print("Commands: /quit /exit  /new  /id  /history")
    print("-" * 50)

    try:
        with httpx.Client(base_url=base, timeout=TIMEOUT) as client:
            # Warm up / health check
            try:
                health = client.get("/health").json()
                print(f"Connected (health={health.get('status', '?')})\n")
            except httpx.HTTPError as exc:
                print(f"Warning: health check failed: {exc}\n")

            while True:
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nBye.")
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
                    print("Bye.")
                    break
                if user_input.lower() == "/new":
                    conversation_id = None
                    print("Started new conversation.\n")
                    continue
                if user_input.lower() == "/id":
                    print(f"conversation_id: {conversation_id or '(none yet)'}\n")
                    continue
                if user_input.lower() == "/history" and conversation_id:
                    try:
                        r = client.get(f"/v1/conversations/{conversation_id}")
                        r.raise_for_status()
                        data = r.json()
                        print(f"Turns: {data['meta']['turn_count']}")
                        for m in data["messages"]:
                            print(f"  [{m['role']}] {m['content'][:200]}")
                        print()
                    except httpx.HTTPError as exc:
                        print(f"History error: {exc}\n")
                    continue

                try:
                    print("Thinking...", flush=True)
                    reply, conversation_id, meta = chat(
                        client, conversation_id, args.model, user_input
                    )
                    print(f"Bot: {reply}")
                    print(f"      {meta}\n")
                except httpx.HTTPStatusError as exc:
                    print(f"Error {exc.response.status_code}: {exc.response.text[:300]}\n")
                except httpx.HTTPError as exc:
                    print(f"Request failed: {exc}\n")

    except httpx.HTTPError as exc:
        print(f"Could not connect to {base}: {exc}", file=sys.stderr)
        return 1

    if conversation_id:
        print(f"Last conversation_id: {conversation_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
