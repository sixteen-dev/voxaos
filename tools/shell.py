import asyncio


async def run_shell(command: str, timeout: int = 30) -> str:
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return f"Command timed out after {timeout}s"

    output = ""
    if stdout:
        output += stdout.decode(errors="replace")
    if stderr:
        output += ("\n" if output else "") + stderr.decode(errors="replace")
    return output or "(no output)"
