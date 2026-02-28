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
