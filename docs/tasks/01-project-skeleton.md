# Task 01: Project Skeleton & Config System

## Priority: 1 (do first)
## Depends on: nothing
## Estimated time: 30-45 min

## Objective

Set up the project structure, dependencies, and Pydantic config system. Everything else builds on this.

## What to create

### 1. `pyproject.toml`

```toml
[project]
name = "voxaos"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # Server
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",

    # LLM (openai SDK works for both vLLM local and Mistral API)
    "openai>=1.0",
    "mistralai>=1.0",

    # Voice
    "numpy>=1.26",
    "soundfile>=0.12",

    # Tools
    "duckduckgo-search>=6.0",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "psutil>=5.9",
    "aiofiles>=23.0",

    # Memory
    "mem0ai>=0.1",
    "qdrant-client>=1.7",

    # Config
    "pydantic>=2.0",
    "tomli>=2.0",

    # Skills
    "pyyaml>=6.0",
]

[project.optional-dependencies]
local = [
    "torch>=2.0",
    "transformers>=4.40",
    "nemo_toolkit[tts]",
]
dev = [
    "ruff>=0.4",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "mypy>=1.10",
    "types-pyyaml",
    "types-psutil",
    "types-beautifulsoup4",
]

[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # relaxed for hackathon speed
```

### 2. `config/default.toml`

Default config with API mode as default. All settings for all components.

```toml
[mode]
backend = "api"    # "api", "local", or "hybrid"

[server]
host = "0.0.0.0"
port = 7860

[stt]
backend = "api"
[stt.local]
model_path = "~/.voxaos/models/voxtral-realtime"
[stt.api]
base_url = "https://api.mistral.ai/v1/audio/transcriptions"
api_key_env = "MISTRAL_API_KEY"

[llm]
backend = "api"
max_tool_iterations = 10
[llm.local]
base_url = "http://localhost:8000/v1"
model = "mistralai/Mistral-Nemo-Instruct-2407"
[llm.api]
base_url = "https://api.mistral.ai/v1"
model = "mistral-nemo-latest"
api_key_env = "MISTRAL_API_KEY"

[tts]
backend = "api"
[tts.local]
model = "fastpitch_hifigan"
model_path = "~/.voxaos/models/nemo-tts"
[tts.api]
base_url = "https://integrate.api.nvidia.com/v1"
api_key_env = "NVIDIA_API_KEY"
voice = "English-US.Female-1"

[vad]
threshold = 0.5
speech_start_ms = 300
silence_end_ms = 500

[tools]
shell_timeout = 30
output_max_chars = 4096
blocked_commands = ["rm -rf /", "mkfs", "dd if=/dev", "shutdown", "reboot", ":(){ :|:&};:", "chmod -R 777 /", "> /dev/sda"]

[memory]
enabled = true
storage_path = "~/.voxaos/memory"
[memory.learning]
enabled = true
[memory.capture]
enabled = true
db_path = "~/.voxaos/capture.db"

[home_assistant]
enabled = false
url = "http://homeassistant.local:8123"
token_env = "HA_TOKEN"
[home_assistant.insights]
enabled = true
schedule = "daily"
time = "08:00"
entities = []

[context]
max_history = 20
```

### 3. `core/__init__.py`, `core/config.py`

Pydantic models that match the TOML structure. Use nested BaseModel classes.

```python
import os
from pathlib import Path
from pydantic import BaseModel
import tomli

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 7860

class STTLocalConfig(BaseModel):
    model_path: str = "~/.voxaos/models/voxtral-realtime"

class STTApiConfig(BaseModel):
    base_url: str = "https://api.mistral.ai/v1/audio/transcriptions"
    api_key_env: str = "MISTRAL_API_KEY"

class STTConfig(BaseModel):
    backend: str = "api"
    local: STTLocalConfig = STTLocalConfig()
    api: STTApiConfig = STTApiConfig()

class LLMLocalConfig(BaseModel):
    base_url: str = "http://localhost:8000/v1"
    model: str = "mistralai/Mistral-Nemo-Instruct-2407"

class LLMApiConfig(BaseModel):
    base_url: str = "https://api.mistral.ai/v1"
    model: str = "mistral-nemo-latest"
    api_key_env: str = "MISTRAL_API_KEY"

class LLMConfig(BaseModel):
    backend: str = "api"
    max_tool_iterations: int = 10
    local: LLMLocalConfig = LLMLocalConfig()
    api: LLMApiConfig = LLMApiConfig()

class TTSLocalConfig(BaseModel):
    model: str = "fastpitch_hifigan"
    model_path: str = "~/.voxaos/models/nemo-tts"

class TTSApiConfig(BaseModel):
    base_url: str = "https://integrate.api.nvidia.com/v1"
    api_key_env: str = "NVIDIA_API_KEY"
    voice: str = "English-US.Female-1"

class TTSConfig(BaseModel):
    backend: str = "api"
    local: TTSLocalConfig = TTSLocalConfig()
    api: TTSApiConfig = TTSApiConfig()

class VADConfig(BaseModel):
    threshold: float = 0.5
    speech_start_ms: int = 300
    silence_end_ms: int = 500

class ToolsConfig(BaseModel):
    shell_timeout: int = 30
    output_max_chars: int = 4096
    blocked_commands: list[str] = []

class MemoryLearningConfig(BaseModel):
    enabled: bool = True

class MemoryCaptureConfig(BaseModel):
    enabled: bool = True
    db_path: str = "~/.voxaos/capture.db"

class MemoryConfig(BaseModel):
    enabled: bool = True
    storage_path: str = "~/.voxaos/memory"
    learning: MemoryLearningConfig = MemoryLearningConfig()
    capture: MemoryCaptureConfig = MemoryCaptureConfig()

class HAInsightsConfig(BaseModel):
    enabled: bool = True
    schedule: str = "daily"
    time: str = "08:00"
    entities: list[str] = []

class HomeAssistantConfig(BaseModel):
    enabled: bool = False
    url: str = "http://homeassistant.local:8123"
    token_env: str = "HA_TOKEN"
    insights: HAInsightsConfig = HAInsightsConfig()

class ContextConfig(BaseModel):
    max_history: int = 20

class ModeConfig(BaseModel):
    backend: str = "api"

class Config(BaseModel):
    mode: ModeConfig = ModeConfig()
    server: ServerConfig = ServerConfig()
    stt: STTConfig = STTConfig()
    llm: LLMConfig = LLMConfig()
    tts: TTSConfig = TTSConfig()
    vad: VADConfig = VADConfig()
    tools: ToolsConfig = ToolsConfig()
    memory: MemoryConfig = MemoryConfig()
    home_assistant: HomeAssistantConfig = HomeAssistantConfig()
    context: ContextConfig = ContextConfig()

def load_config(path: str = "config/default.toml") -> Config:
    """Load config from TOML file, validate with Pydantic."""
    with open(path, "rb") as f:
        data = tomli.load(f)
    return Config(**data)
```

### 4. `core/types.py`

Shared dataclasses used across the entire project.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class PipelineState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"

class RiskLevel(str, Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"

class StreamChunkType(str, Enum):
    TRANSCRIPT = "transcript"
    THINKING = "thinking"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    TEXT = "text"
    AUDIO = "audio"
    STATE = "state"

@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]

@dataclass
class ToolResult:
    tool_call_id: str
    content: str
    is_error: bool = False

@dataclass
class StreamChunk:
    type: StreamChunkType
    content: Any  # str for text types, bytes for audio

@dataclass
class Response:
    text: str
    audio_bytes: bytes | None = None
    tool_calls_made: list[ToolCall] = field(default_factory=list)
    latency_ms: dict[str, float] = field(default_factory=dict)
```

### 5. Directory structure

Create all `__init__.py` files:
```
voxaos/
├── config/
│   └── default.toml
├── core/
│   ├── __init__.py
│   ├── config.py
│   └── types.py
├── llm/
│   └── __init__.py
├── voice/
│   └── __init__.py
├── tools/
│   └── __init__.py
├── skills/
│   └── __init__.py
├── memory/
│   └── __init__.py
├── server/
│   └── __init__.py
├── tests/
│   ├── __init__.py
│   └── conftest.py       # Shared fixtures (config, mock LLM, etc.)
├── ui/
├── scripts/
├── main.py              # Placeholder: just imports config and prints it
└── pyproject.toml
```

### 6. `main.py` (placeholder)

```python
import asyncio
from core.config import load_config

async def main():
    config = load_config()
    print(f"VoxaOS starting in {config.mode.backend} mode")
    print(f"LLM: {config.llm.backend} -> {config.llm.api.base_url if config.llm.backend == 'api' else config.llm.local.base_url}")
    print(f"STT: {config.stt.backend}")
    print(f"TTS: {config.tts.backend}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 7. `tests/conftest.py`

Shared pytest fixtures used across all test files:

```python
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
model = "mistral-nemo-latest"
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
```

### 8. `tests/test_config.py`

```python
from core.config import load_config, Config
from core.types import PipelineState, RiskLevel

def test_load_default_config():
    config = load_config()
    assert isinstance(config, Config)
    assert config.server.port == 7860

def test_config_defaults():
    config = Config()
    assert config.mode.backend == "api"
    assert config.llm.backend == "api"
    assert config.memory.enabled is True

def test_types_enums():
    assert PipelineState.IDLE.value == "idle"
    assert RiskLevel.DANGEROUS.value == "dangerous"
```

## Verification

```bash
uv sync --extra dev
uv run python main.py
# Should print config summary without errors
```

## Quality Gate

Run all of these before moving to task 02:

```bash
# Lint
uv run ruff check core/ tests/ main.py

# Type check
uv run mypy core/config.py core/types.py

# Tests
uv run pytest tests/test_config.py -v

# Import smoke test
uv run python -c "from core.config import load_config; from core.types import PipelineState; print('OK')"
```

| Check | Command | Pass? |
|-------|---------|-------|
| Lint clean | `ruff check core/ tests/ main.py` | |
| Types pass | `mypy core/config.py core/types.py` | |
| Config tests pass | `pytest tests/test_config.py -v` | |
| Config loads | `python main.py` prints config summary | |

## Design reference

See PLAN.md sections: "Project Structure", "Deployment Modes & Fallback Strategy" (config switch), "Dependencies"
