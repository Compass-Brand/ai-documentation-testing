"""Shared test configuration for agent-evals tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Add agent-evals root to sys.path so that `pilot` package is importable
_AGENT_EVALS_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENT_EVALS_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_EVALS_ROOT))
