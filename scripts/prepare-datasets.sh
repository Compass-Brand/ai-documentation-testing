#!/usr/bin/env bash
# prepare-datasets.sh — Idempotent dataset download + conversion.
#
# Usage:
#   bash scripts/prepare-datasets.sh           # prepare all registered datasets
#   bash scripts/prepare-datasets.sh repliqa   # prepare a single dataset
#
# Environment:
#   DATASET_CACHE_DIR  Override cache directory (default: ~/.agent-evals/datasets/)
#
# Exit codes:
#   0  All datasets prepared successfully
#   1  One or more datasets failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Resolve the agent-evals CLI via uv
if command -v uv &>/dev/null; then
    EVALS_CMD="uv run --project ${PROJECT_ROOT} agent-evals"
elif [ -x "$HOME/.local/bin/uv" ]; then
    EVALS_CMD="$HOME/.local/bin/uv run --project ${PROJECT_ROOT} agent-evals"
else
    echo "ERROR: uv is not installed. Run: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

DATASETS="${1:-all}"

# Build prepare-datasets args
ARGS="--prepare-datasets ${DATASETS}"

if [ -n "${DATASET_CACHE_DIR:-}" ]; then
    ARGS="${ARGS} --dataset-cache-dir ${DATASET_CACHE_DIR}"
fi

echo "=== Preparing datasets: ${DATASETS} ==="
echo "Command: ${EVALS_CMD} ${ARGS}"
echo

# shellcheck disable=SC2086
${EVALS_CMD} ${ARGS}
STATUS=$?

if [ ${STATUS} -eq 0 ]; then
    echo
    echo "=== All datasets prepared successfully ==="
else
    echo
    echo "=== Dataset preparation failed (exit ${STATUS}) ===" >&2
fi

exit ${STATUS}
