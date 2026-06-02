from autocoder_agent.core.config import load_config
from autocoder_agent.core.models import ProjectSpec
from autocoder_agent.core.pipeline import AutocoderPipeline
from autocoder_agent.core.tester import Tester as AutocoderTester
from autocoder_agent.core.llm import ProviderRouter


def test_tester_exercises_generated_crud_endpoints(tmp_path):
    config = load_config(tmp_path / "generated")
    pipeline = AutocoderPipeline(config)
    spec = pipeline.interviewer._fallback_spec("Создай TODO API", {})
    result = pipeline.programmer._fallback_generation(spec)
    pipeline.workspace.write_files(result.files)

    report = pipeline.tester.verify_local_endpoints(pipeline.workspace, spec)

    assert report.success, report.logs
    assert "GET /health: 200" in report.logs
    assert "POST /items: 201" in report.logs
    assert "PUT /items/" in report.logs
    assert "DELETE /items/" in report.logs


def test_render_blueprint_uses_project_run_command(tmp_path):
    config = load_config(tmp_path)
    tester = AutocoderTester(ProviderRouter(), config.qwen_model, config)
    spec = ProjectSpec(title="Demo", summary="Demo", run_commands=["python -m app.main"])

    path = tester._ensure_render_files(tmp_path, spec)

    assert "startCommand: python -m app.main" in path.read_text(encoding="utf-8")
