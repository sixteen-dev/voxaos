import subprocess
import webbrowser


async def launch_app(command: str) -> str:
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Launched: {command} (PID {proc.pid})"
    except Exception as e:
        return f"Failed to launch: {e}"


async def open_url(url: str) -> str:
    webbrowser.open(url)
    return f"Opened {url}"
