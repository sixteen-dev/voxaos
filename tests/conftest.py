import pytest

from core.config import Config, load_config


@pytest.fixture
def config() -> Config:
    """Load default config for tests."""
    return load_config()


@pytest.fixture
def temp_config(tmp_path):
    """Create a temp config TOML for isolated tests."""
    toml_content = """
[mode]
backend = "api"
[server]
host = "127.0.0.1"
port = 7860
[llm]
backend = "api"
[llm.api]
base_url = "https://api.mistral.ai/v1"
model = "open-mistral-nemo"
api_key_env = "MISTRAL_API_KEY"
[stt]
backend = "api"
[tts]
backend = "api"
[vad]
threshold = 0.5
[tools]
shell_timeout = 5
output_max_chars = 1024
blocked_commands = ["rm -rf /"]
[memory]
enabled = false
[home_assistant]
enabled = false
[context]
max_history = 5
"""
    config_path = tmp_path / "test.toml"
    config_path.write_text(toml_content)
    return load_config(str(config_path))
