from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class InteractionRecord:
    session_id: str
    timestamp: datetime
    user_transcript: str
    llm_messages: list[dict]
    tool_calls: list[dict]  # [{name, args, result}, ...]
    assistant_response: str
    skill_used: str | None = None
    latency_ms: dict[str, float] = field(default_factory=dict)
