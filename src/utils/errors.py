"""Custom exception classes for the application."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class HyundaiMQTTError(Exception):
    """Base exception for all application errors."""
    pass


class ConfigurationError(HyundaiMQTTError):
    """Invalid or missing configuration."""
    pass


class HyundaiAPIError(HyundaiMQTTError):
    """Hyundai API errors."""
    pass


class MQTTConnectionError(HyundaiMQTTError):
    """MQTT connection errors."""
    pass


class RefreshError(HyundaiMQTTError):
    """Vehicle data refresh errors."""
    pass


class CommandError(HyundaiMQTTError):
    """Command processing errors."""
    pass


@dataclass
class ErrorContext:
    """Additional context for error reporting."""
    component: str
    operation: str
    vehicle_id: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
