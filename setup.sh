#!/bin/bash
set -e

echo "=== VoxaOS Setup ==="
echo ""

# Check uv
if ! command -v uv &>/dev/null; then
    echo "ERROR: uv is required. Install it:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo "uv: $(uv --version)"

# Install dependencies
echo ""
echo "Installing dependencies..."
uv sync

# Create data directories
mkdir -p ~/.voxaos/memory
mkdir -p ~/.voxaos/models

# Check for API keys
echo ""
echo "--- API Key Check ---"
if [ -f .env ]; then
    echo ".env file found"
    set -a; source .env; set +a
fi

if [ -z "$MISTRAL_API_KEY" ]; then
    echo "WARNING: MISTRAL_API_KEY not set. Required for STT + LLM (API mode)."
    echo "  Set it in .env or export MISTRAL_API_KEY=..."
else
    echo "MISTRAL_API_KEY: set"
fi

if [ -z "$NVIDIA_API_KEY" ]; then
    echo "WARNING: NVIDIA_API_KEY not set. Required for TTS (API mode)."
    echo "  Set it in .env or export NVIDIA_API_KEY=..."
else
    echo "NVIDIA_API_KEY: set"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "To start VoxaOS:"
echo "  uv run python main.py              # Server mode (http://0.0.0.0:7860)"
echo "  uv run python main.py --text       # Text REPL mode"
