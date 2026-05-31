from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import time
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

    def verify_local_endpoints(self, workspace: Workspace, spec: ProjectSpec) -> TestReport:
        """Start the generated app and exercise every declared endpoint method."""
        endpoints = list(spec.endpoints)
        if not endpoints:
            return TestReport(success=True, logs="Endpoint check skipped: no endpoints declared in spec.")
        if not spec.run_commands:
            return TestReport(
                success=False,
                issues=[TestIssue(severity="high", description="Endpoint check requires at least one run command")],
                logs="Endpoint check failed: no run_commands in spec.",
            )

        command = spec.run_commands[0]
        base_url = os.getenv("AUTOCODER_TEST_BASE_URL") or self._guess_base_url(command)
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        process = subprocess.Popen(
            command,
            cwd=workspace.root,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        logs = [f"$ {command}", f"Endpoint base URL: {base_url}"]
        issues: list[TestIssue] = []
        try:
            if not self._wait_for_server(base_url, endpoints):
                output = self._collect_process_output(process)
                return TestReport(
                    success=False,
                    issues=[TestIssue(severity="high", description="Generated app did not become reachable", command=command, output=output)],
                    logs="\n".join(logs + [output]),
                )
            created_id: int | str | None = None
            for endpoint in endpoints:
                method = endpoint.method.upper()
                path = self._path_with_id(endpoint.path, created_id)
                payload = self._payload_for_method(method)
                status, body = self._request_json(base_url + path, method, payload)
                logs.append(f"{method} {path}: {status} {body[:300]}")
                if status >= 400:
                    issues.append(TestIssue(severity="high", description=f"Endpoint returned HTTP {status}", command=f"{method} {path}", output=body))
                if method == "POST" and status < 400:
                    created_id = self._extract_id(body) or created_id
        finally:
            self._stop_process(process)
            tail = self._collect_process_output(process)
            if tail:
                logs.append("Server output:\n" + tail)
        return TestReport(success=not issues, issues=issues, logs="\n".join(logs))

    def run_playwright_smoke(self, workspace: Workspace, spec: ProjectSpec) -> TestReport:
        if importlib.util.find_spec("playwright") is None:
            return TestReport(success=True, logs="Playwright browser smoke skipped: python playwright package is not installed.")
        html_files = [path for path in workspace.list_files() if path.endswith((".html", ".htm"))]
        has_ui_hint = html_files or any(part.lower().endswith((".tsx", ".jsx", ".vue", ".svelte")) for part in workspace.list_files())
        if not has_ui_hint:
            return TestReport(success=True, logs="Playwright browser smoke skipped: no obvious browser UI files were generated.")
        if not spec.run_commands:
            return TestReport(
                success=False,
                issues=[TestIssue(severity="high", description="Playwright smoke requires at least one run command")],
                logs="Playwright browser smoke failed: no run_commands in spec.",
            )

        command = spec.run_commands[0]
        base_url = os.getenv("AUTOCODER_TEST_BASE_URL") or self._guess_base_url(command)
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        process = subprocess.Popen(
            command,
            cwd=workspace.root,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        logs = [f"$ {command}", f"Playwright base URL: {base_url}"]
        try:
            if not self._wait_for_server(base_url, list(spec.endpoints)):
                return TestReport(
                    success=False,
                    issues=[TestIssue(severity="high", description="Generated UI app did not become reachable", command=command)],
                    logs="\n".join(logs),
                )
            code, output = self._run_playwright_script(workspace, base_url)
            logs.append(output)
            if code != 0:
                return TestReport(
                    success=False,
                    issues=[TestIssue(severity="high", description="Playwright browser smoke failed", command="python -c <playwright smoke>", output=output[-4000:])],
                    logs="\n".join(logs),
                )
            return TestReport(success=True, logs="\n".join(logs))
        finally:
            self._stop_process(process)


    async def deploy_render(self, workspace: Workspace, spec: ProjectSpec) -> tuple[str | None, str]:
        blueprint = self._ensure_render_files(workspace.root, spec)
        if not self.config.render_api_key or not self.config.render_owner_id:
            return None, f"Render deployment skipped: RENDER_API_KEY or RENDER_OWNER_ID is not configured. Blueprint written to {blueprint}."
        repo = os.getenv("RENDER_GIT_REPO")
        branch = os.getenv("RENDER_GIT_BRANCH", "main")
        if not repo:
            return None, f"Render deployment skipped: RENDER_GIT_REPO is required for Render API service creation. Blueprint written to {blueprint}."
        payload = {
            "type": "web_service",
            "name": self.config.render_service_name,
            "ownerId": self.config.render_owner_id,
            "repo": repo,
            "branch": branch,
            "serviceDetails": {
                "env": "python",
                "region": self.config.render_region,
                "plan": self.config.render_plan,
                "buildCommand": "pip install -e .",
                "startCommand": self._render_start_command(spec),
            },
        }
        try:
            data = await asyncio.to_thread(self._post_json, "https://api.render.com/v1/services", payload, self.config.render_api_key)
        except RuntimeError as exc:
            return None, f"Render API error: {exc}\nBlueprint: {blueprint}"
        url = data.get("service", {}).get("serviceDetails", {}).get("url") or data.get("service", {}).get("url")
        return url, "Render deployment request created."

    def _ensure_render_files(self, root: Path, spec: ProjectSpec) -> Path:
        render_yaml = root / "render.yaml"
        render_yaml.write_text(
            f"""services:\n  - type: web\n    name: {self.config.render_service_name}\n    env: python\n    plan: {self.config.render_plan}\n    buildCommand: pip install -e .\n    startCommand: {self._render_start_command(spec)}\n""",
            encoding="utf-8",
        )
        return render_yaml

    async def verify_deployed(self, url: str | None, spec: ProjectSpec) -> str:
        if not url:
            return "No deployed URL to verify."
        checks = [endpoint.path for endpoint in spec.endpoints if endpoint.method.upper() == "GET"] or ["/health"]
        logs: list[str] = []
        for path in checks:
            status = await asyncio.to_thread(self._get_status, url.rstrip("/") + self._path_with_id(path, 1))
            logs.append(f"GET {path}: {status}")
        return "\n".join(logs)

    def _guess_base_url(self, command: str) -> str:
        port = "8000"
        parts = command.replace("=", " ").split()
        for index, part in enumerate(parts):
            if part in {"--port", "-p"} and index + 1 < len(parts):
                port = parts[index + 1]
                break
        if "flask" in command.lower() and port == "8000":
            port = "5000"
        return f"http://127.0.0.1:{port}"

    def _wait_for_server(self, base_url: str, endpoints: list) -> bool:
        health_paths = [endpoint.path for endpoint in endpoints if endpoint.method.upper() == "GET"] or ["/"]
        deadline = time.time() + 20
        while time.time() < deadline:
            for path in health_paths:
                try:
                    status = self._get_status(base_url + self._path_with_id(path, 1))
                    if status < 500:
                        return True
                except urllib.error.URLError:
                    pass
            time.sleep(0.25)
        return False

    def _request_json(self, url: str, method: str, payload: dict | None = None) -> tuple[int, str]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            return 599, repr(exc)

    def _payload_for_method(self, method: str) -> dict | None:
        if method == "POST":
            return {"name": "autocoder-check", "description": "created by tester"}
        if method in {"PUT", "PATCH"}:
            return {"name": "autocoder-check-updated", "description": "updated by tester"}
        return None

    def _path_with_id(self, path: str, item_id: int | str | None) -> str:
        replacement = str(item_id or 1)
        return path.replace("{id}", replacement).replace(":id", replacement)

    def _extract_id(self, body: str) -> int | str | None:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict):
            return data.get("id")
        return None

    def _stop_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, 15)
            process.wait(timeout=5)
        except Exception:
            try:
                os.killpg(process.pid, 9)
            except Exception:
                process.kill()

    def _collect_process_output(self, process: subprocess.Popen[str]) -> str:
        if not process.stdout:
            return ""
        try:
            output, _ = process.communicate(timeout=0.2)
            return (output or "")[-4000:]
        except Exception:
            return ""

    def _run_playwright_script(self, workspace: Workspace, base_url: str) -> tuple[int, str]:
        script = r'''
import sys
from playwright.sync_api import sync_playwright

base_url = sys.argv[1]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(base_url, wait_until="networkidle")
    clicked = []
    controls = page.locator("button, a, input[type=button], input[type=submit]")
    count = controls.count()
    for index in range(count):
        control = controls.nth(index)
        label = control.inner_text(timeout=1000) if control.is_visible() else f"control-{index}"
        try:
            control.click(timeout=2000)
            page.wait_for_timeout(250)
            clicked.append(label)
        except Exception as exc:
            clicked.append(f"{label}: {exc.__class__.__name__}")
    print(f"opened={base_url}; controls={count}; clicked={clicked}")
    browser.close()
'''
        process = subprocess.run(
            ["python", "-c", script, base_url],
            cwd=workspace.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=90,
        )
        return process.returncode, process.stdout

    def _render_start_command(self, spec: ProjectSpec) -> str:
        if spec.run_commands:
            return spec.run_commands[0].replace("--reload", "").strip()
        return "python -m app.main"

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
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code
