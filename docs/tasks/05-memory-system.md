# Task 05: Memory System (mem0 Learning + SQLite Capture)

## Priority: 5
## Depends on: Task 01 (config), Task 02 (LLM client — mem0 uses it for extraction)
## Estimated time: 30-45 min

## Objective

Build the two-layer memory system: mem0 for learning memory (extracts facts/preferences) and SQLite for full interaction capture (logs everything verbatim).

## What to create

### 1. `memory/types.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class InteractionRecord:
    session_id: str
    timestamp: datetime
    user_transcript: str
    llm_messages: list[dict]
    tool_calls: list[dict]        # [{name, args, result}, ...]
    assistant_response: str
    skill_used: str | None = None
    latency_ms: dict[str, float] = field(default_factory=dict)
```

### 2. `memory/learning.py`

mem0 wrapper. Points at the same LLM endpoint (Mistral API or local vLLM) for memory extraction. Uses Qdrant in-process (no external server needed).

```python
import os
from mem0 import Memory
from core.config import MemoryConfig, LLMConfig

class LearningMemory:
    def __init__(self, memory_config: MemoryConfig, llm_config: LLMConfig):
        # Determine LLM endpoint for mem0's extraction
        if llm_config.backend == "api":
            llm_base_url = llm_config.api.base_url
            llm_model = llm_config.api.model
            api_key = os.environ.get(llm_config.api.api_key_env, "")
        else:
            llm_base_url = llm_config.local.base_url
            llm_model = llm_config.local.model
            api_key = "not-needed"

        storage_path = os.path.expanduser(memory_config.storage_path)
        os.makedirs(storage_path, exist_ok=True)

        self.memory = Memory.from_config({
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "voxaos",
                    "path": storage_path,
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": llm_model,
                    "openai_base_url": llm_base_url,
                    "api_key": api_key,
                }
            }
        })

    def add(self, user_msg: str, assistant_msg: str, user_id: str = "default"):
        """Extract and store memories from a conversation exchange."""
        messages = [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
        ]
        self.memory.add(messages, user_id=user_id)

    def search(self, query: str, user_id: str = "default", limit: int = 5) -> list[str]:
        """Retrieve relevant memories for context injection."""
        results = self.memory.search(query, user_id=user_id, limit=limit)
        return [r["memory"] for r in results.get("results", [])]

    def get_all(self, user_id: str = "default") -> list[str]:
        """Get all stored memories."""
        results = self.memory.get_all(user_id=user_id)
        return [r["memory"] for r in results.get("results", [])]
```

**Note on async:** mem0's API is synchronous. If this blocks the event loop, wrap calls with `asyncio.to_thread()` in the orchestrator. Don't over-engineer this for the hackathon — mem0 calls are fast (~200ms).

### 3. `memory/capture.py`

SQLite full interaction logger. Every interaction is logged verbatim.

```python
import os
import json
import sqlite3
from datetime import datetime
from memory.types import InteractionRecord

class CaptureLog:
    def __init__(self, db_path: str = "~/.voxaos/capture.db"):
        db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                user_transcript TEXT NOT NULL,
                llm_messages TEXT,
                tool_calls TEXT,
                assistant_response TEXT NOT NULL,
                skill_used TEXT,
                latency_ms TEXT
            )
        """)
        self.conn.commit()

    def log(self, record: InteractionRecord):
        """Log a complete interaction record."""
        self.conn.execute(
            """INSERT INTO interactions
               (session_id, timestamp, user_transcript, llm_messages,
                tool_calls, assistant_response, skill_used, latency_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.session_id,
                record.timestamp.isoformat(),
                record.user_transcript,
                json.dumps(record.llm_messages),
                json.dumps(record.tool_calls),
                record.assistant_response,
                record.skill_used,
                json.dumps(record.latency_ms),
            ),
        )
        self.conn.commit()

    def get_recent(self, limit: int = 10) -> list[dict]:
        """Get recent interactions for debugging."""
        cursor = self.conn.execute(
            "SELECT * FROM interactions ORDER BY id DESC LIMIT ?", (limit,)
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self):
        self.conn.close()
```

### 4. `memory/__init__.py`

Convenience factory:

```python
from core.config import Config
from memory.learning import LearningMemory
from memory.capture import CaptureLog

def create_memory(config: Config) -> tuple[LearningMemory | None, CaptureLog | None]:
    """Create memory components based on config."""
    learning = None
    capture = None

    if config.memory.enabled and config.memory.learning.enabled:
        learning = LearningMemory(config.memory, config.llm)

    if config.memory.enabled and config.memory.capture.enabled:
        capture = CaptureLog(config.memory.capture.db_path)

    return learning, capture
```

## Verification

```python
import asyncio
from core.config import load_config
from memory import create_memory

def test():
    config = load_config()
    learning, capture = create_memory(config)

    # Test learning memory
    if learning:
        learning.add("My name is Alex and I prefer Python", "Nice to meet you Alex!")
        results = learning.search("what's my name")
        print(f"Learning memory: {results}")

    # Test capture
    if capture:
        from memory.types import InteractionRecord
        from datetime import datetime
        record = InteractionRecord(
            session_id="test-001",
            timestamp=datetime.now(),
            user_transcript="hello",
            llm_messages=[{"role": "user", "content": "hello"}],
            tool_calls=[],
            assistant_response="Hi there!",
        )
        capture.log(record)
        recent = capture.get_recent(1)
        print(f"Capture: {recent}")
        capture.close()

test()
```

## Quality Gate

### Test file: `tests/test_memory.py`

```python
import pytest
from datetime import datetime
from memory.types import InteractionRecord
from memory.capture import CaptureLog
from memory import create_memory
from core.config import load_config

@pytest.fixture
def capture_log(tmp_path):
    db_path = str(tmp_path / "test_capture.db")
    log = CaptureLog(db_path)
    yield log
    log.close()

def test_capture_log_init(capture_log):
    """DB should initialize with interactions table."""
    cursor = capture_log.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='interactions'"
    )
    assert cursor.fetchone() is not None

def test_capture_log_write_read(capture_log):
    record = InteractionRecord(
        session_id="test-001",
        timestamp=datetime.now(),
        user_transcript="hello",
        llm_messages=[{"role": "user", "content": "hello"}],
        tool_calls=[],
        assistant_response="Hi there!",
    )
    capture_log.log(record)
    recent = capture_log.get_recent(1)
    assert len(recent) == 1
    assert recent[0]["user_transcript"] == "hello"
    assert recent[0]["assistant_response"] == "Hi there!"

def test_capture_log_multiple(capture_log):
    for i in range(5):
        record = InteractionRecord(
            session_id="test-002",
            timestamp=datetime.now(),
            user_transcript=f"msg {i}",
            llm_messages=[],
            tool_calls=[],
            assistant_response=f"resp {i}",
        )
        capture_log.log(record)
    recent = capture_log.get_recent(3)
    assert len(recent) == 3

def test_interaction_record_defaults():
    record = InteractionRecord(
        session_id="s", timestamp=datetime.now(),
        user_transcript="u", llm_messages=[], tool_calls=[],
        assistant_response="a",
    )
    assert record.skill_used is None
    assert record.latency_ms == {}

def test_create_memory_disabled():
    config = load_config()
    config.memory.enabled = False
    learning, capture = create_memory(config)
    assert learning is None
    assert capture is None
```

### Run

```bash
ruff check memory/ tests/test_memory.py
mypy memory/types.py memory/capture.py
pytest tests/test_memory.py -v
```

| Check | Command | Pass? |
|-------|---------|-------|
| Lint clean | `ruff check memory/ tests/test_memory.py` | |
| Types pass | `mypy memory/types.py memory/capture.py` | |
| SQLite CRUD | `pytest tests/test_memory.py -v` | |
| Disabled config returns None | `pytest tests/test_memory.py::test_create_memory_disabled` | |

**Note:** Learning memory (mem0) tests require `MISTRAL_API_KEY` — these are tested manually in verification, not in the gate. The capture log tests run offline.

## Design reference

See PLAN.md section: "Memory System" — full architecture diagram, mem0 config, SQLite schema, orchestrator integration pattern
