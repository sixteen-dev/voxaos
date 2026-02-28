# Task 03: Tool Executor + All Tool Implementations

## Priority: 3
## Depends on: Task 01 (types), Task 02 (tool schemas)
## Estimated time: 60-90 min

## Objective

Build the tool executor with risk classification and all individual tool handlers. When the LLM returns a `tool_calls` array, the executor dispatches each call to the right handler, captures output, and returns results.

## What to create

### 1. `tools/executor.py`

Central dispatcher with risk classification.

```python
from core.types import ToolCall, ToolResult, RiskLevel
from core.config import ToolsConfig
import re

# Risk classification rules
RISK_MAP = {
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
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/", r"mkfs", r"dd\s+if=/dev", r"shutdown", r"reboot",
    r":\(\)\{\s*:\|:&\s*\};:", r"chmod\s+-R\s+777\s+/", r">\s*/dev/sda",
    r"rm\s+-rf\s+~", r"mv\s+/", r">\s*/etc/",
]

class ToolExecutor:
    def __init__(self, config: ToolsConfig):
        self.config = config
        self._handlers: dict[str, callable] = {}
        # Confirmation callback — set by server/orchestrator
        self.on_confirm_request = None

    def register(self, name: str, handler: callable):
        """Register a tool handler function."""
        self._handlers[name] = handler

    def classify_risk(self, tool_call: ToolCall) -> RiskLevel:
        """Determine risk level for a tool call."""
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
        """Execute a single tool call with risk gating."""
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
                    is_error=False,
                )

        try:
            result = await handler(**tool_call.args)
            # Truncate long output
            if isinstance(result, str) and len(result) > self.config.output_max_chars:
                result = result[:self.config.output_max_chars] + "\n...(truncated)"
            return ToolResult(tool_call_id=tool_call.id, content=str(result))
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Error: {type(e).__name__}: {str(e)}",
                is_error=True,
            )
```

### 2. `tools/shell.py`

```python
import asyncio

async def run_shell(command: str, timeout: int = 30) -> str:
    """Execute a shell command, return combined stdout+stderr."""
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return f"Command timed out after {timeout}s"

    output = ""
    if stdout:
        output += stdout.decode(errors="replace")
    if stderr:
        output += ("\n" if output else "") + stderr.decode(errors="replace")
    return output or "(no output)"
```

### 3. `tools/filesystem.py`

```python
import os
import glob as glob_module
import aiofiles

async def read_file(path: str) -> str:
    """Read file contents."""
    path = os.path.expanduser(path)
    async with aiofiles.open(path, "r") as f:
        return await f.read()

async def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates parent dirs if needed."""
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    async with aiofiles.open(path, "w") as f:
        await f.write(content)
    return f"Written {len(content)} bytes to {path}"

async def list_directory(path: str = ".") -> str:
    """List files and directories."""
    path = os.path.expanduser(path)
    entries = []
    for entry in sorted(os.scandir(path), key=lambda e: e.name):
        prefix = "[DIR] " if entry.is_dir() else "[FILE]"
        size = ""
        if entry.is_file():
            size = f" ({entry.stat().st_size} bytes)"
        entries.append(f"{prefix} {entry.name}{size}")
    return "\n".join(entries) or "(empty directory)"

async def search_files(pattern: str, path: str = ".") -> str:
    """Search for files matching a glob pattern."""
    path = os.path.expanduser(path)
    full_pattern = os.path.join(path, pattern)
    matches = glob_module.glob(full_pattern, recursive=True)
    return "\n".join(sorted(matches)) or "(no matches)"
```

### 4. `tools/process.py`

```python
import psutil

async def list_processes(sort_by: str = "cpu") -> str:
    """List top processes by CPU or memory usage."""
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = p.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = 'cpu_percent' if sort_by == "cpu" else 'memory_percent'
    procs.sort(key=lambda x: x.get(key, 0) or 0, reverse=True)

    lines = [f"{'PID':<8} {'CPU%':<8} {'MEM%':<8} {'NAME'}"]
    for p in procs[:15]:
        lines.append(f"{p['pid']:<8} {p.get('cpu_percent', 0):<8.1f} {p.get('memory_percent', 0):<8.1f} {p['name']}")
    return "\n".join(lines)

async def kill_process(pid: int) -> str:
    """Kill a process by PID."""
    try:
        p = psutil.Process(pid)
        name = p.name()
        p.terminate()
        p.wait(timeout=5)
        return f"Terminated process {name} (PID {pid})"
    except psutil.NoSuchProcess:
        return f"No process with PID {pid}"
    except psutil.TimeoutExpired:
        p.kill()
        return f"Force killed process (PID {pid})"
```

### 5. `tools/launcher.py`

```python
import subprocess
import webbrowser

async def launch_app(command: str) -> str:
    """Launch an application in the background."""
    try:
        proc = subprocess.Popen(
            command, shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return f"Launched: {command} (PID {proc.pid})"
    except Exception as e:
        return f"Failed to launch: {e}"

async def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    webbrowser.open(url)
    return f"Opened {url}"
```

### 6. `tools/web_search.py`

```python
from duckduckgo_search import DDGS
import httpx
from bs4 import BeautifulSoup

async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo. Returns titles + URLs + snippets."""
    results = DDGS().text(query, max_results=max_results)
    lines = []
    for r in results:
        lines.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")
    return "\n".join(lines) or "No results found."

async def fetch_page(url: str) -> str:
    """Fetch a URL and extract readable text content."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    # Remove script/style elements
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    # Collapse multiple newlines
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return "\n".join(lines[:200])  # First 200 lines
```

### 7. `tools/home_assistant.py`

```python
import os
import httpx
from datetime import datetime, timedelta
from core.config import HomeAssistantConfig

class HomeAssistantTools:
    def __init__(self, config: HomeAssistantConfig):
        self.config = config
        self.base_url = config.url
        token = os.environ.get(config.token_env, "")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def ha_get_states(self, domain: str = None) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/api/states", headers=self.headers)
            resp.raise_for_status()
            states = resp.json()
            if domain:
                states = [s for s in states if s["entity_id"].startswith(f"{domain}.")]
            lines = [f"{s['entity_id']}: {s['state']}" for s in states]
            return "\n".join(lines) or "No entities found."

    async def ha_get_state(self, entity_id: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/api/states/{entity_id}", headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            attrs = ", ".join(f"{k}={v}" for k, v in data.get("attributes", {}).items())
            return f"{entity_id}: {data['state']} ({attrs})"

    async def ha_set_state(self, entity_id: str, state: str, attributes: dict = None) -> str:
        payload = {"state": state}
        if attributes:
            payload["attributes"] = attributes
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/states/{entity_id}",
                headers=self.headers, json=payload,
            )
            resp.raise_for_status()
            return f"Set {entity_id} to {state}"

    async def ha_call_service(self, domain: str, service: str, entity_id: str, data: dict = None) -> str:
        payload = {"entity_id": entity_id, **(data or {})}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/services/{domain}/{service}",
                headers=self.headers, json=payload,
            )
            resp.raise_for_status()
            return f"Called {domain}.{service} on {entity_id}"

    async def ha_get_history(self, entity_id: str, hours: int = 24) -> str:
        start = (datetime.now() - timedelta(hours=hours)).isoformat()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/history/period/{start}",
                params={"filter_entity_id": entity_id},
                headers=self.headers,
            )
            resp.raise_for_status()
            history = resp.json()
            if not history or not history[0]:
                return "No history found."
            entries = history[0]
            lines = [f"{e['last_changed']}: {e['state']}" for e in entries[-20:]]
            return "\n".join(lines)
```

### 8. Wire everything together

Create a `tools/registry.py` or a function in `tools/__init__.py`:

```python
def register_all_tools(executor: ToolExecutor, config: Config):
    """Register all tool handlers with the executor."""
    from tools.shell import run_shell
    from tools.filesystem import read_file, write_file, list_directory, search_files
    from tools.process import list_processes, kill_process
    from tools.launcher import launch_app, open_url
    from tools.web_search import web_search, fetch_page

    executor.register("run_shell", run_shell)
    executor.register("read_file", read_file)
    executor.register("write_file", write_file)
    executor.register("list_directory", list_directory)
    executor.register("search_files", search_files)
    executor.register("list_processes", list_processes)
    executor.register("kill_process", kill_process)
    executor.register("launch_app", launch_app)
    executor.register("open_url", open_url)
    executor.register("web_search", web_search)
    executor.register("fetch_page", fetch_page)

    if config.home_assistant.enabled:
        ha = HomeAssistantTools(config.home_assistant)
        executor.register("ha_get_states", ha.ha_get_states)
        executor.register("ha_get_state", ha.ha_get_state)
        executor.register("ha_set_state", ha.ha_set_state)
        executor.register("ha_call_service", ha.ha_call_service)
        executor.register("ha_get_history", ha.ha_get_history)
```

## Verification

```python
import asyncio
from core.config import load_config
from core.types import ToolCall
from tools.executor import ToolExecutor
from tools import register_all_tools

async def test():
    config = load_config()
    executor = ToolExecutor(config.tools)
    register_all_tools(executor, config)

    # Test shell
    result = await executor.execute(ToolCall(id="1", name="run_shell", args={"command": "echo hello"}))
    print(f"Shell: {result.content}")

    # Test filesystem
    result = await executor.execute(ToolCall(id="2", name="list_directory", args={"path": "/tmp"}))
    print(f"Files: {result.content[:200]}")

    # Test risk classification
    dangerous = ToolCall(id="3", name="run_shell", args={"command": "rm -rf /"})
    print(f"Risk: {executor.classify_risk(dangerous)}")  # Should be DANGEROUS

asyncio.run(test())
```

## Quality Gate

### Test file: `tests/test_tools.py`

```python
import pytest
from core.types import ToolCall, RiskLevel
from core.config import load_config
from tools.executor import ToolExecutor
from tools import register_all_tools

@pytest.fixture
def executor():
    config = load_config()
    ex = ToolExecutor(config.tools)
    register_all_tools(ex, config)
    return ex

def test_risk_safe(executor):
    tc = ToolCall(id="1", name="list_directory", args={"path": "/tmp"})
    assert executor.classify_risk(tc) == RiskLevel.SAFE

def test_risk_moderate(executor):
    tc = ToolCall(id="2", name="write_file", args={"path": "/tmp/x", "content": "hi"})
    assert executor.classify_risk(tc) == RiskLevel.MODERATE

def test_risk_dangerous_rm(executor):
    tc = ToolCall(id="3", name="run_shell", args={"command": "rm -rf /"})
    assert executor.classify_risk(tc) == RiskLevel.DANGEROUS

def test_risk_dangerous_kill(executor):
    tc = ToolCall(id="4", name="kill_process", args={"pid": 1})
    assert executor.classify_risk(tc) == RiskLevel.DANGEROUS

def test_unknown_tool(executor):
    tc = ToolCall(id="5", name="nonexistent_tool", args={})
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(executor.execute(tc))
    assert result.is_error
    assert "Unknown tool" in result.content

@pytest.mark.asyncio
async def test_shell_echo(executor):
    tc = ToolCall(id="6", name="run_shell", args={"command": "echo hello"})
    result = await executor.execute(tc)
    assert "hello" in result.content
    assert not result.is_error

@pytest.mark.asyncio
async def test_list_directory(executor):
    tc = ToolCall(id="7", name="list_directory", args={"path": "/tmp"})
    result = await executor.execute(tc)
    assert not result.is_error

@pytest.mark.asyncio
async def test_write_read_file(executor, tmp_path):
    path = str(tmp_path / "test.txt")
    write = ToolCall(id="8", name="write_file", args={"path": path, "content": "hello world"})
    result = await executor.execute(write)
    assert not result.is_error

    read = ToolCall(id="9", name="read_file", args={"path": path})
    result = await executor.execute(read)
    assert "hello world" in result.content

@pytest.mark.asyncio
async def test_shell_timeout(executor):
    tc = ToolCall(id="10", name="run_shell", args={"command": "sleep 60", "timeout": 2})
    result = await executor.execute(tc)
    assert "timed out" in result.content.lower()

@pytest.mark.asyncio
async def test_web_search(executor):
    tc = ToolCall(id="11", name="web_search", args={"query": "python", "max_results": 1})
    result = await executor.execute(tc)
    assert not result.is_error
```

### Run

```bash
ruff check tools/ tests/test_tools.py
mypy tools/executor.py
pytest tests/test_tools.py -v
```

| Check | Command | Pass? |
|-------|---------|-------|
| Lint clean | `ruff check tools/ tests/test_tools.py` | |
| Types pass | `mypy tools/executor.py` | |
| Risk classification | `pytest tests/test_tools.py -k risk -v` | |
| Tool execution | `pytest tests/test_tools.py -k "not risk" -v` | |
| Blocked cmd denied | `rm -rf /` classified as DANGEROUS | |

## Design reference

See PLAN.md sections: "Tool Executor + Risk Classification", "Home Assistant Integration" (Tool + LLM Tool Schemas), "Safety Guardrails"
