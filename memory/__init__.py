from core.config import Config
from memory.capture import CaptureLog
from memory.learning import LearningMemory


def create_memory(config: Config) -> tuple[LearningMemory | None, CaptureLog | None]:
    """Create memory components based on config."""
    learning = None
    capture = None

    if config.memory.enabled and config.memory.learning.enabled:
        learning = LearningMemory(config.memory, config.llm)

    if config.memory.enabled and config.memory.capture.enabled:
        capture = CaptureLog(config.memory.capture.db_path)

    return learning, capture
