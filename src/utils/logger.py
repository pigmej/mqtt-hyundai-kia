"""Structured logging configuration."""

import json
import logging
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for better observability."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data)


def redact_sensitive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive information from log data."""
    sensitive_keys = ["password", "pin", "token", "authorization", "auth"]
    return {
        k: "***REDACTED***" if k.lower() in sensitive_keys else v
        for k, v in data.items()
    }


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Get configured logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Avoid adding handlers multiple times
    if not logger.handlers:
        # Console handler with JSON formatting
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(JSONFormatter())
        logger.addHandler(console_handler)
    
    return logger
