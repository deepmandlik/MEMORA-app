from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .config import ProviderSettings
from .extraction import valid_llm_memories

CODE_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.IGNORECASE | re.DOTALL)


def parse_model_content(content: str) -> tuple[str, list[dict[str, str]]]:
    stripped = content.strip()
    fenced = CODE_FENCE.match(stripped)
    candidate = fenced.group(1) if fenced else stripped
    try:
        payload = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return stripped, []
    if not isinstance(payload, dict):
        return stripped, []
    response = payload.get("response")
    if not isinstance(response, str) or not response.strip():
        response = stripped
    return response.strip(), valid_llm_memories(payload.get("memories"))


async def call_chat_completions(
    provider: ProviderSettings,
    message: str,
    memories: list[dict[str, Any]],
) -> tuple[str, list[dict[str, str]]]:
    context = [
        {
            "memory_key": memory.get("memory_key"),
            "category": memory["category"],
            "content": memory["content"],
        }
        for memory in memories
    ]
    system = (
        "You are Memora, a continuity assistant. Use only relevant supplied memories and the user's "
        "message; do not invent personal facts. Return exactly one valid JSON object with this shape: "
        '{"response":"helpful answer","memories":[{"content":"durable fact",'
        '"category":"career","memory_key":"career.example"}]}. '
        "The memories array must contain only new enduring facts explicitly stated by the user, never "
        "questions, temporary states, or facts merely repeated in the prompt. Use an empty array when "
        "nothing new should be saved. Prefer this existing context over generic assumptions.\n"
        f"Retrieved memories:\n{json.dumps(context, ensure_ascii=False)}"
    )
    async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
        response = await client.post(
            provider.endpoint,
            headers={
                "Authorization": f"Bearer {provider.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": provider.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
                "temperature": 0.2,
            },
        )
        response.raise_for_status()
        body = response.json()

    content = body["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Provider returned an empty chat completion")
    return parse_model_content(content)
