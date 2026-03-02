"""Rotating JSON file logging for the Observatory server."""

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        })


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    """Configure rotating JSON file logging for agent_evals.

    Args:
        log_dir: Directory for log files (created if missing).
        level: Logging level name (e.g. "INFO", "DEBUG").
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "observatory.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    handler.setFormatter(_JSONFormatter())
    root = logging.getLogger("agent_evals")
    root.setLevel(getattr(logging, level.upper()))
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)
