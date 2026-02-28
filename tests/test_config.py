from core.config import Config, load_config
from core.types import PipelineState, Response, RiskLevel, StreamChunkType, ToolCall, ToolResult


def test_load_default_config():
    config = load_config()
    assert isinstance(config, Config)
    assert config.server.port == 7860


def test_config_defaults():
    config = Config()
    assert config.mode.backend == "api"
    assert config.llm.backend == "api"
    assert config.memory.enabled is True


def test_config_server():
    config = load_config()
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 7860


def test_config_llm_api():
    config = load_config()
    assert config.llm.api.base_url == "https://api.mistral.ai/v1"
    assert config.llm.api.model == "open-mistral-nemo"
    assert config.llm.max_tool_iterations == 10


def test_config_ha_disabled():
    config = load_config()
    assert config.home_assistant.enabled is False


def test_config_blocked_commands():
    config = load_config()
    assert "rm -rf /" in config.tools.blocked_commands
    assert config.tools.shell_timeout == 30


def test_types_enums():
    assert PipelineState.IDLE.value == "idle"
    assert PipelineState.SPEAKING.value == "speaking"
    assert RiskLevel.DANGEROUS.value == "dangerous"
    assert StreamChunkType.TEXT.value == "text"


def test_types_tool_call():
    tc = ToolCall(id="1", name="run_shell", args={"command": "echo hi"})
    assert tc.id == "1"
    assert tc.name == "run_shell"
    assert tc.args["command"] == "echo hi"


def test_types_tool_result():
    tr = ToolResult(tool_call_id="1", content="hello")
    assert tr.is_error is False
    tr_err = ToolResult(tool_call_id="2", content="fail", is_error=True)
    assert tr_err.is_error is True


def test_types_response_defaults():
    resp = Response(text="hi")
    assert resp.audio_bytes is None
    assert resp.tool_calls_made == []
    assert resp.latency_ms == {}


def test_temp_config(temp_config):
    assert temp_config.server.host == "127.0.0.1"
    assert temp_config.tools.shell_timeout == 5
    assert temp_config.memory.enabled is False
    assert temp_config.home_assistant.enabled is False
    assert temp_config.context.max_history == 5
