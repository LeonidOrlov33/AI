from pathlib import Path
import zipfile

from scripts.export_project import export_project


def test_export_project_excludes_caches_and_env(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("readme", encoding="utf-8")
    (root / ".env").write_text("SECRET=1", encoding="utf-8")
    cache = root / "__pycache__"
    cache.mkdir()
    (cache / "module.pyc").write_bytes(b"cache")

    output = tmp_path / "project.zip"
    export_project(root, output)

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())

    assert "README.md" in names
    assert ".env" not in names
    assert "__pycache__/module.pyc" not in names
