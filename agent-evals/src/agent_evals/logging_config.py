"""Centralized logging configuration for agent-evals."""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(verbosity: int = 0) -> None:
    """Configure the agent_evals logger hierarchy.

    Args:
        verbosity: -1 for quiet (WARNING), 0 for default (INFO), 1+ for verbose (DEBUG).
    """
    global _CONFIGURED  # noqa: PLW0603

    logger = logging.getLogger("agent_evals")

    if verbosity >= 1:
        logger.setLevel(logging.DEBUG)
    elif verbosity <= -1:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)

    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(levelname)s: %(message)s"),
        )
        logger.addHandler(handler)
        _CONFIGURED = True
