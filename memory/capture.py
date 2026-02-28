import json
import os
import sqlite3

from memory.types import InteractionRecord


class CaptureLog:
    def __init__(self, db_path: str = "~/.voxaos/capture.db"):
        db_path = os.path.expanduser(db_path)
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self) -> None:
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

    def log(self, record: InteractionRecord) -> None:
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
        cursor = self.conn.execute("SELECT * FROM interactions ORDER BY id DESC LIMIT ?", (limit,))
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()
