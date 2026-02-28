# Task 10: Integration Testing + Polish + Demo Prep

## Priority: 10
## Depends on: All previous tasks (01-09)
## Estimated time: 60-90 min

## Objective

End-to-end integration testing, error recovery, latency profiling, and demo preparation. Make sure the full pipeline works reliably for a hackathon demo.

## What to do

### 1. End-to-End Testing

Run through these test scenarios via the browser UI:

**Basic tool calls (no skill):**
- "What time is it?" → should use run_shell with `date`
- "List files in /tmp" → should use list_directory tool
- "Create a file called test.py with hello world" → should use write_file
- "Now read that file back" → should use read_file (tests conversation continuity)
- "What processes are using the most CPU?" → should use list_processes

**Skill-triggered multi-step:**
- "Debug why the system feels slow" → should activate system-debug skill, run multiple commands
- "Research the latest Python release" → should activate web-research skill, search + fetch + summarize
- "Set up a new Python project called myapp" → should activate project-setup skill

**Memory:**
- "My favorite language is Rust" → should be stored
- (new session or later) "What's my favorite language?" → should recall from mem0

**Self-demo:**
- "Demo yourself" → should activate self-demo skill, walk through all capabilities

**Edge cases:**
- Empty input → should handle gracefully
- Very long input → should not crash
- Tool that fails (e.g., read nonexistent file) → should return error gracefully
- Multiple rapid inputs → should queue or reject cleanly
- Network failure during API call → should show error in UI, not crash

### 2. Error Recovery

Add error handling where missing:

- **LLM API failure:** Catch connection errors, timeouts, rate limits. Show user-friendly message: "I'm having trouble connecting to my brain. Try again in a moment."
- **STT failure:** If transcription returns empty or fails, say "I didn't catch that. Could you repeat?"
- **TTS failure:** If synthesis fails, still return the text response in the UI (just no audio)
- **Tool failure:** Already handled by executor (returns error ToolResult), but verify LLM handles errors gracefully
- **WebSocket disconnect:** Auto-reconnect in browser JS with exponential backoff
- **Memory failure:** Already wrapped in try/except in orchestrator — verify it doesn't block the pipeline

### 3. Latency Profiling

Add timing to each stage and display in the UI:

```python
# Already in orchestrator — verify these are populated:
# timing["memory_search"], timing["skill_select"], timing["llm_total"]

# Add to voice pipeline:
# timing["vad"], timing["stt"], timing["tts"]
# timing["total"] = sum of all

# Display in UI:
# After each response, show: "STT: 1.2s | LLM: 0.8s | TTS: 0.5s | Total: 2.5s"
```

Target: < 4s total for API mode, < 2s for local mode.

### 4. Setup Script

Create `setup.sh` for one-click installation:

```bash
#!/bin/bash
set -e

echo "=== VoxaOS Setup ==="

# Check Python
python3 --version || { echo "Python 3.11+ required"; exit 1; }

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install deps
pip install -e .

# Create data directories
mkdir -p ~/.voxaos/memory
mkdir -p ~/.voxaos/models

# Check for API keys
if [ -z "$MISTRAL_API_KEY" ]; then
    echo "WARNING: MISTRAL_API_KEY not set. Set it for STT + LLM."
fi
if [ -z "$NVIDIA_API_KEY" ]; then
    echo "WARNING: NVIDIA_API_KEY not set. Set it for TTS."
fi

echo ""
echo "=== Setup complete ==="
echo "Run: source .venv/bin/activate && python main.py"
```

### 5. Demo Script

Prepare a rehearsed demo flow for judges. Write this as `docs/DEMO_SCRIPT.md`:

```markdown
# VoxaOS Demo Script (2-3 minutes)

## Opening (10s)
"This is VoxaOS — a voice-controlled operating system built in 24 hours."

## Auto-Demo (60-90s)
Say: "VoxaOS, demo yourself"
→ System runs through self-demo skill automatically
→ Shows system awareness, file ops, code execution, web search, memory

## Interactive (30-60s)
Pick 2-3 of these based on audience reaction:
- "Turn on the living room lights" (if HA is connected)
- "What do you remember about me?" (shows memory)
- "Create a Python script that generates the Fibonacci sequence and run it"

## Closing (10s)
"Built with Mistral for the brain, NVIDIA for the voice, and mem0 for memory.
All open source, all running in the cloud."
```

### 6. README.md

Create a basic README with:
- One-line description
- Architecture diagram (copy from PLAN.md)
- Quick start instructions (setup.sh, API keys, python main.py)
- Tech stack list
- Screenshot placeholder

## Verification

Full checklist — every item must pass:

| # | Test | Pass? |
|---|------|-------|
| 1 | `python main.py` starts without errors | |
| 2 | `curl localhost:7860/health` returns ok | |
| 3 | Browser loads UI at localhost:7860 | |
| 4 | Text input "hello" returns response | |
| 5 | Push-to-talk captures audio + returns transcript | |
| 6 | TTS audio plays in browser | |
| 7 | Tool calls work (list files, run shell) | |
| 8 | Skills activate correctly (system-debug, web-research) | |
| 9 | Self-demo runs through all acts | |
| 10 | Memory persists across interactions | |
| 11 | Error on bad tool doesn't crash server | |
| 12 | Latency < 4s for API mode | |
| 13 | WebSocket reconnects after disconnect | |

## Quality Gate (Full Suite)

Task 10 is the final gate — run the entire quality suite across all modules.

### Full lint + type check + test suite

```bash
# Lint everything
ruff check core/ llm/ tools/ skills/ memory/ server/ tests/ main.py

# Type check critical modules
mypy core/config.py core/types.py core/context.py \
     llm/client.py llm/tools.py \
     tools/executor.py \
     memory/types.py memory/capture.py \
     server/audio_handler.py

# Run all tests
pytest tests/ -v --tb=short

# Test count sanity check — should have at least 25 tests across all files
pytest tests/ --co -q | tail -1
```

### Final gate checklist

| # | Check | Command | Pass? |
|---|-------|---------|-------|
| 1 | Zero lint errors | `ruff check` exits 0 | |
| 2 | Types clean | `mypy` exits 0 | |
| 3 | All unit tests pass | `pytest tests/ -v` all green | |
| 4 | Server starts clean | `python main.py` no tracebacks | |
| 5 | Health returns ok | `curl localhost:7860/health` | |
| 6 | UI loads | Browser opens without console errors | |
| 7 | Text input roundtrip | "hello" → response in UI | |
| 8 | Tool execution works | "list files in /tmp" → tool output | |
| 9 | Skills activate | "debug system" → system-debug skill | |
| 10 | Self-demo runs | "demo yourself" → all 6 acts execute | |
| 11 | Memory persists | Store + recall works across inputs | |
| 12 | Error handling | Bad tool doesn't crash server | |
| 13 | Latency < 4s | API mode response time | |

## Design reference

See PLAN.md sections: Phase 5 (Polish + Demo Prep), "Verification Plan", "Safety Guardrails"
