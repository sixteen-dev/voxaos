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
