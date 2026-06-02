import asyncio

from autocoder_agent.core.config import load_config
from autocoder_agent.core.pipeline import AutocoderPipeline


def test_fallback_interview_and_generation(tmp_path):
    async def scenario():
        pipeline = AutocoderPipeline(load_config(tmp_path / "generated"))
        questions = await pipeline.interview_questions("Создай TODO API")
        assert 5 <= len(questions) <= 7
        spec = await pipeline.build_spec("Создай TODO API", {q: "MVP" for q in questions})
        result = await pipeline.programmer.generate(spec)
        pipeline.workspace.write_files(result.files)
        assert (tmp_path / "generated" / "app" / "main.py").exists()

    asyncio.run(scenario())
