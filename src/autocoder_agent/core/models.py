from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypeVar


class ModelMixin:
    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, Enum):
                return value.value
            if hasattr(value, "model_dump"):
                return value.model_dump(mode=mode)
            if isinstance(value, list):
                return [convert(v) for v in value]
            if isinstance(value, dict):
                return {k: convert(v) for k, v in value.items()}
            return value
        return {k: convert(v) for k, v in asdict(self).items()}

    def model_dump_json(self, indent: int | None = None, ensure_ascii: bool = False) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=ensure_ascii, indent=indent)

    @classmethod
    def model_validate(cls: type[T], data: dict[str, Any]) -> T:
        return cls(**data)  # type: ignore[arg-type]


T = TypeVar("T", bound=ModelMixin)


class Stage(str, Enum):
    IDLE = "Ожидание"
    INTERVIEW = "Интервью"
    SPEC = "Формирование ТЗ"
    GENERATION = "Генерация кода"
    TESTING = "Тестирование"
    FIXING = "Исправление"
    DEPLOY = "Деплой"
    DONE = "Готово"
    FAILED = "Ошибка"


@dataclass
class ChatMessage(ModelMixin):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class FileSpec(ModelMixin):
    path: str
    purpose: str = ""


@dataclass
class EndpointSpec(ModelMixin):
    method: str
    path: str
    description: str = ""
    request_schema: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None


@dataclass
class DatabaseSpec(ModelMixin):
    engine: str = "sqlite"
    models: list[dict[str, Any]] = field(default_factory=list)
    migrations: bool = False


@dataclass
class ProjectSpec(ModelMixin):
    title: str
    summary: str
    language: str = "Python"
    stack: list[str] = field(default_factory=list)
    architecture: str = ""
    files: list[FileSpec | dict[str, Any]] = field(default_factory=list)
    endpoints: list[EndpointSpec | dict[str, Any]] = field(default_factory=list)
    database: DatabaseSpec | dict[str, Any] = field(default_factory=DatabaseSpec)
    run_commands: list[str] = field(default_factory=list)
    test_commands: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.files = [f if isinstance(f, FileSpec) else FileSpec(**f) for f in self.files]
        self.endpoints = [e if isinstance(e, EndpointSpec) else EndpointSpec(**e) for e in self.endpoints]
        if isinstance(self.database, dict):
            self.database = DatabaseSpec(**self.database)


@dataclass
class GeneratedFile(ModelMixin):
    path: str
    content: str


@dataclass
class GenerationResult(ModelMixin):
    files: list[GeneratedFile | dict[str, Any]]
    notes: str = ""

    def __post_init__(self) -> None:
        self.files = [f if isinstance(f, GeneratedFile) else GeneratedFile(**f) for f in self.files]


@dataclass
class TestIssue(ModelMixin):
    description: str
    file: str | None = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    command: str | None = None
    output: str | None = None


@dataclass
class TestReport(ModelMixin):
    success: bool
    attempts: int = 1
    issues: list[TestIssue | dict[str, Any]] = field(default_factory=list)
    logs: str = ""
    deployed_url: str | None = None

    def __post_init__(self) -> None:
        self.issues = [i if isinstance(i, TestIssue) else TestIssue(**i) for i in self.issues]


@dataclass
class AgentConfig(ModelMixin):
    workspace: Path = field(default_factory=lambda: Path.cwd() / "generated_project")
    max_fix_attempts: int = 5
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    gemini_model: str = "google/gemini-2.5-pro"
    deepseek_model: str = "deepseek/deepseek-r1-671b"
    qwen_model: str = "qwen/qwen3-235b-a22b-thinking-2507"
    render_api_key: str | None = None
    render_owner_id: str | None = None
    render_service_name: str = "autocoder-generated-app"
    render_region: str = "oregon"
    render_plan: str = "free"
