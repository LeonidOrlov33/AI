from __future__ import annotations

import os
from pathlib import Path

from .models import AgentConfig


def _load_dotenv() -> None:
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(workspace: str | Path | None = None) -> AgentConfig:
    _load_dotenv()
    return AgentConfig(
        workspace=Path(workspace or os.getenv("AUTOCODER_WORKSPACE") or Path.cwd() / "generated_project"),
        max_fix_attempts=int(os.getenv("AUTOCODER_MAX_FIX_ATTEMPTS", "5")),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        gemini_model=os.getenv("GEMINI_MODEL", "google/gemini-2.5-pro"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-r1-671b"),
        qwen_model=os.getenv("QWEN_MODEL", "qwen/qwen3-235b-a22b-thinking-2507"),
        render_api_key=os.getenv("RENDER_API_KEY") or None,
        render_owner_id=os.getenv("RENDER_OWNER_ID") or None,
        render_service_name=os.getenv("RENDER_SERVICE_NAME", "autocoder-generated-app"),
        render_region=os.getenv("RENDER_REGION", "oregon"),
        render_plan=os.getenv("RENDER_PLAN", "free"),
    )
