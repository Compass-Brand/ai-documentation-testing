#!/usr/bin/env bash
# Setup script for AI Documentation Testing (Linux/macOS)
# Usage: bash scripts/setup.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Navigate to project root (directory containing this script's parent)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
info "Project directory: $PROJECT_DIR"

# --- Check Python ---
info "Checking Python..."
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    error "Python not found. Install Python 3.11+ from https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    error "Python 3.11+ required (found $PY_VERSION)"
    exit 1
fi
info "Python $PY_VERSION found"

# --- Check/Install UV ---
info "Checking UV package manager..."
if ! command -v uv &>/dev/null; then
    warn "UV not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv &>/dev/null; then
        error "UV installation failed. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi
info "UV $(uv --version) found"

# --- Install dependencies ---
info "Installing project dependencies..."
uv sync --dev --all-packages
info "Dependencies installed"

# --- Setup .env ---
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        warn "Created .env from .env.example"
        warn "Edit .env and add your OPENROUTER_API_KEY from https://openrouter.ai/keys"
    else
        warn "No .env.example found. Create .env with: OPENROUTER_API_KEY=sk-or-v1-your-key"
    fi
else
    info ".env already exists"
fi

# --- Verify installation ---
info "Running tests to verify installation..."
if uv run python -m pytest --tb=short -q 2>&1 | tail -5; then
    info "All tests passed"
else
    warn "Some tests failed. Check output above."
fi

# --- Verify CLI tools ---
info "Verifying CLI tools..."
if uv run agent-evals --help &>/dev/null; then
    info "agent-evals CLI available"
else
    warn "agent-evals CLI not found. Try: uv run agent-evals --help"
fi

if uv run agent-index --help &>/dev/null; then
    info "agent-index CLI available"
else
    warn "agent-index CLI not found. Try: uv run agent-index --help"
fi

echo ""
info "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your OPENROUTER_API_KEY"
echo "  2. Run a dry-run:  uv run agent-evals --model openrouter/anthropic/claude-sonnet-4.5 --dry-run"
echo "  3. Run tests:      uv run python -m pytest"
echo "  4. Run evals:      uv run agent-evals --config agent-evals/examples/minimal-config.yaml"
