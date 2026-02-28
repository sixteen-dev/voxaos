import os
import platform
import subprocess
from dataclasses import dataclass


@dataclass
class ConversationTurn:
    role: str  # "user" or "assistant"
    content: str


class ContextManager:
    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.history: list[ConversationTurn] = []

    def add_turn(self, role: str, content: str) -> None:
        self.history.append(ConversationTurn(role=role, content=content))
        if len(self.history) > self.max_history * 2:  # user+assistant pairs
            self.history = self.history[-(self.max_history * 2) :]

    def get_messages(self) -> list[dict]:
        return [{"role": t.role, "content": t.content} for t in self.history]

    def clear(self) -> None:
        self.history.clear()

    @staticmethod
    def build_env_context() -> str:
        lines = [
            f"- OS: {platform.system()} {platform.release()}",
            f"- Hostname: {platform.node()}",
            f"- Working directory: {os.getcwd()}",
            f"- User: {os.environ.get('USER', 'unknown')}",
            f"- Python: {platform.python_version()}",
        ]
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines.append(f"- GPU: {result.stdout.strip()}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            lines.append("- GPU: not available")
        return "\n".join(lines)
