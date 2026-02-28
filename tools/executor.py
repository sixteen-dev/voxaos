import re
from collections.abc import Callable, Coroutine
from typing import Any

from core.config import ToolsConfig
from core.types import RiskLevel, ToolCall, ToolResult

# Risk classification rules
RISK_MAP: dict[str, RiskLevel] = {
    "read_file": RiskLevel.SAFE,
    "list_directory": RiskLevel.SAFE,
    "search_files": RiskLevel.SAFE,
    "list_processes": RiskLevel.SAFE,
    "web_search": RiskLevel.SAFE,
    "fetch_page": RiskLevel.SAFE,
    "ha_get_states": RiskLevel.SAFE,
    "ha_get_state": RiskLevel.SAFE,
    "ha_get_history": RiskLevel.SAFE,
    "write_file": RiskLevel.MODERATE,
    "launch_app": RiskLevel.MODERATE,
    "open_url": RiskLevel.MODERATE,
    "ha_set_state": RiskLevel.MODERATE,
    "ha_call_service": RiskLevel.MODERATE,
    "run_shell": RiskLevel.MODERATE,  # upgraded to DANGEROUS dynamically
    "kill_process": RiskLevel.DANGEROUS,
}

# Shell commands that upgrade run_shell to DANGEROUS
DANGEROUS_PATTERNS: list[str] = [
    r"rm\s+-rf\s+/",
    r"mkfs",
    r"dd\s+if=/dev",
    r"shutdown",
    r"reboot",
    r":\(\)\{\s*:\|:&\s*\};:",
    r"chmod\s+-R\s+777\s+/",
    r">\s*/dev/sda",
    r"rm\s+-rf\s+~",
    r"mv\s+/",
    r">\s*/etc/",
]

# Type alias for async handler functions
Handler = Callable[..., Coroutine[Any, Any, Any]]


class ToolExecutor:
    def __init__(self, config: ToolsConfig):
        self.config = config
        self._handlers: dict[str, Handler] = {}
        # Confirmation callback — set by server/orchestrator
        self.on_confirm_request: Callable[[ToolCall], Coroutine[Any, Any, bool]] | None = None

    def register(self, name: str, handler: Handler) -> None:
        self._handlers[name] = handler

    def classify_risk(self, tool_call: ToolCall) -> RiskLevel:
        base_risk = RISK_MAP.get(tool_call.name, RiskLevel.MODERATE)

        # Dynamic upgrade for shell commands
        if tool_call.name == "run_shell":
            command = tool_call.args.get("command", "")
            # Check blocked commands
            for blocked in self.config.blocked_commands:
                if blocked in command:
                    return RiskLevel.DANGEROUS
            # Check dangerous patterns
            for pattern in DANGEROUS_PATTERNS:
                if re.search(pattern, command):
                    return RiskLevel.DANGEROUS

        return base_risk

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        handler = self._handlers.get(tool_call.name)
        if not handler:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Unknown tool: {tool_call.name}",
                is_error=True,
            )

        risk = self.classify_risk(tool_call)

        # Gate dangerous operations
        if risk == RiskLevel.DANGEROUS and self.on_confirm_request:
            confirmed = await self.on_confirm_request(tool_call)
            if not confirmed:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    content="Operation cancelled by user.",
                )

        try:
            result = await handler(**tool_call.args)
            # Truncate long output
            if isinstance(result, str) and len(result) > self.config.output_max_chars:
                result = result[: self.config.output_max_chars] + "\n...(truncated)"
            return ToolResult(tool_call_id=tool_call.id, content=str(result))
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Error: {type(e).__name__}: {e}",
                is_error=True,
            )
