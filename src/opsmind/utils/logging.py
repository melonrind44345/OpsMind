"""Structured logging configuration for OpsMind."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "extra") and record.extra:
            log_entry["extra"] = record.extra

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(log_entry)


class OpsMindLogger:
    """OpsMind structured logger wrapper."""

    def __init__(self, name: str = "opsmind", level: str = "INFO") -> None:
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))

        # Console handler (JSON for file, simple for console)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(console_handler)

        # File handler (always JSON)
        log_dir = Path(".opsmind/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "opsmind.log")
        file_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(file_handler)

    def debug(self, message: str, **extra: Any) -> None:
        if extra:
            self.logger.debug(message, extra={"extra": extra})
        else:
            self.logger.debug(message)

    def info(self, message: str, **extra: Any) -> None:
        if extra:
            self.logger.info(message, extra={"extra": extra})
        else:
            self.logger.info(message)

    def warning(self, message: str, **extra: Any) -> None:
        if extra:
            self.logger.warning(message, extra={"extra": extra})
        else:
            self.logger.warning(message)

    def error(self, message: str, **extra: Any) -> None:
        if extra:
            self.logger.error(message, extra={"extra": extra})
        else:
            self.logger.error(message)

    def critical(self, message: str, **extra: Any) -> None:
        if extra:
            self.logger.critical(message, extra={"extra": extra})
        else:
            self.logger.critical(message)


_default_logger: OpsMindLogger | None = None


def get_logger(name: str = "opsmind", level: str = "INFO") -> OpsMindLogger:
    """Get the default OpsMind logger (singleton)."""
    global _default_logger
    if _default_logger is None:
        _default_logger = OpsMindLogger(name, level)
    return _default_logger
