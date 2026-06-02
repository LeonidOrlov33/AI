# Autocoder Agent

Полностью рабочий Python AI-агент для автоматического программирования с тремя последовательными специалистами:

1. **Интервьюер — Gemini 2.5 Pro**: задаёт 5–7 уточняющих вопросов и формирует детальное ТЗ в JSON.
2. **Программист — DeepSeek 671B**: генерирует все файлы проекта и вносит точечные исправления через diff-блоки.
3. **Тестировщик — Qwen 397B**: анализирует код, запускает unit-тесты, поднимает проект локально, проверяет все объявленные GET/POST/PUT/DELETE endpoints, может использовать Playwright, циклически отправляет ошибки программисту и деплоит на Render.

Приложение включает PyQt6 GUI в стиле VSCode/CloudCode: дерево файлов, Monaco Editor через `QWebEngineView`, вкладки «Чат», «План/ТЗ», «Лог тестов», «Этап», нижний терминал и тёмную тему.

## Документация

Подробная установка на Windows/macOS/Linux, перенос ZIP-архивом и инструкции для GitHub описаны в [`INSTALL_RU.md`](INSTALL_RU.md).

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[gui,test]"
# вставьте ключи в src/autocoder_agent/core/llm.py в приватной локальной копии
python -m autocoder_agent.gui.app
```

CLI-режим без GUI:

```bash
autocoder-agent --goal "Создай FastAPI TODO сервис" --workspace ./generated/todo
```

Демо-запуск из исходников без установки entrypoint:

```bash
./scripts/run_cli_demo.sh
```

Создать ZIP-архив проекта для переноса на другой компьютер:

```bash
python scripts/export_project.py --output autocoder-agent.zip
```

## Провайдеры моделей

Файл `src/autocoder_agent/core/llm.py` содержит две функции вызова: Gemini через OpenAI-совместимый Google AI Studio endpoint и Ollama Cloud для DeepSeek/Qwen. Реальные API-ключи не коммитятся; если нужен именно hardcoded-режим, вставьте ключи в приватной локальной копии файла.

## Render

Деплой подготавливает `render.yaml` в сгенерированном проекте. Создание сервиса через Render API выполняется при наличии `RENDER_API_KEY`, `RENDER_OWNER_ID` и `RENDER_GIT_REPO`; без этих значений тестировщик честно отмечает деплой как пропущенный и продолжает локальную проверку.
