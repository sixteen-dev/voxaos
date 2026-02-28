# VoxaOS - Local Voice OS | Hackathon Build Plan

## Context

Building a voice-controlled OS layer for a 24-hour hackathon. The system takes voice input, transcribes it, routes to an LLM with tool-calling capabilities, executes OS operations (shell, file ops, app launching, web research), and responds with synthesized speech. Hosted on NVIDIA L40S (48GB VRAM). Phase 2 (post-hackathon) adds agent swarms.

**Stack (locked):** Mistral Voxtral Realtime (STT) + Mistral Nemo 12B (LLM brain via vLLM) + NVIDIA NeMo TTS (voice output)

**Prior art:** Design patterns informed by `voice-os` project (`/home/sujshe/src/voice-os/`). We're reimplementing from scratch in our stack, not copying code.

---

## Design Patterns from voice-os

Key architectural patterns we're adopting and reimplementing:

### 1. Orchestrator Pattern
**Source design:** `voice-os/src/voice_os/core/orchestrator.py`

Central coordinator that owns the full request lifecycle:
```
build_context() → route_to_llm() → tool_call_loop() → return_response()
```
- Assembles system prompt with dynamic context (environment info, conversation history)
- Runs a multi-round tool calling loop: LLM returns tool calls → execute → feed results back → repeat until LLM gives final text answer
- Configurable max iterations (prevent runaway loops)
- Streaming support via async iterators yielding chunks

**Our adaptation:** Same pattern, but tool calling goes through vLLM's OpenAI-compatible endpoint with Mistral Nemo instead of Claude API. Fully local, no API keys.

### 2. Tool Executor + Risk Classification
**Source design:** `voice-os/src/voice_os/system/tool_executor.py`, `confirmation.py`

Two-layer tool execution:
- **Risk classifier:** Categorizes every tool call as `safe` / `moderate` / `dangerous` based on tool name + input args (e.g., `rm` in a shell command → dangerous)
- **Confirmation gate:** Dangerous ops require user confirmation before execution; safe ops auto-execute
- **Dispatcher:** Maps tool name → handler function, captures output, handles errors, truncates long output

**Our adaptation:** Same pattern. For hackathon, auto-confirm safe+moderate, only gate dangerous. Confirmation happens via WebSocket message to browser UI.

### 3. Declarative Tool Definitions
**Source design:** `voice-os/src/voice_os/llm/tools.py`

Tools defined as data structures with OpenAI function-calling JSON schemas:
```python
tools = [
    {"name": "run_shell", "description": "...", "parameters": {"command": {"type": "string"}}},
    ...
]
```
Passed directly to LLM in the API call. LLM returns structured `tool_calls` with name + args.

**Our adaptation:** Same format. vLLM with Mistral Nemo supports OpenAI function calling format natively.

### 4. Voice Pipeline State Machine
**Source design:** `voice-os/src/voice_os/voice/pipeline.py`

Pipeline states: `IDLE → LISTENING → PROCESSING → SPEAKING → IDLE`
- VAD (Silero) detects speech start/end in audio stream
- Buffers audio during speech, sends to STT on silence
- Prevents barge-in during TTS playback (or allows it with interrupt)
- Latency tracking at each stage

**Our adaptation:** Same state machine, but audio comes from browser WebSocket instead of local mic. VAD runs server-side on incoming audio chunks.

### 5. Context Manager with Conversation History
**Source design:** `voice-os/src/voice_os/core/context.py`

- Maintains rolling conversation history (last N exchanges)
- Builds context section injected into system prompt
- Includes environment info (OS, cwd, hostname)

**Our adaptation:** Same pattern. Skip the macOS-specific context (active window, clipboard) since we're on a Linux cloud GPU. Add system metrics (CPU, RAM, GPU usage) instead.

### 6. Pydantic Config
**Source design:** `voice-os/src/voice_os/config.py`

Nested Pydantic models loaded from TOML:
```python
class Config(BaseModel):
    llm: LLMConfig
    stt: STTConfig
    tts: TTSConfig
    tools: ToolsConfig
```
Type-safe, validated at startup, easy to override per-environment.

**Our adaptation:** Same pattern, simpler. Single `config.toml` with all model paths, ports, and settings.

### 7. Component Health Pattern
**Source design:** Each module exposes `get_component_info() -> ComponentInfo`

Unified health monitoring: every component reports its status, and a `/health` endpoint aggregates them.

**Our adaptation:** Each core module (STT, LLM, TTS) exposes `async def health() -> dict`. FastAPI `/health` endpoint aggregates.

### 8. Skills System (instead of fine-tuning)

**Why not fine-tune:** Mistral Nemo 12B already has strong tool calling and bash knowledge out of the box. Fine-tuning for a hackathon is a waste of time (4-6 hours for data prep + training + eval). Skills give you the same behavioral control with zero training cost.

**What skills are:** Markdown files with YAML frontmatter, following the Anthropic skill pattern. Two-stage design:
- **Stage 1 (selection):** Orchestrator sees ONLY the YAML frontmatter (name + description) to decide whether to activate a skill. This keeps the routing decision cheap — no full playbooks loaded into context during matching.
- **Stage 2 (execution):** Once a skill is selected, the full markdown body is injected into the LLM's context. Rich instructions with examples, code blocks, multi-step procedures.

**Skill file format (`.md` with YAML frontmatter):**
```markdown
---
name: system-debug
description: Diagnose system performance issues, check resources, logs, and GPU status.
  Use when users report slowness, errors, crashes, or ask to check system health.
---

## System Diagnostics Procedure

Investigate the system issue methodically. Execute each step and analyze results
before moving to the next.

### Step 1: Resource Check
Run these commands and analyze output:
- `top -bn1 | head -20` — identify CPU-heavy processes
- `free -h` — check memory pressure
- `df -h` — check disk space

### Step 2: GPU Status
- `nvidia-smi` — check GPU utilization, memory, temperature
- Flag if GPU memory is >90% or temperature >80C

### Step 3: Recent Logs
- `journalctl --since '10 min ago' --no-pager | tail -30`
- Look for OOM kills, segfaults, or service failures

### Step 4: Synthesis
Summarize findings concisely. Lead with the most likely root cause.
If nothing is wrong, say so — don't invent problems.
```

**How it works:**
```
User says: "debug why the server is slow"
    │
    ├── Stage 1: Orchestrator sends ALL skill descriptions to LLM
    │   in a lightweight selection prompt:
    │   "Given this user input, which skill (if any) should be activated?
    │    Available: [system-debug: Diagnose system performance...,
    │               web-research: Multi-step web research..., ...]"
    │
    │   LLM returns: "system-debug" (or "none")
    │
    ├── Stage 2: Load full markdown body of system-debug.md
    │   Inject into system message as additional instructions
    │
    └── LLM follows the playbook, executes tools step by step, reports findings
```

**Why LLM-based selection instead of regex:**
- Regex breaks on paraphrasing: "my machine is crawling" wouldn't match `debug|diagnose`
- The LLM understands intent, not just keywords
- Descriptions are short (~50 tokens each), so sending all of them is cheap
- The selection call can use the same vLLM endpoint, adds ~200ms

**Why this is better than fine-tuning:**
- **Instant iteration** — edit a markdown file, restart, new behavior. No retraining.
- **Transparent** — you can read exactly what the model will do. No black box.
- **Rich instructions** — full markdown with examples, code blocks, conditional logic.
- **User-extensible** — drop a `.md` file in `skills/` to add new capabilities.
- **Two-stage efficiency** — only the matched skill's body goes into context, not all skills.
- **No VRAM cost** — skills are just prompt text, not model weights.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser (Simple Web UI)                                │
│  ┌──────────┐  WebSocket  ┌──────────┐                  │
│  │ Mic Input │────────────▶│ Audio Out │                 │
│  └──────────┘  (binary)   └──────────┘                  │
└────────────────────┬──────────────▲──────────────────────┘
                     │              │
              ┌──────▼──────────────┴──────┐
              │  FastAPI Server             │
              │                            │
              │  ┌────────────────────┐    │
              │  │ Audio Handler      │    │
              │  │ (WebSocket recv,   │    │
              │  │  VAD, buffering)   │    │
              │  └────────┬───────────┘    │
              │           ▼                │
              │  ┌────────────────────┐    │
              │  │ Voxtral Realtime   │    │
              │  │ (STT - streaming)  │    │
              │  └────────┬───────────┘    │
              │           ▼                │
              │  ┌────────────────────┐    │
              │  │ Orchestrator       │    │
              │  │ ┌────────────────┐ │    │
              │  │ │ Context Build  │ │    │
              │  │ │ LLM Call       │ │    │
              │  │ │ Tool Loop      │◄┼────┼── Tool Executor
              │  │ │ Response       │ │    │   (shell, files,
              │  │ └────────────────┘ │    │    apps, web search)
              │  └────────┬───────────┘    │
              │           ▼                │
              │  ┌────────────────────┐    │
              │  │ NVIDIA NeMo TTS   │    │
              │  │ (FastPitch+HiFiGAN)│    │
              │  └────────┬───────────┘    │
              │           │ audio bytes    │
              └───────────┴────────────────┘
```

**Key difference from voice-os:** voice-os runs CLI-only with local mic/speaker. VoxaOS runs as a web server with browser-based audio via WebSocket, making it accessible from any device connecting to the cloud GPU.

---

## VRAM Budget (L40S - 48GB)

| Component | Model | Est. VRAM | Deployment |
|-----------|-------|-----------|------------|
| STT | Voxtral Realtime | ~3 GB | Direct inference (transformers) |
| LLM | Mistral Nemo 12B (Q4_K_M) | ~8 GB | vLLM server |
| TTS | NVIDIA FastPitch + HiFi-GAN | ~1 GB | NeMo inference |
| Overhead | Audio buffers, CUDA context | ~2 GB | - |
| **Total** | | **~14 GB** | |
| **Free for Phase 2 agents** | | **~34 GB** | |

> Using Mistral Nemo 12B over Small 3.1 24B - plenty capable for tool calling, keeps VRAM lean. Can upgrade later.

---

## Project Structure

```
voxaos/
├── docs/
│   └── PLAN.md
├── config/
│   └── default.toml              # Model paths, ports, all settings
├── pyproject.toml                # Dependencies (uv/pip)
├── Dockerfile                    # Container build (post-hackathon)
├── docker-compose.yaml           # One-command deploy with GPU
├── main.py                       # Entry point - starts all services
├── setup.sh                      # One-click: install deps, download models
│
├── core/
│   ├── __init__.py
│   ├── orchestrator.py           # Central brain: context → LLM → tool loop → response
│   ├── context.py                # Conversation history + environment context builder
│   ├── types.py                  # Shared dataclasses (Response, StreamChunk, ToolCall, etc.)
│   └── config.py                 # Pydantic config models + TOML loader
│
├── voice/
│   ├── __init__.py
│   ├── stt.py                    # Voxtral Realtime STT wrapper
│   ├── tts.py                    # NVIDIA NeMo TTS wrapper
│   ├── vad.py                    # Silero VAD - speech detection on audio chunks
│   └── pipeline.py               # State machine: IDLE → LISTENING → PROCESSING → SPEAKING
│
├── llm/
│   ├── __init__.py
│   ├── client.py                 # vLLM OpenAI-compatible client (async, tool calling)
│   ├── tools.py                  # Tool definitions as OpenAI function schemas
│   └── prompts.py                # System prompt builder
│
├── skills/
│   ├── __init__.py
│   ├── loader.py                 # Discovers skill .md files, parses YAML frontmatter
│   ├── selector.py               # LLM-based skill selection from descriptions
│   ├── system-debug.md           # Skill: diagnose system issues, check resources/logs/GPU
│   ├── deploy.md                 # Skill: detect build system, test, build, deploy
│   ├── project-setup.md          # Skill: scaffold new project from template
│   ├── web-research.md           # Skill: multi-step web research + synthesize findings
│   ├── file-ops.md               # Skill: bulk file operations (rename, move, organize)
│   └── home-insights.md          # Skill: analyze HA sensor data, daily/weekly briefing
│
├── memory/
│   ├── __init__.py
│   ├── learning.py               # mem0 wrapper - add, search, get_all
│   ├── capture.py                # SQLite full interaction logger
│   └── types.py                  # InteractionRecord dataclass
│
├── tools/
│   ├── __init__.py
│   ├── executor.py               # Risk classification + dispatch + confirmation gate
│   ├── shell.py                  # Shell command execution (subprocess, timeout, safety)
│   ├── filesystem.py             # File CRUD, directory listing, search
│   ├── process.py                # List/kill processes, system info
│   ├── launcher.py               # Launch apps, open URLs
│   ├── web_search.py             # DuckDuckGo search + page fetch/summarize
│   └── home_assistant.py         # HA REST API: get states, history, call services
│
├── server/
│   ├── __init__.py
│   ├── app.py                    # FastAPI app: WebSocket + REST endpoints
│   └── audio_handler.py          # WebSocket audio stream → VAD → pipeline
│
├── ui/
│   ├── index.html                # Single-page browser UI
│   ├── style.css                 # Dark terminal aesthetic
│   └── app.js                    # Mic capture, WebSocket, audio playback
│
└── scripts/
    ├── start_vllm.sh             # Start vLLM server with Mistral Nemo
    └── download_models.sh        # Pull all model weights
```

---

## Implementation Phases (24-hour hackathon)

### Phase 1: Infrastructure + Model Serving (Hours 0-4)

**Goal:** All models downloadable, vLLM serving, config wired up.

1. **`pyproject.toml`** - define all deps
2. **`setup.sh`** - one-click install: system packages (ffmpeg, libsndfile), Python env, deps
3. **`scripts/download_models.sh`** - pull Voxtral Realtime, Mistral Nemo 12B, NeMo TTS weights
4. **`scripts/start_vllm.sh`** - launch vLLM with Mistral Nemo 12B, OpenAI-compatible endpoint on `:8000`
5. **`config/default.toml`** + **`core/config.py`** - Pydantic config models, TOML loader
   - Model paths, vLLM URL, server port, tool settings, VAD thresholds
6. **`core/types.py`** - shared dataclasses
   - `Response(text, audio_bytes, tool_calls_made, latency_ms)`
   - `StreamChunk(type, content)` - types: "transcript", "thinking", "tool_start", "tool_result", "text", "audio"
   - `ToolCall(id, name, args)`, `ToolResult(tool_use_id, content, is_error)`
7. **Verify:** `curl localhost:8000/v1/chat/completions` with a tool-calling test payload

### Phase 2: Core Brain - Orchestrator + LLM + Tools (Hours 4-12)

**Goal:** Text in → tool execution → text out. The brain works without voice.

1. **`llm/tools.py`** - define all tool schemas (OpenAI function format)
   - `run_shell`, `read_file`, `write_file`, `list_directory`, `search_files`
   - `list_processes`, `kill_process`, `launch_app`, `open_url`
   - `web_search`, `fetch_page`
2. **`llm/prompts.py`** - system prompt builder
   - VoxaOS persona, environment context injection, tool usage instructions
   - Key instruction: "Be concise - the user is listening, not reading"
3. **`llm/client.py`** - async vLLM client
   - Uses `openai` Python SDK pointing at `localhost:8000`
   - `async def chat(messages, tools) -> LLMResponse`
   - Parses tool_calls from response, handles streaming
4. **`tools/executor.py`** - tool dispatch + risk classification
   - Risk levels: `safe` (read_file, list_dir) / `moderate` (write_file, open_url) / `dangerous` (run_shell with rm, kill_process)
   - Auto-confirm safe, prompt for dangerous
   - Maps tool name → handler, captures output, truncates to 4096 chars
5. **`tools/shell.py`** - `asyncio.create_subprocess_exec`, 30s timeout, blocklist
6. **`tools/filesystem.py`** - aiofiles for read/write, `os.scandir` for listing, `glob` for search
7. **`tools/process.py`** - `psutil` for list/kill
8. **`tools/launcher.py`** - `subprocess.Popen` for apps, `webbrowser.open` for URLs
9. **`tools/web_search.py`** - `duckduckgo-search` lib, `httpx` + `beautifulsoup4` for page fetch
10. **`tools/home_assistant.py`** - Home Assistant REST API integration
    - `ha_get_states(domain?)` — get all entity states, optionally filtered by domain (light, sensor, switch, climate)
    - `ha_get_history(entity_id, hours)` — pull sensor history for a time period
    - `ha_call_service(domain, service, entity_id, data?)` — control devices (turn on/off, set temp, etc.)
    - All calls go through `httpx` to `http://<ha_url>:8123/api/` with long-lived access token
    - Gated behind `[home_assistant] enabled = true` in config — off by default
11. **`core/context.py`** - conversation history (last 20 exchanges), environment section (OS, hostname, cwd, GPU info)
11. **Skills system** - markdown playbooks with YAML frontmatter (Anthropic skill pattern)
    - **`skills/loader.py`** - discovers skill `.md` files, parses frontmatter vs body
      ```python
      @dataclass
      class Skill:
          name: str           # from YAML frontmatter
          description: str    # from YAML frontmatter (used for selection)
          body: str           # full markdown body (loaded only when activated)
          file_path: Path

      def load_skills(skills_dir: Path) -> list[Skill]:
          """Glob all .md files, parse YAML frontmatter, return Skill objects.
          Body is loaded but NOT sent to LLM until skill is selected."""
      ```
    - **`skills/selector.py`** - LLM-based skill selection (not regex)
      ```python
      async def select_skill(user_input: str, skills: list[Skill], llm_client) -> Skill | None:
          """Send skill descriptions (name + description only) to LLM.
          LLM decides which skill to activate, or 'none'.
          Returns matched Skill or None."""

          # Build lightweight selection prompt
          skill_list = "\n".join(f"- {s.name}: {s.description}" for s in skills)
          selection_prompt = f"""Given this user request, which skill should be activated?
          Available skills:
          {skill_list}

          User request: "{user_input}"
          Respond with just the skill name, or "none" if no skill applies."""

          # Quick LLM call (~200ms, just text classification)
          result = await llm_client.chat([{"role": "user", "content": selection_prompt}])
          # Match result to skill name, return Skill or None
      ```
    - **Skill file format** — `.md` with YAML frontmatter:
      ```markdown
      ---
      name: web-research
      description: Multi-step web research and synthesis. Use when users ask to
        research a topic, find information across multiple sources, or need a
        comprehensive summary of a subject from the web.
      ---

      ## Web Research Procedure

      Research the topic thoroughly using multiple search queries.

      ### Step 1: Initial Search
      Use web_search with 2-3 different phrasings of the query to get diverse results.

      ### Step 2: Deep Dive
      For the top 3 most relevant results, use fetch_page to get full content.
      Extract key facts, data points, and quotes.

      ### Step 3: Synthesis
      Combine findings into a concise briefing. Lead with the answer,
      then supporting evidence. Cite sources. Keep it under 5 sentences
      for voice delivery — offer to elaborate if asked.
      ```
    - **Starter skills to ship:**
      - `system-debug.md` - system diagnostics (resources, logs, GPU, processes)
      - `deploy.md` - detect project type, run tests, build, deploy
      - `project-setup.md` - scaffold directories, init files, git init
      - `web-research.md` - multi-query web search, fetch pages, synthesize findings
      - `file-ops.md` - bulk rename, move, organize files by pattern
      - `home-insights.md` - analyze Home Assistant sensor data, generate daily/weekly briefings
13. **Memory system** - learning memory + full capture
    - **`memory/types.py`** - `InteractionRecord` dataclass (session_id, timestamp, transcript, messages, tool_calls, response, skill_used, latency)
    - **`memory/learning.py`** - mem0 wrapper pointing at local vLLM for extraction, Qdrant in-process for vector storage
    - **`memory/capture.py`** - SQLite logger for complete interaction records
    - Wire into orchestrator: search before LLM call, add after response, log everything
13. **`core/orchestrator.py`** - the brain
    - `async def process(user_input: str) -> Response`
    - **Two-stage skill selection + execution flow:**
      ```
      user_input
          │
          ▼
      ┌─ Stage 1: Skill Selection (lightweight LLM call) ─────────┐
      │  Send ONLY skill descriptions (name + description) to LLM  │
      │  LLM returns: skill name or "none"                         │
      │  Cost: ~200ms, ~100 tokens                                 │
      └────────────────────────┬───────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ skill matched?      │
                    │ yes → load .md body │
                    │ no  → skip          │
                    └──────────┬──────────┘
                               │
      ┌─ Stage 2: Main LLM Call ──────────────────────────────────┐
      │  Build system prompt:                                      │
      │    ├── base persona prompt                                 │
      │    ├── environment context (OS, hostname, GPU)             │
      │    ├── conversation history (last N turns)                 │
      │    └── skill.body (full markdown, ONLY if skill matched)   │
      │                                                            │
      │  Call LLM with tools + system prompt                       │
      │  Run tool call loop (max 10 iterations)                    │
      │  Return final text response                                │
      └───────────────────────────────────────────────────────────┘
      ```
    - `async def process_streaming(user_input) -> AsyncIterator[StreamChunk]` for progressive UI updates
    - **Key detail:** The skill body can be substantial (500+ tokens of detailed instructions) but it only enters context when that skill is actually needed. No skill = no extra tokens in the prompt.
13. **Verify:** Run orchestrator directly from Python:
    ```python
    # Basic tool call (no skill activated)
    response = await orchestrator.process("List all files in /tmp")
    # LLM skill selection returns "none"
    # LLM uses run_shell tool directly, returns natural language summary

    # Skill-triggered multi-step
    response = await orchestrator.process("Debug why the system feels slow")
    # Stage 1: LLM selects "system-debug" skill
    # Stage 2: Full system-debug.md body injected, LLM follows procedure
    # Runs top, free, nvidia-smi, journalctl, synthesizes report

    # Skill-triggered research
    response = await orchestrator.process("Research the latest NVIDIA earnings")
    # Stage 1: LLM selects "web-research" skill
    # Stage 2: Follows multi-search → deep-dive → synthesis procedure
    ```

### Phase 3: Voice Pipeline (Hours 12-17)

**Goal:** Audio in → transcription → orchestrator → synthesized audio out.

1. **`voice/vad.py`** - Silero VAD wrapper
   - Load model (CPU, ~2MB)
   - `detect(audio_chunk: np.ndarray) -> bool` - returns True if speech detected
   - Configurable thresholds: speech start (300ms of speech), speech end (500ms of silence)
2. **`voice/stt.py`** - Voxtral Realtime wrapper
   - Load model on GPU
   - `async def transcribe(audio: np.ndarray) -> str`
   - Input: 16kHz mono float32 PCM
   - Streaming mode: feed chunks, get partial transcripts
3. **`voice/tts.py`** - NVIDIA NeMo TTS wrapper
   - Load FastPitch (text→spectrogram) + HiFi-GAN (spectrogram→waveform)
   - `async def synthesize(text: str) -> np.ndarray`
   - Output: 22.05kHz mono float32
   - Text preprocessing: strip markdown, expand common abbreviations
   - **Fallback:** If local NeMo setup burns >1 hour, switch to NVIDIA Riva TTS API (same models, cloud-hosted, streaming support)
4. **`voice/pipeline.py`** - state machine
   - States: `IDLE → LISTENING → PROCESSING → SPEAKING`
   - `async def feed_audio(chunk: bytes)` - called by WebSocket handler
   - VAD detects speech start → buffer audio → VAD detects silence → send to STT
   - STT text → orchestrator.process() → TTS → emit audio via callback
   - Callback: `on_audio_out(audio_bytes)` - server sends back through WebSocket
   - Callback: `on_state_change(state)` - server sends status updates to UI
   - Callback: `on_stream_chunk(chunk)` - progressive text updates to UI
5. **Verify:** Feed a .wav file through the pipeline, check full round-trip produces audio response

### Phase 4: Server + Browser UI (Hours 17-21)

**Goal:** Open browser, talk to VoxaOS, hear it respond.

1. **`server/app.py`** - FastAPI application
   - `GET /` - serve `ui/index.html`
   - `GET /health` - aggregate component health (STT loaded? vLLM up? TTS loaded?)
   - `WS /ws/audio` - bidirectional audio + control messages
   - On startup: initialize pipeline, load STT/TTS models
2. **`server/audio_handler.py`** - WebSocket protocol
   - **Client → Server messages:**
     - Binary frames: raw PCM audio chunks (16kHz, mono, int16)
     - JSON `{"type": "push_to_talk", "state": "start"|"stop"}` - manual trigger
     - JSON `{"type": "confirm", "tool_call_id": "..."}` - user confirms dangerous op
   - **Server → Client messages:**
     - Binary frames: TTS audio (22.05kHz, mono, int16)
     - JSON `{"type": "transcript", "text": "...", "partial": true|false}`
     - JSON `{"type": "thinking", "text": "Searching the web..."}` - tool execution status
     - JSON `{"type": "response", "text": "...", "tools_used": [...]}`
     - JSON `{"type": "state", "pipeline": "listening"|"processing"|"speaking"}`
     - JSON `{"type": "confirm_request", "tool_name": "...", "args": {...}}` - ask user to confirm
3. **`ui/index.html`** - single page app
   - Header: VoxaOS logo/title + connection status indicator
   - Main area: scrolling terminal-style log (transcripts, responses, tool outputs)
   - Bottom: push-to-talk button (big, spacebar-activated) + waveform visualizer
   - Audio playback: Web Audio API for low-latency TTS playback
4. **`ui/app.js`** - browser logic
   - `getUserMedia()` for mic access
   - `AudioWorklet` or `ScriptProcessorNode` to capture PCM chunks at 16kHz
   - WebSocket connection: send binary audio, receive mixed binary+JSON
   - Audio queue: buffer incoming TTS audio, play sequentially
   - Spacebar push-to-talk: hold to record, release to stop
5. **`ui/style.css`** - dark terminal theme
   - Monospace font, dark background, green/amber text
   - Pulsing indicator for listening state
   - Scrolling log with color-coded entries (user=cyan, system=green, tool=yellow, error=red)
6. **Verify:** Open browser, hold spacebar, say "hello", see transcript + hear response

### Phase 5: Polish + Demo Prep (Hours 21-24)

**Goal:** Smooth demo, no embarrassing failures.

1. End-to-end testing of 10+ diverse commands
2. Latency profiling: measure each stage, optimize bottlenecks (target: <3s total)
3. Error recovery: if any model crashes, show graceful error in UI instead of dying
4. Conversation continuity: verify multi-turn works ("create a file" → "now read it back to me")
5. **Demo script** - rehearse these commands:
   - "What's the current system memory and CPU usage?"
   - "Search the web for the latest NVIDIA earnings report"
   - "Create a Python file called fibonacci.py with a recursive fibonacci function"
   - "Now read that file back to me"
   - "List all running processes and tell me which one is using the most CPU"
   - "Open the NVIDIA developer documentation in a browser"

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM serving | vLLM | OpenAI-compatible API, native Mistral tool calling, battle-tested |
| Audio transport | WebSocket (binary + JSON) | Low latency, bidirectional, works from any browser |
| VAD | Silero VAD | Lightweight (~2MB), accurate, CPU-only, proven in voice-os |
| Web search | DuckDuckGo (duckduckgo-search) | No API key needed, fast for hackathon |
| Frontend | Vanilla HTML/JS | Zero build step, no node_modules, fast to iterate |
| Config | Pydantic + TOML | Type-safe, validated at startup, proven in voice-os |
| Tool format | OpenAI function calling JSON | vLLM + Mistral support it natively, industry standard |
| TTS fallback | NVIDIA Riva TTS API | Same FastPitch+HiFi-GAN models, cloud-hosted via NIM |

---

## System Prompt (LLM)

```
You are VoxaOS, a voice-controlled operating system running on an NVIDIA L40S GPU.
You have direct access to the host Linux system through your tools.

Capabilities:
- Execute any shell command
- Read, write, search, and manage files
- Launch applications and manage processes
- Search the web and summarize pages

Rules:
- Be concise. The user is LISTENING to your response, not reading it. Keep answers
  under 3 sentences unless they ask for detail.
- Use tools proactively. If the user asks "what files are here", use list_directory.
  Don't guess.
- For destructive operations (delete, kill, overwrite), state what you're about to
  do and wait for confirmation.
- When reporting tool output, summarize it naturally. Don't read raw JSON or
  full file contents aloud.
- If a command fails, explain the error briefly and suggest a fix.
```

---

## Deployment Modes & Fallback Strategy

The architecture supports three deployment modes via a single config toggle. The code stays the same — only the endpoint URLs change.

### Mode 1: Full Local (NVIDIA L40S GPU)
**Primary mode.** Everything runs on the GPU.

| Component | Implementation | Latency |
|-----------|---------------|---------|
| STT | Voxtral Realtime (local GPU) | ~200ms |
| LLM | Mistral Nemo 12B via vLLM (local GPU) | ~500ms |
| TTS | NVIDIA NeMo FastPitch+HiFi-GAN (local GPU) | ~300ms |
| **Total** | | **~1-2s** |

### Mode 2: Full API (Laptop / No GPU)
**Backup if NVIDIA cloud falls through.** Runs on any machine with internet.

| Component | Implementation | Latency | Cost |
|-----------|---------------|---------|------|
| STT | Mistral Voxtral API | ~1-2s | $0.003/min |
| LLM | Mistral Nemo API (La Plateforme) | ~500ms-1s | $0.02/M input, $0.04/M output |
| TTS | NVIDIA Riva TTS NIM API | ~500ms | Free tier on build.nvidia.com |
| **Total** | | **~2-4s** | **<$1 for entire hackathon** |

### Mode 3: Hybrid (Mix local + API)
**Best of both worlds.** Run what you can locally, offload the rest.

Example: Local LLM (fast tool calling) + API for STT/TTS.

### Config switch

```toml
[mode]
# "local" = everything on GPU
# "api"   = everything via API (no GPU needed)
# "hybrid" = mix (configure per-component below)
backend = "local"

[stt]
backend = "local"              # or "api"

[stt.local]
model_path = "~/.voxaos/models/voxtral-realtime"

[stt.api]
base_url = "https://api.mistral.ai/v1/audio/transcriptions"
api_key_env = "MISTRAL_API_KEY"

[llm]
backend = "local"              # or "api"

[llm.local]
base_url = "http://localhost:8000/v1"
model = "mistralai/Mistral-Nemo-Instruct-2407"

[llm.api]
base_url = "https://api.mistral.ai/v1"
model = "mistral-nemo-latest"
api_key_env = "MISTRAL_API_KEY"

[tts]
backend = "local"              # or "api"

[tts.local]
model = "fastpitch_hifigan"
model_path = "~/.voxaos/models/nemo-tts"

[tts.api]
base_url = "https://integrate.api.nvidia.com/v1"   # Riva TTS NIM
api_key_env = "NVIDIA_API_KEY"
voice = "English-US.Female-1"
```

### Code impact

Each module (`voice/stt.py`, `llm/client.py`, `voice/tts.py`) has a factory pattern:

```python
# voice/tts.py
async def create_tts(config: TTSConfig) -> TTSEngine:
    if config.backend == "local":
        return NeMoTTS(config.local)
    else:
        return RivaTTSAPI(config.api)
```

Both implementations expose the same interface: `async def synthesize(text: str) -> np.ndarray`. The rest of the pipeline doesn't care which backend is running.

---

## Safety Guardrails

- **Shell blocklist:** Reject commands matching: `rm -rf /`, `mkfs`, `dd if=/dev`, `shutdown`, `reboot`, `:(){ :|:&};:`, `chmod -R 777 /`, `> /dev/sda`
- **Timeout:** All tool executions capped at 30 seconds
- **Output truncation:** Truncate tool output to 4096 chars before feeding back to LLM
- **Non-root:** Run all commands as the current non-root user
- **Confirmation gate:** Dangerous ops (delete, kill, write to system paths) require user confirmation via UI
- **Rate limiting:** Max 10 tool call iterations per request (prevent infinite loops)

---

## Dependencies

```toml
[project]
requires-python = ">=3.11"
dependencies = [
    # Server
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",

    # LLM (openai SDK works for both vLLM local and Mistral API)
    "openai>=1.0",
    "mistralai>=1.0",           # Mistral API client (Voxtral STT API)

    # Voice - local GPU mode
    "torch>=2.0",
    "transformers>=4.40",       # Voxtral model loading
    "nemo_toolkit[tts]",        # NVIDIA NeMo TTS (FastPitch + HiFi-GAN)
    "numpy>=1.26",
    "soundfile>=0.12",

    # Voice - API mode (no extra deps, uses httpx/openai SDK)
    # Riva TTS NIM API: HTTP streaming
    # Voxtral API: via mistralai SDK

    # Tools
    "duckduckgo-search>=6.0",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "psutil>=5.9",
    "aiofiles>=23.0",

    # Memory
    "mem0ai>=0.1",
    "qdrant-client>=1.7",

    # Config
    "pydantic>=2.0",
    "tomli>=2.0",
]
```

---

## Verification Plan

| Step | Test | Expected |
|------|------|----------|
| 1 | `curl localhost:8000/v1/models` | vLLM returns Mistral Nemo model info |
| 2 | Python: feed .wav to Voxtral STT | Returns correct transcription text |
| 3 | Python: send tool-calling message to vLLM | Returns `tool_calls` array with correct function + args |
| 4 | Python: `await executor.execute(ToolCall("run_shell", {"command": "echo hi"}))` | Returns `ToolResult(content="hi")` |
| 5 | Python: feed text to NeMo TTS | Returns playable audio numpy array |
| 6 | Python: `await orchestrator.process("What time is it?")` | Returns natural language response with current time |
| 7 | Browser: open UI, hold spacebar, say "hello" | See transcript, hear spoken response |
| 8 | Browser: "List files in /tmp" | See tool execution in UI, hear file listing summary |
| 9 | Latency: measure end-of-speech to start-of-audio | Target: <3 seconds |

---

## Deployment on NVIDIA Brev

### Hackathon Day: Bare VM (no containers needed)

Brev gives you a VM with NVIDIA drivers + CUDA pre-installed. Fastest path:

```bash
# 1. Create L40S instance on brev.dev console
#    - Select GPU: NVIDIA L40S (48GB)
#    - Select "I have code files in a git repository" → point to repo
#    - Or select "I don't have any code files" and git clone after SSH

# 2. SSH into instance
brev open voxaos-dev

# 3. One-click setup
git clone <repo-url> voxaos && cd voxaos
chmod +x setup.sh && ./setup.sh

# 4. Start all services
python main.py
# → vLLM loads Mistral Nemo on GPU
# → Voxtral STT loads on GPU
# → NeMo TTS loads on GPU
# → FastAPI serves on :7860

# 5. Access from browser
# Brev auto-forwards ports, or use the provided URL
```

**`setup.sh` does everything:**
- Installs system packages (ffmpeg, libsndfile)
- Creates Python venv, installs all deps
- Downloads model weights (Voxtral, Mistral Nemo 12B Q4, NeMo TTS)
- Validates GPU is accessible (`nvidia-smi`)

### Post-Hackathon: Containerized Deployment

For reproducibility and sharing, wrap in Docker:

**`Dockerfile`:**
```dockerfile
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3-pip \
    ffmpeg libsndfile1 git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
RUN python3.11 -m pip install --no-cache-dir .

COPY . .

# Download models at build time (or mount as volume)
RUN bash scripts/download_models.sh

EXPOSE 7860
CMD ["python3.11", "main.py", "--host", "0.0.0.0", "--port", "7860"]
```

**`docker-compose.yaml`:**
```yaml
services:
  voxaos:
    build: .
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    ports:
      - "7860:7860"
    volumes:
      - model-cache:/app/models    # Persist model weights across rebuilds
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - VLLM_MODEL=mistralai/Mistral-Nemo-Instruct-2407
    restart: unless-stopped

volumes:
  model-cache:
```

**Deploying on Brev with containers:**
1. Create new instance → select "With container(s)"
2. Choose "Docker Compose Mode"
3. Provide the `docker-compose.yaml` URL or upload it
4. Select GPU: L40S
5. Deploy — Brev builds + runs with GPU access

### Port Exposure

Brev handles port forwarding automatically. The FastAPI server on `:7860` will be accessible via:
- Brev's auto-generated URL: `https://<instance-id>.brev.dev`
- Or direct IP if using static networking

### Estimated Cloud Costs

| Resource | Cost | Duration |
|----------|------|----------|
| L40S on Brev | ~$1.50-2.00/hr | 24hr hackathon = ~$36-48 |
| Model downloads | Free (open-source weights) | One-time ~20min |
| Total hackathon cost | **~$36-48** | |

---

## Memory System

VoxaOS needs two types of memory:
1. **Learning memory** — extracts and retains facts, preferences, and patterns across sessions
2. **Full capture** — logs every interaction verbatim for replay, debugging, and training data

### Framework Choice: mem0

**Why mem0 over alternatives:**

| Framework | Verdict | Reason |
|-----------|---------|--------|
| **mem0** | **Selected** | Standalone memory layer, plugs into any agent. LLM auto-extracts key info. Vector + optional graph storage. Apache 2.0. Simple API. |
| Letta (MemGPT) | Too heavy | Full agent runtime — wants to BE your agent, not serve it. Would require restructuring orchestrator. Great tech, wrong fit. |
| Graphiti | Phase 2 | Temporal knowledge graphs by Zep AI. Better for agent swarms tracking evolving entity relationships. |
| Memary | Phase 2 | Auto-updating knowledge graph. Same rationale — overkill for single-agent hackathon. |
| Cognee | Phase 2 | Knowledge graphs + RAG. More setup than a hackathon allows. |

**mem0 integration is ~50 lines of code.** It handles the hard parts (LLM-based extraction, deduplication, semantic search) so we don't have to build a memory pipeline from scratch.

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  Orchestrator                                       │
│                                                     │
│  1. User speaks → STT → transcript                  │
│  2. Search mem0 for relevant memories               │  ◄── Learning Memory
│  3. Inject memories into LLM context                │
│  4. LLM processes → tool loop → response            │
│  5. After response:                                 │
│     ├── mem0.add(user_msg + assistant_response)     │  ◄── Learns from exchange
│     └── capture_log.append(full_interaction)        │  ◄── Raw capture
└─────────────────────────────────────────────────────┘

┌── Learning Memory (mem0) ──────────────────────────┐
│  Vector DB: Qdrant (in-memory, no external server)  │
│  LLM extracts: facts, preferences, corrections     │
│  Deduplicates: won't store same fact twice          │
│  Semantic search: "user prefers..." → relevant hits │
│  Persistence: ~/.voxaos/memory/                     │
└─────────────────────────────────────────────────────┘

┌── Full Capture (SQLite) ───────────────────────────┐
│  Table: interactions                                │
│  ├── id, session_id, timestamp                      │
│  ├── user_transcript (raw STT output)               │
│  ├── llm_messages (full message array as JSON)      │
│  ├── tool_calls (all tool invocations + results)    │
│  ├── assistant_response (final text)                │
│  ├── audio_paths (STT input + TTS output files)     │
│  └── latency_ms (per-stage timing)                  │
│  File: ~/.voxaos/capture.db                         │
└─────────────────────────────────────────────────────┘
```

### Implementation

**New files:**
```
voxaos/
├── memory/
│   ├── __init__.py
│   ├── learning.py          # mem0 wrapper - add, search, get_all
│   ├── capture.py           # SQLite full interaction logger
│   └── types.py             # InteractionRecord dataclass
```

**`memory/learning.py`** — mem0 wrapper:
```python
from mem0 import Memory

class LearningMemory:
    def __init__(self, config: MemoryConfig):
        self.memory = Memory.from_config({
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "voxaos",
                    "path": str(config.storage_path),  # ~/.voxaos/memory/
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": config.llm_model,
                    "openai_base_url": config.llm_base_url,  # points at local vLLM
                }
            }
        })

    async def add(self, user_msg: str, assistant_msg: str, user_id: str = "default"):
        """Extract and store memories from a conversation exchange."""
        messages = [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
        ]
        self.memory.add(messages, user_id=user_id)

    async def search(self, query: str, user_id: str = "default", limit: int = 5) -> list[str]:
        """Retrieve relevant memories for context injection."""
        results = self.memory.search(query, user_id=user_id, limit=limit)
        return [r["memory"] for r in results.get("results", [])]

    async def get_all(self, user_id: str = "default") -> list[str]:
        """Get all stored memories."""
        results = self.memory.get_all(user_id=user_id)
        return [r["memory"] for r in results.get("results", [])]
```

**`memory/capture.py`** — SQLite full capture:
```python
import sqlite3
import json
from datetime import datetime

class CaptureLog:
    def __init__(self, db_path: str = "~/.voxaos/capture.db"):
        self.conn = sqlite3.connect(os.path.expanduser(db_path))
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TEXT,
                user_transcript TEXT,
                llm_messages TEXT,       -- full message array as JSON
                tool_calls TEXT,         -- [{name, args, result}, ...] as JSON
                assistant_response TEXT,
                skill_used TEXT,         -- which skill was activated, if any
                latency_ms TEXT          -- {"stt": 200, "llm": 500, "tts": 300} as JSON
            )
        """)
        self.conn.commit()

    def log(self, record: InteractionRecord):
        self.conn.execute(
            "INSERT INTO interactions VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
            (record.session_id, record.timestamp.isoformat(),
             record.user_transcript, json.dumps(record.llm_messages),
             json.dumps(record.tool_calls), record.assistant_response,
             record.skill_used, json.dumps(record.latency_ms))
        )
        self.conn.commit()
```

**Orchestrator integration** — add to `core/orchestrator.py`:
```python
# In process() method, BEFORE building LLM context:
memories = await self.learning_memory.search(user_input)
if memories:
    memory_context = "Relevant memories from past interactions:\n"
    memory_context += "\n".join(f"- {m}" for m in memories)
    # Inject into system prompt as additional context section

# AFTER getting final response:
await self.learning_memory.add(user_input, response.text)
self.capture_log.log(InteractionRecord(
    session_id=self.session_id,
    timestamp=datetime.now(),
    user_transcript=user_input,
    llm_messages=messages,
    tool_calls=tool_calls_made,
    assistant_response=response.text,
    skill_used=selected_skill.name if selected_skill else None,
    latency_ms=timing,
))
```

### Config

```toml
[memory]
enabled = true
storage_path = "~/.voxaos/memory"

[memory.learning]
enabled = true
# Uses the same LLM as the main brain for extraction
# mem0 points at vLLM (local) or Mistral API (api mode)

[memory.capture]
enabled = true
db_path = "~/.voxaos/capture.db"
# Set to false to disable full logging (privacy mode)
```

### VRAM Impact

**Zero additional VRAM.** mem0's memory extraction reuses the same vLLM/Mistral endpoint as the main brain. Qdrant runs in-memory on CPU (~50MB RAM). SQLite is disk-only.

### What mem0 Learns (examples)

After a few sessions, `memory.search("preferences")` might return:
- "User prefers Python over JavaScript for scripting tasks"
- "User's project directory is /home/user/src/voxaos"
- "User likes concise answers, dislikes verbose explanations"
- "User's name is [name], working on a hackathon project"
- "Server is hosted on NVIDIA L40S with 48GB VRAM"

These get injected into context before each LLM call, making the assistant progressively more personalized.

### Phase 2 Memory Upgrades

- **Graphiti** for temporal knowledge graphs — track how project state evolves over time
- **Cross-agent memory** — specialist agents share memories through a common mem0 instance
- **Memory consolidation** — periodic "sleep-time" job that reviews capture log and distills patterns into learning memory
- **User-facing memory management** — "forget that", "what do you remember about X", "clear all memories"

### Dependencies (additions)

```toml
# Memory
"mem0ai>=0.1",            # Learning memory (auto-extraction + vector search)
"qdrant-client>=1.7",     # Vector DB (in-process, no external server)
```

---

## Home Assistant Integration

VoxaOS connects to Home Assistant via REST API to read sensor data and control devices. HA handles all the hard work — Zigbee pairing, device management, IR codes, protocol translation. VoxaOS just consumes the clean API.

### Phase 1 (Hackathon): Read sensors + insights

**Tool: `tools/home_assistant.py`**
```python
HA_HEADERS = {"Authorization": f"Bearer {os.environ[config.ha.token_env]}",
              "Content-Type": "application/json"}

async def ha_get_states(domain: str = None) -> list[dict]:
    """Get all entity states, optionally filtered by domain."""
    resp = await httpx.get(f"{config.ha.url}/api/states", headers=HA_HEADERS)
    states = resp.json()
    if domain:
        states = [s for s in states if s["entity_id"].startswith(f"{domain}.")]
    return states

async def ha_get_history(entity_id: str, hours: int = 24) -> list[dict]:
    """Get sensor history for time period — used by insights analyzer."""
    start = (datetime.now() - timedelta(hours=hours)).isoformat()
    resp = await httpx.get(
        f"{config.ha.url}/api/history/period/{start}?filter_entity_id={entity_id}",
        headers=HA_HEADERS)
    return resp.json()

async def ha_call_service(domain: str, service: str, entity_id: str, data: dict = None) -> dict:
    """Call an HA service — turn_on, turn_off, set_temperature, etc."""
    payload = {"entity_id": entity_id, **(data or {})}
    resp = await httpx.post(f"{config.ha.url}/api/services/{domain}/{service}",
                            headers=HA_HEADERS, json=payload)
    return resp.json()
```

**Skill: `skills/home-insights.md`**
```markdown
---
name: home-insights
description: Analyze Home Assistant sensor data and generate insights. Use when
  the user asks about home conditions, sensor readings, daily briefing, energy
  usage patterns, or "what happened at home today".
---

## Home Insights Procedure

### Step 1: Gather Data
Pull the last 24 hours of history for key sensors using ha_get_history:
- Temperature sensors (all rooms)
- Presence/motion sensors
- Power consumption (smart plugs)
- Door/window sensors

### Step 2: Analyze Patterns
Look for:
- Temperature anomalies (sudden drops/spikes, rooms that differ significantly)
- Presence patterns (how long in each room, unusual absence/presence)
- Power anomalies (unexpected spikes, devices left on overnight)
- Environmental trends (rising humidity, declining air quality)

### Step 3: Generate Briefing
Summarize findings conversationally. Lead with anything unusual or actionable.
Keep it under 30 seconds of speech. Examples:
- "Your office hit 28°C around 2pm — might want to crack a window earlier"
- "Kitchen smart plug drew power between 1-4am — something left on?"
- "You were in the office 11 hours straight. Maybe take more breaks."

If nothing unusual: "Everything looks normal. Home ran steady at [temp],
no anomalies in power or presence."
```

**Scheduled insights (cron-style):**
```python
# core/scheduler.py — lightweight APScheduler or just asyncio background task
async def daily_insights_job(orchestrator):
    """Run once daily, store insights in memory, speak on next interaction."""
    response = await orchestrator.process(
        "[SYSTEM] Generate daily home insights briefing from sensor data."
    )
    await orchestrator.learning_memory.add(
        "daily home analysis", response.text
    )
    # Flag that a briefing is pending — speak it when user next interacts
    orchestrator.pending_briefing = response.text
```

### Config

```toml
[home_assistant]
enabled = false                    # Opt-in, off by default
url = "http://homeassistant.local:8123"
token_env = "HA_TOKEN"             # Long-lived access token from HA

[home_assistant.insights]
enabled = true
schedule = "daily"                 # "daily", "weekly", or "off"
time = "08:00"                     # When to run daily analysis
entities = [                       # Which entities to track
    "sensor.living_room_temperature",
    "sensor.office_presence",
    "sensor.kitchen_plug_power",
]
```

### Phase 2 Upgrades (good to have, later)

- **Direct MQTT subscription** — subscribe to `zigbee2mqtt/#` via `paho-mqtt` for real-time sensor streams without polling HA
- **mmWave presence triggers** — proactive alerts ("someone entered the room", "office empty for 2 hours")
- **IR blaster control** — voice-controlled TV, AC via Broadlink/Switchbot through HA service calls
- **Energy dashboard** — track daily/weekly power consumption, cost estimates
- **Automation creation** — "When I leave the office, turn off the lights" → VoxaOS creates HA automations via API
- **Multi-room awareness** — combine presence + temp + time to infer context ("you're in bed, dimming lights")

---

## Phase 2 Preview (post hackathon)

### Multimodal: Pixtral 12B + Webcam

Swap Mistral Nemo 12B for **Pixtral 12B** (`mistralai/Pixtral-12B-2409`) to add vision. Same Mistral family, same tool calling support, but accepts images.

| | Nemo 12B (Phase 1) | Pixtral 12B (Phase 2) |
|---|---|---|
| Text + tool calling | Yes | Yes |
| Vision (images) | No | **Yes** |
| VRAM | ~8 GB | ~10 GB |
| vLLM support | Yes | Yes |
| API format | OpenAI chat | OpenAI chat + vision |

**Implementation (~50 lines of code):**
1. `ui/app.js` — add `getUserMedia({video: true})`, grab frame on demand via canvas
2. `server/audio_handler.py` — detect image vs audio binary frames
3. `llm/client.py` — include image in messages as `image_url` content block
4. `config/default.toml` — change model name to `mistralai/Pixtral-12B-2409`

**Approach:** On-demand frame capture. User says something that needs vision → browser grabs one JPEG from webcam → sends over WebSocket → Pixtral analyzes. Not continuous video — no vision LLM does real-time streaming yet.

**Demo possibilities:**
- "Rate my outfit" — webcam frame + fashion judgment
- "What am I holding up?" — object recognition
- "Read this whiteboard" — OCR from camera
- "How many people are in the room?" — audience counting

### Agent Swarms

With ~34GB free VRAM after Phase 1, architecture supports spawning specialist agents:

- **Research Agent** - dedicated Mistral instance with web search + RAG tools, handles multi-page research
- **Code Agent** - Mistral instance with file I/O + shell tools, writes and debugs code
- **System Agent** - lightweight monitor, tracks system health, auto-optimizes resources

**Orchestrator becomes a router:** User intent → classify → delegate to specialist agent → collect result → respond.

**Communication:** Async message queue between agents (in-process asyncio.Queue or Redis for persistence).

**VRAM plan:** Each additional Mistral Nemo 12B Q4 instance costs ~8GB. Can fit 3-4 specialist agents alongside the main pipeline.
