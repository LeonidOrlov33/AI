# Установка и запуск Autocoder Agent на своём компьютере

Этот файл нужен, чтобы не потеряться между GitHub, локальной папкой, CLI и GUI.

## 1. Получить файлы проекта

### Через GitHub

```bash
git clone https://github.com/<USERNAME>/<REPO>.git
cd <REPO>
```

Если репозиторий на GitHub пустой, сначала отправьте локальный код туда:

```bash
git remote add origin https://github.com/<USERNAME>/<REPO>.git
git branch -M main
git push -u origin main
```

### Через ZIP-архив из этой рабочей копии

```bash
python scripts/export_project.py --output autocoder-agent.zip
```

Потом перенесите `autocoder-agent.zip` на компьютер и распакуйте.

## 2. Создать виртуальное окружение

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### macOS/Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 3. Установить зависимости

### Только CLI/core

```bash
python -m pip install -e .
```

### GUI на PyQt6

```bash
python -m pip install -e ".[gui]"
```

Если PyQt6 не ставится через pip на Linux, попробуйте системные пакеты:

```bash
sudo apt update
sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine
```

### Полная dev-среда

```bash
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## 4. Настроить ключи

По требованию проект больше не читает `.env`. Провайдеры и модели задаются в `src/autocoder_agent/core/llm.py`:

- Интервьюер → Gemini через OpenAI-совместимый Google AI Studio endpoint.
- Программист → DeepSeek через Ollama Cloud API.
- Тестировщик → Qwen через Ollama Cloud API.

В репозиторий нельзя коммитить реальные секреты. Если нужен hardcoded-режим на своём компьютере, вставьте ключи в приватной локальной копии `src/autocoder_agent/core/llm.py` вместо `PASTE_GEMINI_API_KEY_HERE` и `PASTE_OLLAMA_API_KEY_HERE`.

Render-деплой опционален. Его параметры всё ещё берутся из переменных окружения процесса: `RENDER_API_KEY`, `RENDER_OWNER_ID`, `RENDER_GIT_REPO`.

## 5. Запуск

### GUI

```bash
autocoder-agent-gui
```

или:

```bash
python -m autocoder_agent.gui.app
```

### CLI

```bash
autocoder-agent --goal "Создай FastAPI TODO сервис" --workspace ./generated/todo
```

Если пакет не установлен, можно запустить из исходников:

```bash
PYTHONPATH=src python -m autocoder_agent.cli --goal "Создай TODO API" --workspace ./generated/todo
```

## 6. Проверка проекта

```bash
python -m pytest
python -m compileall src tests
```

## Частые проблемы

### `ModuleNotFoundError: No module named 'PyQt6'`

GUI-зависимости не установлены. Выполните:

```bash
python -m pip install -e ".[gui]"
```

### На GitHub пустой репозиторий

Проверьте remote и ветку:

```bash
git remote -v
git branch -vv
git log --oneline --all -5
```

Если remote отсутствует, добавьте его и запушьте:

```bash
git remote add origin https://github.com/<USERNAME>/<REPO>.git
git branch -M main
git push -u origin main
```
