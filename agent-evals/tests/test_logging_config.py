"""Tests for centralized logging configuration."""

from __future__ import annotations

import logging
import sys

import pytest

from agent_evals.logging_config import configure_logging


class TestConfigureLogging:
    """Tests for configure_logging()."""

    def setup_method(self) -> None:
        """Reset the logger state before each test."""
        logger = logging.getLogger("agent_evals")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)
        # Reset the module-level flag
        import agent_evals.logging_config as mod

        mod._CONFIGURED = False

    def test_default_level_is_info(self) -> None:
        configure_logging()
        logger = logging.getLogger("agent_evals")
        assert logger.level == logging.INFO

    def test_verbose_sets_debug(self) -> None:
        configure_logging(verbosity=1)
        logger = logging.getLogger("agent_evals")
        assert logger.level == logging.DEBUG

    def test_quiet_sets_warning(self) -> None:
        configure_logging(verbosity=-1)
        logger = logging.getLogger("agent_evals")
        assert logger.level == logging.WARNING

    def test_handler_writes_to_stderr(self) -> None:
        configure_logging()
        logger = logging.getLogger("agent_evals")
        handlers = [h for h in logger.handlers if hasattr(h, "stream")]
        assert any(h.stream is sys.stderr for h in handlers)

    def test_idempotent_no_duplicate_handlers(self) -> None:
        configure_logging()
        count_before = len(logging.getLogger("agent_evals").handlers)
        configure_logging()
        count_after = len(logging.getLogger("agent_evals").handlers)
        assert count_after == count_before

    def test_reconfigure_changes_level(self) -> None:
        configure_logging(verbosity=0)
        assert logging.getLogger("agent_evals").level == logging.INFO
        configure_logging(verbosity=1)
        assert logging.getLogger("agent_evals").level == logging.DEBUG
