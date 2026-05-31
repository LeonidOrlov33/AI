from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any

from .models import ChatMessage


class LLMError(RuntimeError):
    pass


class OpenRouterClient:
    """Small OpenAI/OpenRouter-compatible chat client used by all specialists."""

    def __init__(self, *, api_key: str | None, base_url: str, timeout: float = 120.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def chat(self, model: str, messages: Sequence[ChatMessage | dict[str, str]], *, json_mode: bool = False) -> str:
        return await asyncio.to_thread(self._chat_sync, model, messages, json_mode)

    def _chat_sync(self, model: str, messages: Sequence[ChatMessage | dict[str, str]], json_mode: bool) -> str:
        if not self.api_key:
            raise LLMError("API key is not configured. Set OPENROUTER_API_KEY or provide a compatible provider.")
        payload: dict[str, Any] = {
            "model": model,
            "messages": [m.model_dump() if isinstance(m, ChatMessage) else m for m in messages],
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/autocoder-agent/local",
                "X-Title": "Autocoder Agent",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc.code} {exc.read().decode('utf-8', errors='replace')[:1000]}") from exc
        return data["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(stripped[start : end + 1])
