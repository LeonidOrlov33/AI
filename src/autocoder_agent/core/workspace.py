from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .models import GeneratedFile


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def safe_path(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise ValueError(f"Unsafe path outside workspace: {relative}")
        return candidate

    def write_file(self, file: GeneratedFile) -> Path:
        path = self.safe_path(file.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file.content, encoding="utf-8")
        return path

    def write_files(self, files: list[GeneratedFile]) -> list[Path]:
        self.ensure()
        return [self.write_file(file) for file in files]

    def read_text(self, relative: str) -> str:
        return self.safe_path(relative).read_text(encoding="utf-8")

    def list_files(self) -> list[str]:
        if not self.root.exists():
            return []
        ignored = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"}
        result: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in ignored]
            for filename in filenames:
                path = Path(dirpath) / filename
                result.append(str(path.relative_to(self.root)))
        return sorted(result)

    def snapshot(self, max_chars_per_file: int = 12000) -> str:
        chunks: list[str] = []
        for relative in self.list_files():
            path = self.safe_path(relative)
            if path.stat().st_size > max_chars_per_file:
                content = path.read_text(encoding="utf-8", errors="replace")[:max_chars_per_file]
                content += "\n...[truncated]"
            else:
                content = path.read_text(encoding="utf-8", errors="replace")
            chunks.append(f"# FILE: {relative}\n```\n{content}\n```")
        return "\n\n".join(chunks)

    def run(self, command: str, timeout: int = 120) -> tuple[int, str]:
        process = subprocess.run(
            command,
            cwd=self.root,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return process.returncode, process.stdout

    def reset(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
