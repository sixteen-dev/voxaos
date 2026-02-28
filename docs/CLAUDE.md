# VoxaOS Development Guidelines

## Package Management
- **Always use `uv`** for package management. Never use `pip` directly.
  - Install: `uv sync` (or `uv sync --extra dev` for dev deps)
  - Add dep: `uv add <package>`
  - Run scripts: `uv run python main.py`
  - Run tests: `uv run pytest`
