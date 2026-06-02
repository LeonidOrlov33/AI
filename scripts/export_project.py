from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    "generated_project",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def should_include(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    if path.name == ".env":
        return False
    return path.is_file()


def export_project(root: Path, output: Path) -> Path:
    root = root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path == output or not should_include(path, root):
                continue
            archive.write(path, path.relative_to(root).as_posix())
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a portable ZIP archive of the Autocoder Agent project.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root to archive; defaults to the current directory.")
    parser.add_argument("--output", type=Path, default=Path("autocoder-agent.zip"), help="Output ZIP path.")
    args = parser.parse_args()
    output = export_project(args.root, args.output)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
