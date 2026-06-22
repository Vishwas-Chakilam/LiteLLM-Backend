"""
Smoke tests for the Render deployment of LiteLLM Chat API.

Usage:
    pip install -r requirements.txt
    python test_render_api.py
"""

from __future__ import annotations

import json
import sys
import time

import httpx

BASE_URL = "https://litellm-chat-api.onrender.com"
TIMEOUT = 120.0  # Render free tier cold starts can be slow


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(title)
    print("=" * 60)


def ok(label: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"  [PASS] {label}{suffix}")


def fail(label: str, detail: str) -> None:
    print(f"  [FAIL] {label} — {detail}")


def main() -> int:
    section(f"Testing {BASE_URL}")
    failures = 0
    conversation_id: str | None = None

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        # 1. Root
        section("GET /")
        try:
            r = client.get("/")
            r.raise_for_status()
            data = r.json()
            if data.get("message"):
                ok("root", json.dumps(data))
            else:
                failures += 1
                fail("root", f"unexpected body: {data}")
        except Exception as exc:
            failures += 1
            fail("root", str(exc))

        # 2. Health
        section("GET /health")
        try:
            r = client.get("/health")
            r.raise_for_status()
            if r.json().get("status") == "ok":
                ok("health", r.json()["status"])
            else:
                failures += 1
                fail("health", str(r.json()))
        except Exception as exc:
            failures += 1
            fail("health", str(exc))

        # 3. Create conversation
        section("POST /v1/conversations")
        try:
            r = client.post("/v1/conversations")
            r.raise_for_status()
            data = r.json()
            conversation_id = data.get("conversation_id")
            if conversation_id:
                ok("create conversation", conversation_id)
            else:
                failures += 1
                fail("create conversation", "no conversation_id")
        except Exception as exc:
            failures += 1
            fail("create conversation", str(exc))

        # 4. Chat completion (may cold-start)
        section("POST /v1/chat/completions")
        print("  (first chat may take 30-60s on free tier cold start...)")
        t0 = time.time()
        try:
            payload = {
                "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
                "model": "fast",
            }
            if conversation_id:
                payload["conversation_id"] = conversation_id

            r = client.post("/v1/chat/completions", json=payload)
            elapsed = time.time() - t0
            if r.status_code != 200:
                failures += 1
                fail("chat", f"HTTP {r.status_code}: {r.text[:500]}")
            else:
                data = r.json()
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                conversation_id = data.get("conversation_id", conversation_id)
                if reply:
                    ok("chat", f"{elapsed:.1f}s | tier={data.get('tier')} | model={data.get('model_used')}")
                    print(f"  Reply: {reply[:200]}")
                else:
                    failures += 1
                    fail("chat", "empty assistant content")
        except Exception as exc:
            failures += 1
            fail("chat", str(exc))

        # 5. Multi-turn
        if conversation_id:
            section("POST /v1/chat/completions (turn 2)")
            try:
                r = client.post(
                    "/v1/chat/completions",
                    json={
                        "conversation_id": conversation_id,
                        "messages": [{"role": "user", "content": "What was my first message about?"}],
                        "model": "fast",
                    },
                )
                r.raise_for_status()
                reply = r.json()["choices"][0]["message"]["content"]
                ok("multi-turn", reply[:120])
            except Exception as exc:
                failures += 1
                fail("multi-turn", str(exc))

        # 6. Conversation history
        if conversation_id:
            section(f"GET /v1/conversations/{conversation_id}")
            try:
                r = client.get(f"/v1/conversations/{conversation_id}")
                r.raise_for_status()
                data = r.json()
                turns = data.get("meta", {}).get("turn_count", 0)
                msgs = len(data.get("messages", []))
                ok("history", f"turn_count={turns}, messages={msgs}")
            except Exception as exc:
                failures += 1
                fail("history", str(exc))

        # 7. List conversations
        section("GET /v1/conversations")
        try:
            r = client.get("/v1/conversations")
            r.raise_for_status()
            ok("list", f"{len(r.json())} conversation(s)")
        except Exception as exc:
            failures += 1
            fail("list", str(exc))

        # 8. Admin cost
        section("GET /v1/admin/cost")
        try:
            r = client.get("/v1/admin/cost")
            r.raise_for_status()
            data = r.json()
            ok("cost", f"daily=${data.get('daily_spend_usd', 0):.6f} / ${data.get('daily_budget_usd', 0)}")
        except Exception as exc:
            failures += 1
            fail("admin cost", str(exc))

    section("Summary")
    if failures:
        print(f"  {failures} test(s) FAILED")
        return 1
    print("  All tests PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
