from datetime import datetime

import pytest

from core.config import load_config
from memory import create_memory
from memory.capture import CaptureLog
from memory.types import InteractionRecord


@pytest.fixture
def capture_log(tmp_path):
    db_path = str(tmp_path / "test_capture.db")
    log = CaptureLog(db_path)
    yield log
    log.close()


def test_capture_log_init(capture_log):
    cursor = capture_log.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interactions'")
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


def test_capture_log_ordering(capture_log):
    for i in range(3):
        record = InteractionRecord(
            session_id="test-003",
            timestamp=datetime.now(),
            user_transcript=f"msg {i}",
            llm_messages=[],
            tool_calls=[],
            assistant_response=f"resp {i}",
        )
        capture_log.log(record)
    recent = capture_log.get_recent(3)
    # Most recent first (DESC order)
    assert recent[0]["user_transcript"] == "msg 2"
    assert recent[2]["user_transcript"] == "msg 0"


def test_interaction_record_defaults():
    record = InteractionRecord(
        session_id="s",
        timestamp=datetime.now(),
        user_transcript="u",
        llm_messages=[],
        tool_calls=[],
        assistant_response="a",
    )
    assert record.skill_used is None
    assert record.latency_ms == {}


def test_interaction_record_with_skill():
    record = InteractionRecord(
        session_id="s",
        timestamp=datetime.now(),
        user_transcript="debug my system",
        llm_messages=[],
        tool_calls=[{"name": "run_shell", "args": {"command": "top"}, "result": "..."}],
        assistant_response="System looks fine",
        skill_used="system-debug",
        latency_ms={"stt": 120.5, "llm": 340.0},
    )
    assert record.skill_used == "system-debug"
    assert record.latency_ms["stt"] == 120.5


def test_create_memory_disabled():
    config = load_config()
    config.memory.enabled = False
    learning, capture = create_memory(config)
    assert learning is None
    assert capture is None
