#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PYTHONPATH=src python -m autocoder_agent.cli --goal "Создай TODO API" --workspace ./generated_project/demo
