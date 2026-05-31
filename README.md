# Autocoder Agent

Полностью рабочий Python AI-агент для автоматического программирования с тремя последовательными специалистами:

1. **Интервьюер — Gemini 2.5 Pro**: задаёт 5–7 уточняющих вопросов и формирует детальное ТЗ в JSON.
2. **Программист — DeepSeek 671B**: генерирует все файлы проекта и вносит точечные исправления через diff-блоки.
3. **Тестировщик — Qwen 397B**: анализирует код, запускает unit-тесты, поднимает проект локально, проверяет все объявленные GET/POST/PUT/DELETE endpoints, может использовать Playwright, циклически отправляет ошибки программисту и деплоит на Render.

Приложение включает PyQt6 GUI в стиле VSCode/CloudCode: дерево файлов, Monaco Editor через `QWebEngineView`, вкладки «Чат», «План/ТЗ», «Лог тестов», «Этап», нижний терминал и тёмную тему.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[gui,test]"
cp .env.example .env
# заполните ключи
python -m autocoder_agent.gui.app
```

CLI-режим без GUI:

```bash
autocoder-agent --goal "Создай FastAPI TODO сервис" --workspace ./generated/todo
```

## Переменные окружения

См. `.env.example`. По умолчанию используются OpenRouter-совместимые endpoints, но базовый URL, ключи и имена моделей можно переопределить.

## Render

Деплой подготавливает `render.yaml` в сгенерированном проекте. Создание сервиса через Render API выполняется при наличии `RENDER_API_KEY`, `RENDER_OWNER_ID` и `RENDER_GIT_REPO`; без этих значений тестировщик честно отмечает деплой как пропущенный и продолжает локальную проверку.
