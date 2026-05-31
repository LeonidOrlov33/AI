from __future__ import annotations

import asyncio
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from .llm import OpenRouterClient, extract_json
from .models import AgentConfig, ChatMessage, ProjectSpec, TestIssue, TestReport
from .specialists import TESTER_SYSTEM
from .workspace import Workspace


class Tester:
    def __init__(self, llm: OpenRouterClient, model: str, config: AgentConfig) -> None:
        self.llm = llm
        self.model = model
        self.config = config

    async def analyze(self, workspace: Workspace, spec: ProjectSpec) -> list[TestIssue]:
        if not self.llm.available:
            return []
        prompt = f"ТЗ:\n{spec.model_dump_json(indent=2)}\n\nКод:\n{workspace.snapshot()}"
        content = await self.llm.chat(
            self.model,
            [ChatMessage(role="system", content=TESTER_SYSTEM), ChatMessage(role="user", content=prompt)],
            json_mode=True,
        )
        data = extract_json(content)
        return [TestIssue.model_validate(issue) for issue in data.get("issues", [])]

    def run_local_checks(self, workspace: Workspace, spec: ProjectSpec) -> TestReport:
        logs: list[str] = []
        issues: list[TestIssue] = []
        commands = spec.test_commands or ["python -m pytest"]
        for command in commands:
            if command.strip().startswith("playwright") and not shutil.which("playwright"):
                logs.append(f"SKIP {command}: playwright is not installed")
                continue
            try:
                code, output = workspace.run(command, timeout=180)
            except Exception as exc:  # subprocess timeout and OS errors are runtime test failures
                code, output = 1, repr(exc)
            logs.append(f"$ {command}\n{output}")
            if code != 0:
                issues.append(TestIssue(severity="high", description="Command failed", command=command, output=output[-4000:]))
        return TestReport(success=not issues, issues=issues, logs="\n\n".join(logs))

    async def deploy_render(self, workspace: Workspace) -> tuple[str | None, str]:
        if not self.config.render_api_key or not self.config.render_owner_id:
            return None, "Render deployment skipped: RENDER_API_KEY or RENDER_OWNER_ID is not configured."
        blueprint = self._ensure_render_files(workspace.root)
        payload = {
            "type": "web_service",
            "name": self.config.render_service_name,
            "ownerId": self.config.render_owner_id,
            "repo": "manual/local-upload-required",
            "branch": "main",
            "serviceDetails": {
                "env": "python",
                "region": self.config.render_region,
                "plan": self.config.render_plan,
                "buildCommand": "pip install -e .",
                "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
            },
        }
        try:
            data = await asyncio.to_thread(self._post_json, "https://api.render.com/v1/services", payload, self.config.render_api_key)
        except RuntimeError as exc:
            return None, f"Render API error: {exc}\nBlueprint: {blueprint}"
        url = data.get("service", {}).get("serviceDetails", {}).get("url") or data.get("service", {}).get("url")
        return url, "Render deployment request created."

    def _ensure_render_files(self, root: Path) -> Path:
        render_yaml = root / "render.yaml"
        if not render_yaml.exists():
            render_yaml.write_text(
                f"""services:\n  - type: web\n    name: {self.config.render_service_name}\n    env: python\n    plan: {self.config.render_plan}\n    buildCommand: pip install -e .\n    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT\n""",
                encoding="utf-8",
            )
        return render_yaml

    async def verify_deployed(self, url: str | None, spec: ProjectSpec) -> str:
        if not url:
            return "No deployed URL to verify."
        checks = [endpoint.path for endpoint in spec.endpoints if endpoint.method.upper() == "GET"] or ["/health"]
        logs: list[str] = []
        for path in checks:
            status = await asyncio.to_thread(self._get_status, url.rstrip("/") + path)
            logs.append(f"GET {path}: {status}")
        return "\n".join(logs)

    def _post_json(self, url: str, payload: dict, api_key: str | None) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{exc.code}: {exc.read().decode('utf-8', errors='replace')[:1000]}") from exc

    def _get_status(self, url: str) -> int:
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code
