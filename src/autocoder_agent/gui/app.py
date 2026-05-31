from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFileSystemModel,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from autocoder_agent.core.config import load_config
from autocoder_agent.core.events import AgentEvent, EventBus
from autocoder_agent.core.pipeline import AutocoderPipeline
from autocoder_agent.gui.monaco import MonacoEditor, language_for_path


STYLE = """
QMainWindow, QWidget { background: #1e1e1e; color: #d4d4d4; }
QTextEdit, QLineEdit, QTreeView, QTabWidget::pane { background: #252526; color: #d4d4d4; border: 1px solid #3c3c3c; }
QPushButton { background: #0e639c; color: white; padding: 8px; border: 0; border-radius: 4px; }
QPushButton:hover { background: #1177bb; }
QTabBar::tab { background: #2d2d2d; color: #d4d4d4; padding: 8px; }
QTabBar::tab:selected { background: #1e1e1e; border-bottom: 2px solid #0e639c; }
"""


class AgentWorker(QThread):
    event = pyqtSignal(str, str, object)
    finished_report = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, goal: str, workspace: Path) -> None:
        super().__init__()
        self.goal = goal
        self.workspace = workspace

    def run(self) -> None:
        try:
            asyncio.run(self._run_async())
        except Exception as exc:
            self.failed.emit(repr(exc))

    async def _run_async(self) -> None:
        bus = EventBus()
        bus.subscribe(self._emit_event)
        pipeline = AutocoderPipeline(load_config(self.workspace), bus)
        questions = await pipeline.interview_questions(self.goal)
        answers: dict[str, str] = {}
        for question in questions:
            answers[question] = "Сделай оптимальный выбор для production-ready MVP."
            self.event.emit("Интервью", f"Q: {question}\nA: {answers[question]}", None)
        spec = await pipeline.build_spec(self.goal, answers)
        report = await pipeline.generate_project(spec)
        self.finished_report.emit(report)

    def _emit_event(self, event: AgentEvent) -> None:
        payload = event.payload
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        self.event.emit(event.stage.value, event.message, payload)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Автопрограммист — Gemini + DeepSeek + Qwen")
        self.resize(1500, 900)
        self.workspace = Path.cwd() / "generated_project"
        self.worker: AgentWorker | None = None
        self._build_ui()
        self._bind_actions()
        self.refresh_tree()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        top = QSplitter()
        top.setHandleWidth(2)

        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(str(self.workspace))
        self.tree = QTreeView()
        self.tree.setHeaderHidden(False)
        self.tree.setModel(self.file_model)
        for column in range(1, 4):
            self.tree.hideColumn(column)
        top.addWidget(self.tree)

        self.editor = MonacoEditor()
        self.editor.set_code("# Здесь появится код проекта", "python")
        top.addWidget(self.editor)

        right = QTabWidget()
        self.chat = QTextEdit()
        self.plan = QTextEdit()
        self.test_log = QTextEdit()
        self.stage = QTextEdit()
        for widget in (self.chat, self.plan, self.test_log, self.stage):
            widget.setReadOnly(True)
        right.addTab(self.chat, "Чат")
        right.addTab(self.plan, "План/ТЗ")
        right.addTab(self.test_log, "Лог тестов")
        right.addTab(self.stage, "Этап")
        top.addWidget(right)
        top.setSizes([260, 820, 420])

        bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(bottom_bar)
        self.goal_input = QLineEdit()
        self.goal_input.setPlaceholderText("Опишите проект, который нужно создать...")
        self.run_button = QPushButton("Запустить агента")
        bottom_layout.addWidget(self.goal_input)
        bottom_layout.addWidget(self.run_button)

        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setMaximumHeight(190)
        self.terminal.setPlaceholderText("Терминал и системные логи")

        root_layout.addWidget(top, 1)
        root_layout.addWidget(bottom_bar)
        root_layout.addWidget(self.terminal)
        self.setCentralWidget(root)

        menu = self.menuBar().addMenu("Файл")
        self.open_workspace_action = QAction("Выбрать workspace", self)
        self.refresh_action = QAction("Обновить дерево", self)
        menu.addAction(self.open_workspace_action)
        menu.addAction(self.refresh_action)

    def _bind_actions(self) -> None:
        self.run_button.clicked.connect(self.start_agent)
        self.tree.clicked.connect(self.open_selected_file)
        self.refresh_action.triggered.connect(self.refresh_tree)
        self.open_workspace_action.triggered.connect(self.choose_workspace)

    def choose_workspace(self) -> None:
        text, ok = QInputDialog.getText(self, "Workspace", "Путь к workspace:", text=str(self.workspace))
        if ok and text:
            self.workspace = Path(text).expanduser().resolve()
            self.refresh_tree()

    def refresh_tree(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.file_model.setRootPath(str(self.workspace))
        self.tree.setRootIndex(self.file_model.index(str(self.workspace)))

    def open_selected_file(self) -> None:
        path = Path(self.file_model.filePath(self.tree.currentIndex()))
        if path.is_file():
            self.editor.set_code(path.read_text(encoding="utf-8", errors="replace"), language_for_path(path.name))

    def start_agent(self) -> None:
        goal = self.goal_input.text().strip()
        if not goal:
            QMessageBox.warning(self, "Нет задачи", "Введите описание проекта.")
            return
        self.run_button.setEnabled(False)
        self.terminal.append(f"$ start-agent {goal}")
        self.worker = AgentWorker(goal, self.workspace)
        self.worker.event.connect(self.handle_event)
        self.worker.finished_report.connect(self.handle_finished)
        self.worker.failed.connect(self.handle_failed)
        self.worker.start()

    def handle_event(self, stage: str, message: str, payload: object) -> None:
        line = f"[{stage}] {message}"
        self.terminal.append(line)
        self.stage.append(line)
        if stage in {"Интервью", "Формирование ТЗ"}:
            self.chat.append(message)
        if payload:
            rendered = json.dumps(payload, ensure_ascii=False, indent=2) if not isinstance(payload, str) else payload
            if stage == "Формирование ТЗ":
                self.plan.setPlainText(rendered)
            elif stage == "Тестирование":
                self.test_log.append(rendered)
        self.refresh_tree()

    def handle_finished(self, report: object) -> None:
        self.run_button.setEnabled(True)
        self.terminal.append("Готово")
        self.test_log.append(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
        self.refresh_tree()

    def handle_failed(self, error: str) -> None:
        self.run_button.setEnabled(True)
        self.terminal.append(f"ОШИБКА: {error}")
        QMessageBox.critical(self, "Ошибка агента", error)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
