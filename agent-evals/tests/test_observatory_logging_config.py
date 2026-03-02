"""Tests for Observatory logging configuration."""
import logging
import pytest
from logging.handlers import RotatingFileHandler
from pathlib import Path


@pytest.fixture(autouse=True)
def _cleanup_logger():
    """Remove any RotatingFileHandlers added during tests."""
    yield
    logger = logging.getLogger("agent_evals")
    logger.handlers = [
        h for h in logger.handlers if not isinstance(h, RotatingFileHandler)
    ]


def test_setup_logging_creates_log_file_on_first_write(tmp_path):
    from agent_evals.observatory.logging_config import setup_logging
    import logging
    setup_logging(log_dir=tmp_path)
    logger = logging.getLogger("agent_evals")
    logger.info("test message")
    for handler in logger.handlers:
        handler.flush()
    # File must exist after a real write
    assert (tmp_path / "observatory.log").exists()
