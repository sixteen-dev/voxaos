import tomli
from pydantic import BaseModel


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
    model: str = "open-mistral-nemo"
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
    backend: str = "disabled"
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
