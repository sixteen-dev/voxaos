from typing import Any

import psutil


async def list_processes(sort_by: str = "cpu") -> str:
    procs: list[dict[str, Any]] = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info: dict[str, Any] = p.info  # type: ignore[assignment]
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    procs.sort(key=lambda x: x.get(key, 0) or 0, reverse=True)

    lines = [f"{'PID':<8} {'CPU%':<8} {'MEM%':<8} {'NAME'}"]
    for proc in procs[:15]:
        lines.append(f"{proc['pid']:<8} {proc.get('cpu_percent', 0):<8.1f} {proc.get('memory_percent', 0):<8.1f} {proc['name']}")
    return "\n".join(lines)


async def kill_process(pid: int) -> str:
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
