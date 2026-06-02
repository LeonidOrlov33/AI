from __future__ import annotations

import os
from pathlib import Path

from .llm import DEEPSEEK_MODEL, GEMINI_MODEL, QWEN_MODEL
from .models import AgentConfig


def load_config(workspace: str | Path | None = None) -> AgentConfig:
    return AgentConfig(
        workspace=Path(workspace or os.getenv("AUTOCODER_WORKSPACE") or Path.cwd() / "generated_project"),
        max_fix_attempts=int(os.getenv("AUTOCODER_MAX_FIX_ATTEMPTS", "5")),
        gemini_model=GEMINI_MODEL,
        deepseek_model=DEEPSEEK_MODEL,
        qwen_model=QWEN_MODEL,
        render_api_key=os.getenv("RENDER_API_KEY") or None,
        render_owner_id=os.getenv("RENDER_OWNER_ID") or None,
        render_service_name=os.getenv("RENDER_SERVICE_NAME", "autocoder-generated-app"),
        render_region=os.getenv("RENDER_REGION", "oregon"),
        render_plan=os.getenv("RENDER_PLAN", "free"),
    )
