from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_conversation_without_auth(client):
    resp = client.post("/v1/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert "conversation_id" in data
    assert "created_at" in data


def test_list_conversations(client):
    client.post("/v1/conversations")
    resp = client.get("/v1/conversations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


def test_get_conversation_not_found(client):
    resp = client.get("/v1/conversations/00000000-0000-0000-0000-000000000099")
    assert resp.status_code == 404


def test_get_conversation_after_create(client):
    create = client.post("/v1/conversations").json()
    conv_id = create["conversation_id"]
    resp = client.get(f"/v1/conversations/{conv_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"] == conv_id
    assert data["meta"]["turn_count"] == 0


@patch("app.main.get_router_service")
def test_chat_completions_mock(mock_get_router, client):
    mock_router = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello from assistant"
    mock_response.usage.prompt_tokens = 8
    mock_response.usage.completion_tokens = 4
    mock_response.model = "gpt-4o-mini"
    mock_router.completion.return_value = mock_response
    mock_router.extract_content.return_value = "Hello from assistant"
    mock_router.extract_usage.return_value = (8, 4, 0.0001, "gpt-4o-mini")
    mock_get_router.return_value = mock_router

    resp = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "fast",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "Hello from assistant"
    assert "conversation_id" in data
    assert data["tier"] == "fast"

    conv_id = data["conversation_id"]
    detail = client.get(f"/v1/conversations/{conv_id}")
    assert detail.status_code == 200
    assert detail.json()["meta"]["turn_count"] == 1
    assert len(detail.json()["messages"]) == 2


@patch("app.main.get_router_service")
def test_chat_multi_turn(mock_get_router, client):
    mock_router = MagicMock()
    mock_router.extract_content.side_effect = ["First reply", "Second reply"]
    mock_router.extract_usage.return_value = (5, 3, 0.0001, "gpt-4o-mini")

    def make_response(text):
        r = MagicMock()
        r.choices = [MagicMock()]
        r.choices[0].message.content = text
        r.usage.prompt_tokens = 5
        r.usage.completion_tokens = 3
        r.model = "gpt-4o-mini"
        return r

    mock_router.completion.side_effect = [
        make_response("First reply"),
        make_response("Second reply"),
    ]
    mock_get_router.return_value = mock_router

    first = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "Turn 1"}]},
    ).json()
    conv_id = first["conversation_id"]

    second = client.post(
        "/v1/chat/completions",
        json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "Turn 2"}],
        },
    )
    assert second.status_code == 200
    assert second.json()["choices"][0]["message"]["content"] == "Second reply"

    detail = client.get(f"/v1/conversations/{conv_id}").json()
    assert detail["meta"]["turn_count"] == 2
    user_msgs = [m for m in detail["messages"] if m["role"] == "user"]
    assert user_msgs[0]["content"] == "Turn 1"
    assert user_msgs[1]["content"] == "Turn 2"


@patch("app.main.get_router_service")
def test_admin_cost(mock_get_router, client):
    mock_router = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "ok"
    mock_response.usage.prompt_tokens = 1
    mock_response.usage.completion_tokens = 1
    mock_response.model = "gpt-4o-mini"
    mock_router.completion.return_value = mock_response
    mock_router.extract_content.return_value = "ok"
    mock_router.extract_usage.return_value = (1, 1, 0.05, "gpt-4o-mini")
    mock_get_router.return_value = mock_router

    client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "cost test"}]},
    )

    resp = client.get("/v1/admin/cost")
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_count"] >= 1
    assert "daily_spend_usd" in data


def test_stream_not_supported(client):
    resp = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
        },
    )
    assert resp.status_code == 400
