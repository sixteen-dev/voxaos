from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PipelineState(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class RiskLevel(StrEnum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


class StreamChunkType(StrEnum):
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
