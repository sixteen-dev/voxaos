# VoxaOS Demo Script (2-3 minutes)

## Opening (10s)

"This is VoxaOS — a voice-controlled operating system built in 24 hours.
Speak to it, and it understands, acts, and responds."

## Auto-Demo (60-90s)

Say: **"VoxaOS, demo yourself"**

The system runs through its self-demo skill automatically:
- Shows system awareness (hostname, GPU, uptime, memory)
- Creates and reads a file
- Executes a Python snippet
- Runs a web search
- Demonstrates memory recall

Let it run — each act transitions automatically.

## Interactive (30-60s)

Pick 2-3 based on audience reaction:

- **"What processes are using the most CPU?"** — shows real-time process management
- **"Create a Python script that generates Fibonacci numbers and run it"** — live code generation + execution
- **"Research the latest NVIDIA stock price"** — web search skill activation
- **"My favorite language is Rust"** → then later **"What's my favorite language?"** — demonstrates persistent memory
- **"Turn on the living room lights"** — if Home Assistant is connected

## Closing (10s)

"Built with Mistral for the brain, NVIDIA for the voice, and mem0 for memory.
Modular pipeline — every component is swappable. All running in the cloud on an L40S."

## Backup Commands

If something fails during the demo, use text input as fallback:

- Type "list files in /tmp" — quick tool demo
- Type "what can you do?" — triggers a capabilities overview
- Type "hello" — simple smoke test

## Pre-Demo Checklist

- [ ] Server running: `uv run python main.py`
- [ ] Browser open at `http://localhost:7860`
- [ ] Green connection dot visible
- [ ] Mic permissions granted (click PTT button once)
- [ ] API keys set (MISTRAL_API_KEY, NVIDIA_API_KEY)
- [ ] Test text input works before going live
