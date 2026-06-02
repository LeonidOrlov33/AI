from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from .models import ChatMessage

# Google AI Studio (Gemini, OpenAI-compatible endpoint).
# Do not commit real secrets here. Paste local keys only in a private copy if you
# intentionally want hardcoded credentials on your own computer.
GEMINI_API_KEY = "PASTE_GEMINI_API_KEY_HERE"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_MODEL = "gemini-2.5-pro"

# Ollama Cloud (DeepSeek + Qwen).
# Do not commit real secrets here. Paste local keys only in a private copy if you
# intentionally want hardcoded credentials on your own computer.
OLLAMA_API_KEY = "PASTE_OLLAMA_API_KEY_HERE"
OLLAMA_BASE_URL = "https://ollama.com/api"
DEEPSEEK_MODEL = "deepseek-v3.1:671b-cloud"
QWEN_MODEL = "qwen3.5:397b-cloud"

_PLACEHOLDERS = {"", "PASTE_GEMINI_API_KEY_HERE", "PASTE_OLLAMA_API_KEY_HERE"}


class LLMError(RuntimeError):
    pass


def _messages_payload(messages: Sequence[ChatMessage | dict[str, str]]) -> list[dict[str, str]]:
    return [m.model_dump() if isinstance(m, ChatMessage) else dict(m) for m in messages]


def _has_real_keys() -> bool:
    return GEMINI_API_KEY not in _PLACEHOLDERS and OLLAMA_API_KEY not in _PLACEHOLDERS


async def call_gemini(messages: Sequence[ChatMessage | dict[str, str]]) -> str:
    if GEMINI_API_KEY in _PLACEHOLDERS:
        raise LLMError("GEMINI_API_KEY is not configured in autocoder_agent.core.llm")
    try:
        import openai
    except ImportError as exc:
        raise LLMError("Install OpenAI client first: python -m pip install openai") from exc

    client = openai.AsyncOpenAI(api_key=GEMINI_API_KEY, base_url=GEMINI_BASE_URL)
    response = await client.chat.completions.create(model=GEMINI_MODEL, messages=_messages_payload(messages))
    return response.choices[0].message.content or ""


async def call_ollama(model: str, messages: Sequence[ChatMessage | dict[str, str]]) -> str:
    if OLLAMA_API_KEY in _PLACEHOLDERS:
        raise LLMError("OLLAMA_API_KEY is not configured in autocoder_agent.core.llm")
    try:
        import httpx
    except ImportError as exc:
        raise LLMError("Install httpx first: python -m pip install httpx") from exc

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/chat",
            json={"model": model, "messages": _messages_payload(messages), "stream": False},
            headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
        )
    response.raise_for_status()
    return response.json()["message"]["content"]


async def interview(messages: Sequence[ChatMessage | dict[str, str]]) -> str:
    return await call_gemini(messages)


async def generate_code(messages: Sequence[ChatMessage | dict[str, str]]) -> str:
    return await call_ollama(DEEPSEEK_MODEL, messages)


async def test_code(messages: Sequence[ChatMessage | dict[str, str]]) -> str:
    return await call_ollama(QWEN_MODEL, messages)


class ProviderRouter:
    """Routes specialist calls to the requested hardcoded provider/model."""

    @property
    def available(self) -> bool:
        return _has_real_keys()

    async def chat(self, model: str, messages: Sequence[ChatMessage | dict[str, str]], *, json_mode: bool = False) -> str:
        if model == GEMINI_MODEL:
            return await interview(messages)
        if model == DEEPSEEK_MODEL:
            return await generate_code(messages)
        if model == QWEN_MODEL:
            return await test_code(messages)
        raise LLMError(f"Unknown hardcoded model route: {model}")


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
