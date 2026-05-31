from __future__ import annotations

import argparse
import asyncio

try:
    from rich.console import Console
except Exception:
    class Console:  # type: ignore[no-redef]
        def log(self, message: str) -> None:
            print(message)

        def print_json(self, data) -> None:
            import json
            if hasattr(data, "model_dump"):
                data = data.model_dump(mode="json")
            print(json.dumps(data, ensure_ascii=False, indent=2))

from .core.config import load_config
from .core.events import AgentEvent, EventBus
from .core.pipeline import AutocoderPipeline

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="AI агент автоматического программирования")
    parser.add_argument("--goal", required=True, help="Что нужно создать")
    parser.add_argument("--workspace", default=None, help="Куда записать сгенерированный проект")
    parser.add_argument("--answer", action="append", default=[], help="Ответ на вопрос интервьюера. Можно указать несколько раз.")
    args = parser.parse_args()
    asyncio.run(run(args.goal, args.workspace, args.answer))


async def run(goal: str, workspace: str | None, raw_answers: list[str]) -> None:
    events = EventBus()
    events.subscribe(lambda event: console.log(f"[{event.stage.value}] {event.message}"))
    pipeline = AutocoderPipeline(load_config(workspace), events)
    questions = await pipeline.interview_questions(goal)
    answers: dict[str, str] = {}
    for index, question in enumerate(questions):
        answers[question] = raw_answers[index] if index < len(raw_answers) else "Сделай оптимальный выбор для MVP."
    spec = await pipeline.build_spec(goal, answers)
    report = await pipeline.generate_project(spec)
    console.print_json(data=report.model_dump(mode="json"))


if __name__ == "__main__":
    main()
