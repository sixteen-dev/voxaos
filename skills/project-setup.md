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
