from __future__ import annotations

from .events import EventBus
from .llm import ProviderRouter
from .models import AgentConfig, ProjectSpec, Stage, TestReport
from .specialists import Interviewer, Programmer
from .tester import Tester
from .workspace import Workspace


class AutocoderPipeline:
    def __init__(self, config: AgentConfig, events: EventBus | None = None) -> None:
        self.config = config
        self.events = events or EventBus()
        self.workspace = Workspace(config.workspace)
        llm = ProviderRouter()
        self.interviewer = Interviewer(llm, config.gemini_model)
        self.programmer = Programmer(llm, config.deepseek_model)
        self.tester = Tester(llm, config.qwen_model, config)

    async def interview_questions(self, goal: str) -> list[str]:
        self.events.emit(Stage.INTERVIEW, "Интервьюер готовит уточняющие вопросы")
        return await self.interviewer.ask_questions(goal)

    async def build_spec(self, goal: str, answers: dict[str, str]) -> ProjectSpec:
        self.events.emit(Stage.SPEC, "Интервьюер формирует JSON ТЗ")
        spec = await self.interviewer.make_spec(goal, answers)
        self.events.emit(Stage.SPEC, spec.model_dump_json(indent=2, ensure_ascii=False), spec)
        return spec

    async def generate_project(self, spec: ProjectSpec, *, clean: bool = True) -> TestReport:
        self.events.emit(Stage.GENERATION, "Программист генерирует файлы проекта")
        if clean:
            self.workspace.reset()
        result = await self.programmer.generate(spec)
        self.workspace.write_files(result.files)
        self.events.emit(Stage.GENERATION, f"Записано файлов: {len(result.files)}. {result.notes}")
        return await self.test_fix_deploy(spec)

    async def test_fix_deploy(self, spec: ProjectSpec) -> TestReport:
        final_report = TestReport(success=False, attempts=0)
        for attempt in range(1, self.config.max_fix_attempts + 1):
            self.events.emit(Stage.TESTING, f"Тестировщик запускает проверку, попытка {attempt}")
            ai_issues = await self.tester.analyze(self.workspace, spec)
            local_report = self.tester.run_local_checks(self.workspace, spec)
            endpoint_report = self.tester.verify_local_endpoints(self.workspace, spec)
            browser_report = self.tester.run_playwright_smoke(self.workspace, spec)
            issues = ai_issues + local_report.issues + endpoint_report.issues + browser_report.issues
            logs = "\n\n".join(part for part in [local_report.logs, endpoint_report.logs, browser_report.logs] if part)
            final_report = TestReport(success=not issues, attempts=attempt, issues=issues, logs=logs)
            self.events.emit(Stage.TESTING, logs or "Локальные проверки завершены", final_report)
            if not issues:
                self.events.emit(Stage.DEPLOY, "Локальные проверки успешны, запускается деплой Render")
                url, deploy_log = await self.tester.deploy_render(self.workspace, spec)
                verify_log = await self.tester.verify_deployed(url, spec)
                final_report.deployed_url = url
                final_report.logs += f"\n\n{deploy_log}\n{verify_log}"
                self.events.emit(Stage.DONE, "Проект успешно создан и проверен", final_report)
                return final_report
            self.events.emit(Stage.FIXING, f"Найдено ошибок: {len(issues)}. Программист исправляет точечными diff-блоками.")
            notes = await self.programmer.fix(self.workspace, issues)
            self.events.emit(Stage.FIXING, notes)
        self.events.emit(Stage.FAILED, "Достигнут лимит попыток исправления", final_report)
        return final_report
