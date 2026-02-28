import glob as glob_module
import os

import aiofiles


async def read_file(path: str) -> str:
    path = os.path.expanduser(path)
    async with aiofiles.open(path) as f:
        content: str = await f.read()
        return content


async def write_file(path: str, content: str) -> str:
    path = os.path.expanduser(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    async with aiofiles.open(path, "w") as f:
        await f.write(content)
    return f"Written {len(content)} bytes to {path}"


async def list_directory(path: str = ".") -> str:
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
    path = os.path.expanduser(path)
    full_pattern = os.path.join(path, pattern)
    matches = glob_module.glob(full_pattern, recursive=True)
    return "\n".join(sorted(matches)) or "(no matches)"
