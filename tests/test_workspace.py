import pytest

from autocoder_agent.core.models import GeneratedFile
from autocoder_agent.core.workspace import Workspace


def test_workspace_writes_and_blocks_path_escape(tmp_path):
    workspace = Workspace(tmp_path / "project")
    workspace.write_file(GeneratedFile(path="app/main.py", content="print('ok')"))
    assert workspace.read_text("app/main.py") == "print('ok')"
    with pytest.raises(ValueError):
        workspace.safe_path("../escape.py")
