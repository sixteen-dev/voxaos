# VoxaOS

A voice-controlled operating system layer. Speak to it — it understands, acts, and responds.

Built in 24 hours for a hackathon. Runs shell commands, manages files, launches apps, searches the web, controls smart home devices, and remembers what you tell it — all through natural voice conversation.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser (Terminal-style Web UI)                        │
│  ┌──────────┐  WebSocket  ┌──────────┐                  │
│  │ Mic Input │────────────▶│ Audio Out │                 │
│  └──────────┘  (binary)   └──────────┘                  │
└────────────────────┬──────────────▲──────────────────────┘
                     │              │
              ┌──────▼──────────────┴──────┐
              │  FastAPI Server             │
              │                            │
              │  Audio Pipeline            │
              │  (VAD → STT → LLM → TTS)  │
              │                            │
              │  ┌────────────────────┐    │
              │  │ Silero VAD         │    │
              │  │ (voice detection)  │    │
              │  └────────┬───────────┘    │
              │           ▼                │
              │  ┌────────────────────┐    │
              │  │ Mistral Voxtral    │    │
              │  │ (speech-to-text)   │    │
              │  └────────┬───────────┘    │
              │           ▼                │
              │  ┌────────────────────┐    │
              │  │ Mistral Nemo 12B   │    │
              │  │ (LLM + tool calls) │    │
              │  └────────┬───────────┘    │
              │           ▼                │
              │  ┌────────────────────┐    │
              │  │ Tool Executor      │    │
              │  │ (shell, files,     │    │
              │  │  web, smart home)  │    │
              │  └────────┬───────────┘    │
              │           ▼                │
              │  ┌────────────────────┐    │
              │  │ NVIDIA Riva TTS    │    │
              │  │ (text-to-speech)   │    │
              │  └────────────────────┘    │
              └────────────────────────────┘
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **STT** | Mistral Voxtral | Speech-to-text transcription |
| **LLM** | Mistral Nemo 12B | Language understanding + tool calling |
| **TTS** | NVIDIA Riva NIM | Text-to-speech synthesis |
| **VAD** | Silero VAD | Voice activity detection (CPU) |
| **Memory** | mem0 + Qdrant | Persistent learning across sessions |
| **Capture** | SQLite | Full interaction logging |
| **Server** | FastAPI + uvicorn | Async WebSocket server |
| **UI** | Vanilla HTML/JS/CSS | Zero build step, terminal aesthetic |
| **Tools** | asyncio subprocess, psutil, aiofiles, DuckDuckGo | OS operations |

## Features

- **Voice pipeline**: Push-to-talk or continuous VAD-based detection
- **Tool calling**: Shell commands, file CRUD, process management, web search, app launching
- **Skills system**: Context-aware skill selection (system debug, web research, deploy, project setup, etc.)
- **Memory**: Remembers facts across sessions via vector search, full interaction history in SQLite
- **Home Assistant**: Optional smart home control (lights, climate, scenes)
- **Risk classification**: Dangerous commands (rm -rf, shutdown, etc.) are blocked or require confirmation
- **Self-demo**: Say "demo yourself" and VoxaOS walks through its own capabilities
- **Latency profiling**: Per-stage timing (STT, LLM, TTS) shown after each response
- **Error recovery**: Graceful handling of API failures, empty transcripts, TTS errors

## Project Structure

```
voxaos/
├── main.py                   # Entry point (server or --text REPL)
├── setup.sh                  # One-click install
├── config/default.toml       # All settings (models, ports, API keys)
├── core/
│   ├── config.py             # Pydantic config from TOML
│   ├── types.py              # PipelineState, ToolCall, Response, etc.
│   ├── context.py            # Conversation history + env context
│   └── orchestrator.py       # The brain: memory → skill → LLM → tools → response
├── llm/
│   ├── client.py             # AsyncOpenAI client (API + local vLLM)
│   ├── prompts.py            # System prompt builder
│   └── tools.py              # OpenAI function schema generation
├── voice/
│   ├── vad.py                # Silero VAD wrapper
│   ├── stt.py                # STT engine (Mistral API / local)
│   ├── tts.py                # TTS engine (NVIDIA API / local)
│   └── pipeline.py           # State machine: IDLE → LISTENING → PROCESSING → SPEAKING
├── tools/
│   ├── executor.py           # Central dispatcher with risk classification
│   ├── shell.py              # Async shell execution
│   ├── filesystem.py         # File CRUD via aiofiles
│   ├── process.py            # Process management via psutil
│   ├── launcher.py           # App launching + URL opening
│   ├── web_search.py         # DuckDuckGo search + page fetching
│   └── home_assistant.py     # Home Assistant REST API
├── skills/
│   ├── loader.py             # YAML frontmatter .md parser
│   ├── selector.py           # LLM-based skill selection
│   └── *.md                  # Skill definitions (7 starter skills)
├── memory/
│   ├── learning.py           # mem0 + Qdrant vector memory
│   ├── capture.py            # SQLite interaction log
│   └── types.py              # InteractionRecord dataclass
├── server/
│   ├── app.py                # FastAPI with WebSocket endpoint
│   └── audio_handler.py      # WebSocket protocol handler
├── ui/
│   ├── index.html            # Single-page app
│   ├── style.css             # Dark terminal theme
│   └── app.js                # Mic capture, WebSocket, audio playback
└── tests/                    # 84 tests across all modules
```

## Prerequisites

- **Python 3.11+**
- **uv** (package manager) — [install](https://astral.sh/uv)
- **API keys** (for API mode):
  - `MISTRAL_API_KEY` — for STT (Voxtral) and LLM (Mistral Nemo)
  - `NVIDIA_API_KEY` — for TTS (Riva NIM)

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url> && cd voxaos
./setup.sh
```

Or manually:

```bash
uv sync
mkdir -p ~/.voxaos/memory ~/.voxaos/models
```

### 2. Set API keys

Create a `.env` file in the project root:

```bash
MISTRAL_API_KEY=your-mistral-key-here
NVIDIA_API_KEY=your-nvidia-key-here
```

Or export them directly:

```bash
export MISTRAL_API_KEY=your-mistral-key-here
export NVIDIA_API_KEY=your-nvidia-key-here
```

### 3. Start the server

```bash
uv run python main.py
```

Open **http://localhost:7860** in your browser.

### 4. Use it

- **Text input**: Type a command in the text box and press Enter
- **Voice input**: Hold the spacebar (or hold the mic button) and speak, release to process
- **Try these**:
  - "What time is it?"
  - "List files in /tmp"
  - "Create a file called hello.py with a fibonacci function"
  - "Search the web for the latest Python release"
  - "Demo yourself"

## Testing Locally

### Run the full test suite

```bash
# Install dev dependencies
uv sync --extra dev

# Lint
uv run ruff check core/ llm/ tools/ skills/ memory/ server/ tests/ main.py

# Type check
uv run mypy core/config.py core/types.py core/context.py llm/client.py \
     llm/tools.py tools/executor.py memory/types.py memory/capture.py \
     server/audio_handler.py

# Run all 84 tests
uv run pytest tests/ -v
```

### Test individual modules

```bash
# Config and types (11 tests)
uv run pytest tests/test_config.py -v

# LLM client and tool schemas (11 tests)
uv run pytest tests/test_llm.py -v

# Tool executor and all tools (16 tests)
uv run pytest tests/test_tools.py -v

# Skills system (7 tests)
uv run pytest tests/test_skills.py -v

# Memory system (7 tests)
uv run pytest tests/test_memory.py -v

# Orchestrator (7 tests)
uv run pytest tests/test_orchestrator.py -v

# Voice pipeline (11 tests)
uv run pytest tests/test_voice.py -v

# Server and WebSocket handler (14 tests)
uv run pytest tests/test_server.py -v
```

### Text REPL mode (no browser needed)

```bash
uv run python main.py --text
```

This starts an interactive text-only REPL — useful for testing the orchestrator, tools, and skills without needing a browser or microphone.

### Manual end-to-end testing

1. Start the server: `uv run python main.py`
2. Check health: `curl http://localhost:7860/health`
3. Open browser: `http://localhost:7860`
4. Verify green connection dot in the header
5. Type "hello" in the text box — should get a response
6. Try "list files in /tmp" — should see tool execution
7. Try "demo yourself" — triggers the self-demo skill

### Testing without API keys

The unit tests don't require API keys — they use mocks. For end-to-end testing with the actual LLM, STT, and TTS, you need valid API keys set.

## Configuration

All settings live in `config/default.toml`. Key sections:

| Section | What it controls |
|---------|-----------------|
| `[mode]` | `api` (cloud APIs) or `local` (self-hosted models) |
| `[server]` | Host and port (default: `0.0.0.0:7860`) |
| `[stt]` | Speech-to-text backend and API endpoint |
| `[llm]` | LLM backend, model, max tool iterations |
| `[tts]` | Text-to-speech backend, voice selection |
| `[vad]` | Voice detection threshold and timing |
| `[tools]` | Shell timeout, output limits, blocked commands |
| `[memory]` | Enable/disable learning memory and capture log |
| `[home_assistant]` | Optional HA integration (disabled by default) |
| `[context]` | Conversation history length |

## Modes

### API Mode (default)

Uses cloud APIs — works on any machine with internet:
- STT: Mistral Voxtral API
- LLM: Mistral Nemo API
- TTS: NVIDIA Riva NIM API

### Local Mode (requires GPU)

For self-hosted inference on NVIDIA L40S or similar:
- STT: Voxtral Realtime (local)
- LLM: Mistral Nemo 12B via vLLM
- TTS: NVIDIA NeMo FastPitch + HiFi-GAN

Set `backend = "local"` in each section of `config/default.toml`.

## Safety

- **Blocked commands**: `rm -rf /`, `mkfs`, `dd if=/dev`, `shutdown`, `reboot`, fork bombs, etc.
- **Risk classification**: Tools are classified as SAFE, MODERATE, or DANGEROUS
- **Shell timeout**: All commands capped at 30 seconds
- **Output truncation**: Command output limited to 4096 chars
- **Confirmation required**: Dangerous operations need explicit user approval
