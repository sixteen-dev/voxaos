from core.config import Config

CORE_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Execute a shell command on the host system. Returns stdout and stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 30)",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative file path to read",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates parent directories if needed. Overwrites existing file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to write to",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories at the given path with sizes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (default: current directory)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files matching a glob pattern recursively.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g. '**/*.py', '*.txt')",
                    },
                    "path": {
                        "type": "string",
                        "description": "Base directory to search from (default: current directory)",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "List top running processes sorted by CPU or memory usage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sort_by": {
                        "type": "string",
                        "enum": ["cpu", "memory"],
                        "description": "Sort by 'cpu' or 'memory' (default: cpu)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_process",
            "description": "Terminate a process by its PID. Use with caution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {
                        "type": "integer",
                        "description": "Process ID to kill",
                    },
                },
                "required": ["pid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launch_app",
            "description": "Launch an application or command in the background.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to launch (e.g. 'firefox', 'code .')",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in the default web browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to open",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo. Returns titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "Fetch a URL and extract readable text content from the page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to fetch and extract text from",
                    },
                },
                "required": ["url"],
            },
        },
    },
]

HA_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "ha_get_states",
            "description": "Get all Home Assistant entity states, optionally filtered by domain (e.g. 'light', 'sensor', 'switch').",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter (e.g. 'light', 'sensor', 'climate')",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ha_get_state",
            "description": "Get the current state and attributes of a single Home Assistant entity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Entity ID (e.g. 'sensor.temperature', 'light.living_room')",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ha_set_state",
            "description": "Update the state of a Home Assistant entity via POST /api/states/<entity_id>.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Entity ID to update",
                    },
                    "state": {
                        "type": "string",
                        "description": "New state value",
                    },
                    "attributes": {
                        "type": "object",
                        "description": "Optional attributes to set",
                    },
                },
                "required": ["entity_id", "state"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ha_call_service",
            "description": "Call a Home Assistant service to control a device (e.g. turn on light, set thermostat).",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Service domain (e.g. 'light', 'climate', 'switch')",
                    },
                    "service": {
                        "type": "string",
                        "description": "Service name (e.g. 'turn_on', 'turn_off', 'set_temperature')",
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "Target entity ID",
                    },
                    "data": {
                        "type": "object",
                        "description": "Optional service data (e.g. {\"brightness\": 200, \"color_name\": \"blue\"})",
                    },
                },
                "required": ["domain", "service", "entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ha_get_history",
            "description": "Get state history for a Home Assistant entity over a time period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Entity ID to get history for",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours of history to fetch (default: 24)",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
]


def get_tools(config: Config) -> list[dict]:
    """Return all tool definitions, gating HA tools on config."""
    tools = list(CORE_TOOLS)
    if config.home_assistant.enabled:
        tools.extend(HA_TOOLS)
    return tools
