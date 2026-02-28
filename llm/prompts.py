import os
import platform

SYSTEM_PROMPT = """You are VoxaOS, a voice-controlled operating system running on an NVIDIA L40S GPU.
You have direct access to the host Linux system through your tools.

Capabilities:
- Execute any shell command
- Read, write, search, and manage files
- Launch applications and manage processes
- Search the web and summarize pages

Rules:
- Be concise. The user is LISTENING to your response, not reading it. Keep answers under 3 sentences unless they ask for detail.
- Use tools proactively. If the user asks "what files are here", use list_directory. Don't guess.
- For destructive operations (delete, kill, overwrite), state what you're about to do and wait for confirmation.
- When reporting tool output, summarize it naturally. Don't read raw JSON or full file contents aloud.
- If a command fails, explain the error briefly and suggest a fix."""


def build_system_prompt(
    env_context: str = "",
    memory_context: str = "",
    skill_body: str = "",
) -> str:
    """Build the full system prompt with dynamic sections."""
    parts = [SYSTEM_PROMPT]

    if env_context:
        parts.append(f"\n\n## Current Environment\n{env_context}")

    if memory_context:
        parts.append(f"\n\n## Relevant Memories\n{memory_context}")

    if skill_body:
        parts.append(f"\n\n## Active Skill Instructions\n{skill_body}")

    return "\n".join(parts)


def build_env_context() -> str:
    """Gather current environment info."""
    return (
        f"- OS: {platform.system()} {platform.release()}\n"
        f"- Hostname: {platform.node()}\n"
        f"- Working directory: {os.getcwd()}\n"
        f"- User: {os.environ.get('USER', 'unknown')}\n"
        f"- Python: {platform.python_version()}"
    )
