# VoxaOS Implementation Tasks

## Task Order & Dependencies

```
01 Project Skeleton ─────┬──► 02 LLM Client ──┬──► 04 Skills System ──┐
                         │                     │                       │
                         │                     ├──► 03 Tool Executor ──┤
                         │                     │                       │
                         │                     └──► 05 Memory System ──┤
                         │                                             │
                         └─────────────────────────────────────────────┤
                                                                       │
                                                          06 Orchestrator
                                                                │
                                                          07 Voice Pipeline
                                                                │
                                                          08 FastAPI Server
                                                                │
                                                          09 Browser UI
                                                                │
                                                          10 Integration + Polish
```

## Task Summary

| # | Task | Depends On | Time Est. | Description |
|---|------|-----------|-----------|-------------|
| 01 | Project Skeleton | — | 30-45m | pyproject.toml, config system, types, directory structure |
| 02 | LLM Client | 01 | 45-60m | Async OpenAI SDK client, tool calling, prompts |
| 03 | Tool Executor | 01, 02 | 60-90m | Risk classification, all tool handlers (shell, fs, web, HA) |
| 04 | Skills System | 02 | 45-60m | Loader, LLM-based selector, all starter .md skill files |
| 05 | Memory System | 01, 02 | 30-45m | mem0 learning memory + SQLite capture log |
| 06 | Orchestrator | 02, 03, 04, 05 | 60-90m | Central brain: context → skill → LLM → tool loop → response |
| 07 | Voice Pipeline | 06 | 60-90m | Silero VAD + STT API + TTS API + state machine |
| 08 | FastAPI Server | 07 | 45-60m | WebSocket audio handler, REST endpoints |
| 09 | Browser UI | 08 | 60-90m | HTML/CSS/JS: mic capture, terminal log, push-to-talk |
| 10 | Integration | 01-09 | 60-90m | E2E testing, error recovery, demo prep, setup.sh |

**Total estimated: ~8-12 hours of implementation**

## Parallel Work

Tasks 03, 04, and 05 can be done in parallel after 02 is complete.

## Quality Gates

Every task includes a **Quality Gate** section with:
- **Test files** to create (`tests/test_*.py`)
- **Lint**: `ruff check` on all modified modules
- **Type check**: `mypy` on critical files
- **Unit tests**: `pytest` with specific test file
- **Gate checklist**: table of pass/fail items

Dev dependencies are defined in task 01's `pyproject.toml` under `[project.optional-dependencies] dev`:
```bash
pip install -e ".[dev]"  # installs ruff, pytest, pytest-asyncio, mypy
```

**Rule: Don't move to the next task until the current task's quality gate passes.**

## How to Use

Each task file contains:
- Exact files to create
- Code snippets and class structures
- Design decisions and rationale
- Quality gate with tests, lint, and type checks
- Verification steps to confirm it works
- References back to PLAN.md

Tell Claude: "Implement task 01 from docs/tasks/01-project-skeleton.md"
