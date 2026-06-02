from __future__ import annotations

import json
from typing import Any

from .diff import apply_diff_blocks, parse_diff_blocks
from .llm import ProviderRouter, extract_json
from .models import ChatMessage, GeneratedFile, GenerationResult, ProjectSpec, TestIssue
from .workspace import Workspace


INTERVIEWER_SYSTEM = """Ты Интервьюер Gemini 2.5 Pro в агенте автопрограммирования.
Задай пользователю 5-7 точных уточняющих вопросов. После получения ответов создай детальное ТЗ в JSON.
ТЗ должно включать: стек, архитектуру, структуру файлов, endpoints, схему БД, команды запуска и тестирования.
Отвечай по-русски. JSON должен соответствовать полям ProjectSpec.
"""

PROGRAMMER_SYSTEM = """Ты Программист DeepSeek 671B. По ТЗ генерируй ВСЕ файлы проекта.
Возвращай строго JSON: {"files":[{"path":"...","content":"..."}],"notes":"..."}.
Код должен быть рабочим, самодостаточным, с README, тестами и командами запуска.
Если тебя просят исправить ошибку, возвращай JSON вида {"patches":[{"path":"...","diff":"<<<<<<< ORIGINAL\nстарый код\n=======\nновый код\n>>>>>>> FIXED"}],"notes":"..."}.
Не переписывай весь файл при исправлениях — только точечные diff-блоки.
"""

TESTER_SYSTEM = """Ты Тестировщик Qwen 397B. Анализируй проект как строгий QA.
Найди ошибки, проверь API endpoints, UI-кнопки и сценарии. Возвращай JSON:
{"success":false,"issues":[{"file":"...","severity":"high","description":"...","command":"...","output":"..."}],"recommended_commands":["..."]}
или {"success":true,"issues":[],"recommended_commands":["..."]}.
"""


class Interviewer:
    def __init__(self, llm: ProviderRouter, model: str) -> None:
        self.llm = llm
        self.model = model

    async def ask_questions(self, goal: str) -> list[str]:
        if not self.llm.available:
            return [
                "Какой тип приложения нужен (web/API/CLI/desktop) и кто пользователь?",
                "Какие 3-5 ключевых функций обязательны в первой версии?",
                "Нужна ли база данных, аутентификация, роли пользователей?",
                "Какой стек предпочитаете: FastAPI/Django/Flask, frontend, Docker?",
                "Какие внешние сервисы, файлы или API нужно подключить?",
                "Как проект должен запускаться, тестироваться и деплоиться?",
            ]
        content = await self.llm.chat(
            self.model,
            [ChatMessage(role="system", content=INTERVIEWER_SYSTEM), ChatMessage(role="user", content=f"Цель проекта: {goal}\nЗадай 5-7 вопросов списком.")],
        )
        return [line.strip(" -0123456789.") for line in content.splitlines() if line.strip()][:7]

    async def make_spec(self, goal: str, answers: dict[str, str]) -> ProjectSpec:
        if not self.llm.available:
            return self._fallback_spec(goal, answers)
        prompt = f"Цель: {goal}\nОтветы пользователя:\n{json.dumps(answers, ensure_ascii=False, indent=2)}\nВерни только JSON ProjectSpec."
        content = await self.llm.chat(
            self.model,
            [ChatMessage(role="system", content=INTERVIEWER_SYSTEM), ChatMessage(role="user", content=prompt)],
            json_mode=True,
        )
        return ProjectSpec.model_validate(extract_json(content))

    def _fallback_spec(self, goal: str, answers: dict[str, str]) -> ProjectSpec:
        summary = goal or "Python web API project"
        return ProjectSpec(
            title="Generated Python Application",
            summary=summary,
            stack=["Python", "stdlib http.server", "unittest"],
            architecture="Dependency-free layered HTTP JSON API with in-memory storage and stdlib tests.",
            files=[
                {"path": "pyproject.toml", "purpose": "dependencies"},
                {"path": "app/main.py", "purpose": "stdlib HTTP JSON API"},
                {"path": "tests/test_api.py", "purpose": "API tests"},
                {"path": "README.md", "purpose": "usage"},
            ],
            endpoints=[
                {"method": "GET", "path": "/health", "description": "healthcheck"},
                {"method": "GET", "path": "/items", "description": "list items"},
                {"method": "POST", "path": "/items", "description": "create item"},
                {"method": "PUT", "path": "/items/{id}", "description": "update item"},
                {"method": "DELETE", "path": "/items/{id}", "description": "delete item"},
            ],
            run_commands=["python -m app.main"],
            test_commands=["python -m unittest discover -s tests"],
            acceptance_criteria=["All tests pass", "All declared API endpoints respond", "Project starts locally"],
        )


class Programmer:
    def __init__(self, llm: ProviderRouter, model: str) -> None:
        self.llm = llm
        self.model = model

    async def generate(self, spec: ProjectSpec) -> GenerationResult:
        if not self.llm.available:
            return self._fallback_generation(spec)
        content = await self.llm.chat(
            self.model,
            [ChatMessage(role="system", content=PROGRAMMER_SYSTEM), ChatMessage(role="user", content=spec.model_dump_json(indent=2))],
            json_mode=True,
        )
        return GenerationResult.model_validate(extract_json(content))

    async def fix(self, workspace: Workspace, issues: list[TestIssue]) -> str:
        if not self.llm.available:
            return "API key is not configured; automatic LLM fixes skipped."
        prompt = "Код проекта:\n" + workspace.snapshot() + "\nОшибки:\n" + json.dumps([i.model_dump() for i in issues], ensure_ascii=False, indent=2)
        content = await self.llm.chat(
            self.model,
            [ChatMessage(role="system", content=PROGRAMMER_SYSTEM), ChatMessage(role="user", content=prompt)],
            json_mode=True,
        )
        data: dict[str, Any] = extract_json(content)
        notes = data.get("notes", "")
        for patch in data.get("patches", []):
            path = patch["path"]
            blocks = parse_diff_blocks(patch["diff"])
            current = workspace.read_text(path)
            workspace.safe_path(path).write_text(apply_diff_blocks(current, blocks), encoding="utf-8")
        return notes

    def _fallback_generation(self, spec: ProjectSpec) -> GenerationResult:
        main_py = r'''import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ITEMS: dict[int, dict] = {}
NEXT_ID = 1


def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict | list) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            _json(self, HTTPStatus.OK, {"status": "ok"})
        elif path == "/items":
            _json(self, HTTPStatus.OK, list(ITEMS.values()))
        else:
            _json(self, HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        global NEXT_ID
        if urlparse(self.path).path != "/items":
            _json(self, HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        data = self._read_json()
        if not data.get("name"):
            _json(self, HTTPStatus.BAD_REQUEST, {"error": "name is required"})
            return
        item = {"id": NEXT_ID, "name": data["name"], "description": data.get("description")}
        ITEMS[NEXT_ID] = item
        NEXT_ID += 1
        _json(self, HTTPStatus.CREATED, item)

    def do_PUT(self) -> None:
        item_id = self._item_id()
        if item_id is None or item_id not in ITEMS:
            _json(self, HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        data = self._read_json()
        ITEMS[item_id].update({key: value for key, value in data.items() if key in {"name", "description"}})
        _json(self, HTTPStatus.OK, ITEMS[item_id])

    def do_DELETE(self) -> None:
        item_id = self._item_id()
        if item_id is None or item_id not in ITEMS:
            _json(self, HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        deleted = ITEMS.pop(item_id)
        _json(self, HTTPStatus.OK, deleted)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _item_id(self) -> int | None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != "items":
            return None
        try:
            return int(parts[1])
        except ValueError:
            return None

    def log_message(self, format: str, *args) -> None:
        return


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
'''
        tests_py = r'''import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from app.main import AppHandler, ITEMS


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ITEMS.clear()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), AppHandler)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=2)

    def request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(self.url + path, data=data, method=method, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_crud_and_health(self):
        self.assertEqual(self.request("GET", "/health"), (200, {"status": "ok"}))
        status, created = self.request("POST", "/items", {"name": "demo"})
        self.assertEqual(status, 201)
        item_id = created["id"]
        self.assertEqual(self.request("GET", "/items")[0], 200)
        self.assertEqual(self.request("PUT", f"/items/{item_id}", {"description": "updated"})[1]["description"], "updated")
        self.assertEqual(self.request("DELETE", f"/items/{item_id}")[0], 200)


if __name__ == "__main__":
    unittest.main()
'''
        return GenerationResult(
            notes="Fallback generator used because no LLM key is configured.",
            files=[
                GeneratedFile(path="pyproject.toml", content='[project]\nname = "generated-app"\nversion = "0.1.0"\nrequires-python = ">=3.11"\ndependencies = []\n'),
                GeneratedFile(path="app/__init__.py", content=""),
                GeneratedFile(path="app/main.py", content=main_py),
                GeneratedFile(path="tests/test_api.py", content=tests_py),
                GeneratedFile(path="README.md", content=f'''# {spec.title}

{spec.summary}

## Запуск

```bash
python -m app.main
python -m unittest discover -s tests
```

API: `GET /health`, `GET /items`, `POST /items`, `PUT /items/{{id}}`, `DELETE /items/{{id}}`.
'''),
            ],
        )
