# Task 04: Skills System (Loader + Selector + Starter Skills)

## Priority: 4
## Depends on: Task 02 (LLM client)
## Estimated time: 45-60 min

## Objective

Build the two-stage skills system: markdown files with YAML frontmatter, LLM-based skill selection, and body injection. Plus write all starter skill files.

## What to create

### 1. `skills/loader.py`

Discovers `.md` files in the skills directory, parses YAML frontmatter from markdown body.

```python
import os
import yaml
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Skill:
    name: str
    description: str
    body: str
    file_path: Path

def load_skills(skills_dir: str | Path = "skills") -> list[Skill]:
    """Glob all .md files in skills_dir, parse YAML frontmatter, return Skill objects."""
    skills_dir = Path(skills_dir)
    skills = []
    for md_file in sorted(skills_dir.glob("*.md")):
        text = md_file.read_text()
        # Parse YAML frontmatter between --- markers
        if not text.startswith("---"):
            continue
        end = text.index("---", 3)
        frontmatter = yaml.safe_load(text[3:end])
        body = text[end + 3:].strip()

        skills.append(Skill(
            name=frontmatter["name"],
            description=frontmatter["description"],
            body=body,
            file_path=md_file,
        ))
    return skills
```

### 2. `skills/selector.py`

LLM-based skill selection. Sends ONLY the name + description of all skills to the LLM in a lightweight classification call.

```python
from skills.loader import Skill
from llm.client import LLMClient

SELECTION_PROMPT = """Given this user request, which skill (if any) should be activated?

Available skills:
{skill_list}

User request: "{user_input}"

Respond with ONLY the skill name, or "none" if no skill applies. No explanation."""

async def select_skill(
    user_input: str,
    skills: list[Skill],
    llm_client: LLMClient,
) -> Skill | None:
    """Use LLM to select the best matching skill for user input.

    Stage 1 of the two-stage skill system. Only descriptions are sent,
    not the full bodies — keeps this call cheap (~100 tokens).
    """
    if not skills:
        return None

    skill_list = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    prompt = SELECTION_PROMPT.format(skill_list=skill_list, user_input=user_input)

    result = await llm_client.chat_simple([{"role": "user", "content": prompt}])
    result = result.strip().lower().strip('"').strip("'")

    if result == "none":
        return None

    # Match to skill by name
    for skill in skills:
        if skill.name.lower() == result:
            return skill

    return None
```

### 3. Starter skill files

Create these `.md` files in `skills/`:

**`skills/system-debug.md`**
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

**`skills/web-research.md`**
```markdown
---
name: web-research
description: Multi-step web research and synthesis. Use when users ask to research
  a topic, find information across multiple sources, or need a comprehensive summary
  of a subject from the web.
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

**`skills/deploy.md`**
```markdown
---
name: deploy
description: Detect project type, run tests, build, and deploy. Use when users ask
  to deploy a project, run CI, or prepare a release.
---

## Deploy Procedure

### Step 1: Detect Project Type
Check for these files in order:
- `package.json` → Node.js (npm/yarn/pnpm)
- `pyproject.toml` or `setup.py` → Python
- `Cargo.toml` → Rust
- `go.mod` → Go
- `Dockerfile` → Docker
- `Makefile` → Make

### Step 2: Run Tests
Execute the project's test suite:
- Node: `npm test` or `yarn test`
- Python: `pytest` or `python -m pytest`
- Rust: `cargo test`
- Go: `go test ./...`

Report results. If tests fail, stop and report the failures.

### Step 3: Build
- Node: `npm run build`
- Python: `pip install -e .` or `python -m build`
- Rust: `cargo build --release`
- Docker: `docker build -t <name> .`

### Step 4: Deploy
Ask the user where to deploy. Common targets:
- Docker: `docker run` or `docker compose up`
- Git: `git push origin main`
- Custom: follow user instructions
```

**`skills/project-setup.md`**
```markdown
---
name: project-setup
description: Scaffold a new project from scratch. Use when users ask to create a new
  project, initialize a repo, or set up a development environment.
---

## Project Setup Procedure

### Step 1: Clarify
If not specified, ask the user:
- Language/framework (Python, Node, Rust, etc.)
- Project name
- Any specific tools (pytest, eslint, docker, etc.)

### Step 2: Scaffold
Create the standard directory structure for the chosen stack:
- Python: `src/`, `tests/`, `pyproject.toml`, `.gitignore`
- Node: `src/`, `tests/`, `package.json`, `.gitignore`
- Generic: `src/`, `docs/`, `README.md`, `.gitignore`

### Step 3: Initialize
- `git init`
- Create initial `.gitignore` for the language
- Install dependencies if a package file was created
- Create a basic README with project name

### Step 4: Verify
- Run the project/tests to ensure the scaffold works
- Report what was created
```

**`skills/file-ops.md`**
```markdown
---
name: file-ops
description: Bulk file operations — rename, move, organize, or transform multiple
  files at once. Use when users want to batch rename, reorganize directories, or
  apply operations across many files.
---

## Bulk File Operations

### Step 1: Understand the Operation
Clarify what the user wants:
- Rename pattern (e.g., "add prefix", "change extension", "snake_case")
- Move/organize rule (e.g., "by date", "by extension", "by size")
- Which files/directory to operate on

### Step 2: Preview
Before executing, list what WILL change:
- Show source → destination for each file
- Count total files affected
- Ask for confirmation if more than 10 files

### Step 3: Execute
Run the operations. For each file:
- Check if destination already exists (don't overwrite without asking)
- Report success/failure per file
- Summarize total: "Renamed 15 files, 0 errors"

### Safety
- Never operate on system directories (/etc, /usr, /bin)
- Always preview before bulk operations
- Keep a dry-run log of what was done
```

**`skills/home-assistant.md`**
```markdown
---
name: home-assistant
description: Control and monitor smart home devices via Home Assistant. Use when the
  user asks to turn on/off lights, check sensor readings, set thermostat temperature,
  get home status, control any smart device, or analyze home sensor data patterns.
  Also handles daily/weekly home briefings and insights.
---

## Home Assistant Control & Insights

You have access to a Home Assistant instance with connected smart home devices
(Zigbee sensors, lights, switches, climate, plugs, presence sensors, IR blasters).

### Reading State
- Use ha_get_states(domain) to list devices by type
- Use ha_get_state(entity_id) to check a specific device
- Common domains: light, switch, sensor, climate, binary_sensor, media_player

### Controlling Devices
- Use ha_call_service to trigger physical device actions:
  - Lights: ha_call_service("light", "turn_on", "light.living_room", {"brightness": 200})
  - AC/Climate: ha_call_service("climate", "set_temperature", "climate.bedroom_ac", {"temperature": 22})
  - Switches: ha_call_service("switch", "turn_off", "switch.kitchen_plug")
  - Media: ha_call_service("media_player", "media_play_pause", "media_player.tv")
- Use ha_set_state to update entity state directly via POST /api/states/<entity_id>

### Analyzing Sensor Data
When asked for insights, briefings, or "what happened at home":
1. Pull history with ha_get_history for relevant sensors (last 24h default)
2. Look for: temperature anomalies, presence patterns, power spikes, devices left on
3. Summarize conversationally — lead with unusual or actionable findings
4. Keep voice response under 30 seconds

### Safety
- Always confirm before controlling climate (AC, heating) — changing temp costs money
- Never turn off devices that sound safety-critical (alarms, cameras, medical)
- For batch operations ("turn off everything"), list what will be affected first
```

**`skills/self-demo.md`**
```markdown
---
name: self-demo
description: Run a live, narrated demonstration of VoxaOS capabilities. Use when
  the user says "demo yourself", "show what you can do", "run a demo", or is
  presenting to an audience.
---

## Self-Demo Procedure

You are about to demonstrate yourself to an audience. Be confident, concise,
and let the ACTIONS speak louder than words. Execute real commands — never fake output.

Pause briefly between each section so the audience can absorb what happened.

### Opening
Say: "I'm VoxaOS — a voice-controlled operating system. Let me show you what I can do."

### Act 1: System Awareness
Say: "First, I know exactly what I'm running on."
- Run nvidia-smi and summarize: GPU model, VRAM usage, temperature
- Run uname -a and summarize: OS, kernel
- Run free -h and report available memory

### Act 2: File Operations
Say: "I can manage files by voice."
- List files in the current project directory
- Create a short Python script (fibonacci or something visual)
- Read it back, confirm it's correct

### Act 3: Code Execution
Say: "And I can run what I create."
- Execute the Python file you just created
- Report the output naturally

### Act 4: Web Intelligence
Say: "I'm not limited to this machine. I can reach the web."
- Search for something timely (today's date, recent tech news)
- Summarize the top result in one sentence

### Act 5: Process Management
Say: "I can see and control everything running on this system."
- List top 5 processes by CPU usage
- Identify what's using the most resources

### Act 6: Memory
Say: "And I remember. Every conversation teaches me something."
- Search memory for something learned about the user or project
- If memories exist, share one
- If no memories yet: "Over time I learn your preferences, your projects, your patterns."

### Closing
Say: "That's VoxaOS. Voice in, action out. Built in 24 hours on NVIDIA cloud."
Pause, then say: "What would you like me to do?"
```

## Verification

```python
import asyncio
from skills.loader import load_skills
from skills.selector import select_skill
from llm.client import LLMClient
from core.config import load_config

async def test():
    skills = load_skills("skills")
    print(f"Loaded {len(skills)} skills:")
    for s in skills:
        print(f"  - {s.name}: {s.description[:60]}...")

    config = load_config()
    client = LLMClient(config.llm)

    # Test selection
    skill = await select_skill("debug why the server is slow", skills, client)
    print(f"\nSelected: {skill.name if skill else 'none'}")  # Should be system-debug

    skill = await select_skill("what's the weather", skills, client)
    print(f"Selected: {skill.name if skill else 'none'}")  # Should be none or web-research

asyncio.run(test())
```

## Quality Gate

### Test file: `tests/test_skills.py`

```python
import pytest
from pathlib import Path
from skills.loader import load_skills, Skill

@pytest.fixture
def skills():
    return load_skills("skills")

def test_load_skills_count(skills):
    """Should load all 7 starter skills."""
    assert len(skills) >= 7

def test_skill_has_required_fields(skills):
    for skill in skills:
        assert isinstance(skill, Skill)
        assert skill.name
        assert skill.description
        assert skill.body
        assert skill.file_path.exists()

def test_skill_names(skills):
    names = {s.name for s in skills}
    expected = {"system-debug", "web-research", "deploy", "project-setup",
                "file-ops", "home-assistant", "self-demo"}
    assert expected.issubset(names)

def test_skill_frontmatter_parse():
    """Verify YAML frontmatter parsing works correctly."""
    skills = load_skills("skills")
    for skill in skills:
        # Every skill should have a non-empty body after frontmatter
        assert len(skill.body) > 50, f"{skill.name} body too short"

def test_self_demo_has_acts():
    skills = load_skills("skills")
    demo = next(s for s in skills if s.name == "self-demo")
    assert "Act 1" in demo.body
    assert "Act 6" in demo.body
    assert "Closing" in demo.body
```

### Run

```bash
uv run ruff check skills/ tests/test_skills.py
uv run mypy skills/loader.py skills/selector.py
uv run pytest tests/test_skills.py -v
```

| Check | Command | Pass? |
|-------|---------|-------|
| Lint clean | `uv run ruff check skills/ tests/test_skills.py` | |
| Types pass | `uv run mypy skills/loader.py skills/selector.py` | |
| 7 skills loaded | `uv run pytest tests/test_skills.py::test_load_skills_count` | |
| All skills parse | `uv run pytest tests/test_skills.py::test_skill_has_required_fields` | |
| Self-demo complete | `uv run pytest tests/test_skills.py::test_self_demo_has_acts` | |

## Design reference

See PLAN.md sections: "Skills System (instead of fine-tuning)", "Home Assistant Integration" (Skill), self-demo skill from planning conversation
