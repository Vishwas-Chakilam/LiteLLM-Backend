import requests

conversation_id = None

def call_chat(prompt: str) -> tuple[str, str]:
    global conversation_id

    payload = {
        "model": "fast",
        "messages": [{"role": "user", "content": prompt}],
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    response = requests.post(
        "https://litellm-chat-api.onrender.com/v1/chat/completions",
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    conversation_id = data["conversation_id"]
    reply = data["choices"][0]["message"]["content"]
    return reply, conversation_id


if __name__ == "__main__":
    reply, conv_id = call_chat("Hello, how are you?")
    print(reply)
    print(f"conversation_id: {conv_id}")

    reply2, conv_id = call_chat("What did I just ask?")
    print(reply2)