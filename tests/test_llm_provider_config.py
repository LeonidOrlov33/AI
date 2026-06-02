from autocoder_agent.core import llm
from autocoder_agent.core.config import load_config


def test_hardcoded_provider_models_are_wired_into_config(tmp_path):
    config = load_config(tmp_path / "generated")
    assert config.gemini_model == llm.GEMINI_MODEL
    assert config.deepseek_model == llm.DEEPSEEK_MODEL
    assert config.qwen_model == llm.QWEN_MODEL


def test_no_real_provider_secrets_are_committed():
    assert llm.GEMINI_API_KEY == "PASTE_GEMINI_API_KEY_HERE"
    assert llm.OLLAMA_API_KEY == "PASTE_OLLAMA_API_KEY_HERE"
