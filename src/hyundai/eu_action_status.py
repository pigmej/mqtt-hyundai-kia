"""EU-specific action status checking and error handling."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from ..utils.logger import get_logger

logger = get_logger(__name__)


# EU-specific polling intervals (seconds)
EU_POLLING_INTERVALS = {
    "lock": 5,
    "unlock": 5,
    "climate_start": 5,
    "climate_stop": 5,
    "climate": 5,
    "windows": 5,
    "charge_port": 5,
    "charging_current": 5,
}

# EU-specific timeout configurations (seconds)
EU_TIMEOUT_CONFIG = {
    "lock": 60,
    "unlock": 60,
    "climate_start": 120,
    "climate_stop": 120,
    "climate": 120,
    "windows": 90,
    "charge_port": 60,
    "charging_current": 120,
}


class EUActionStatusChecker:
    """
    EU-specific action status checking with regional configurations.
    """
    
    def __init__(self, api_client: Any) -> None:
        self.api_client = api_client
    
    async def check_eu_action_status(
        self,
        vehicle_id: str,
        action_id: str,
        command_type: str
    ) -> str:
        """
        Check action status with EU-specific polling and timeout.
        
        Returns:
            Final status: "SUCCESS", "FAILED", "TIMEOUT", or "UNKNOWN"
        """
        polling_interval = EU_POLLING_INTERVALS.get(command_type, 5)
        timeout = EU_TIMEOUT_CONFIG.get(command_type, 60)
        
        logger.info(
            f"Starting EU action status check for {command_type}",
            extra={
                "action_id": action_id,
                "polling_interval": polling_interval,
                "timeout": timeout
            }
        )
        
        start_time = datetime.utcnow()
        
        while True:
            # Check status
            status = await self.api_client.check_action_status(
                vehicle_id,
                action_id,
                synchronous=False  # Get current status only
            )
            
            # Terminal states
            if status in ["SUCCESS", "FAILED", "UNKNOWN"]:
                logger.info(f"Action {action_id} reached terminal state: {status}")
                return status
            
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed >= timeout:
                logger.warning(f"Action {action_id} timed out after {elapsed}s")
                return "TIMEOUT"
            
            # Wait before next poll
            await asyncio.sleep(polling_interval)


@dataclass
class EUErrorClassification:
    """Classification of EU-specific errors."""
    error_type: str  # "timeout", "rejected", "network", "authentication", "unknown"
    is_retryable: bool
    suggested_action: str
    error_code: Optional[str] = None


class EUActionErrorHandler:
    """
    Classify and handle EU-specific action errors.
    """
    
    # EU-specific error patterns
    EU_ERROR_PATTERNS = {
        "timeout": {
            "patterns": ["timeout", "timed out", "no response"],
            "retryable": True,
            "action": "Retry command or check vehicle connectivity"
        },
        "rejected": {
            "patterns": ["rejected", "not allowed", "prohibited", "blocked"],
            "retryable": False,
            "action": "Command not allowed in current vehicle state"
        },
        "network": {
            "patterns": ["network", "connection", "unreachable", "offline"],
            "retryable": True,
            "action": "Check network connectivity and retry"
        },
        "authentication": {
            "patterns": ["authentication", "unauthorized", "invalid token", "expired"],
            "retryable": True,
            "action": "Re-authenticate and retry"
        },
        "rate_limit": {
            "patterns": ["rate limit", "too many requests", "throttled"],
            "retryable": True,
            "action": "Wait before retrying"
        },
    }
    
    @classmethod
    def classify_eu_error(cls, error_message: str) -> EUErrorClassification:
        """
        Classify error message using EU-specific patterns.
        
        Args:
            error_message: Error message from API or action status
        
        Returns:
            EUErrorClassification with error type and handling guidance
        """
        error_lower = error_message.lower()
        
        for error_type, config in cls.EU_ERROR_PATTERNS.items():
            for pattern in config["patterns"]:
                if pattern in error_lower:
                    return EUErrorClassification(
                        error_type=error_type,
                        is_retryable=config["retryable"],
                        suggested_action=config["action"]
                    )
        
        # Default: unknown error
        return EUErrorClassification(
            error_type="unknown",
            is_retryable=False,
            suggested_action="Check logs for details"
        )


class EUActionStateMachine:
    """
    State machine for EU action lifecycle management.
    
    States: PENDING -> (SUCCESS / FAILED / TIMEOUT / UNKNOWN)
    """
    
    VALID_STATES = ["PENDING", "SUCCESS", "FAILED", "TIMEOUT", "UNKNOWN"]
    TERMINAL_STATES = ["SUCCESS", "FAILED", "TIMEOUT", "UNKNOWN"]
    
    def __init__(self) -> None:
        self.current_state = "PENDING"
        self.state_history = [(datetime.utcnow(), "PENDING")]
    
    async def update_action_state(
        self,
        new_state: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update action state with validation.
        
        Args:
            new_state: New state to transition to
            metadata: Optional metadata about state transition
        
        Returns:
            True if state transition was valid, False otherwise
        """
        if new_state not in self.VALID_STATES:
            logger.error(f"Invalid state: {new_state}")
            return False
        
        # Validate state transitions
        if self.current_state in self.TERMINAL_STATES:
            logger.warning(
                f"Cannot transition from terminal state {self.current_state} to {new_state}"
            )
            return False
        
        # Record state transition
        self.current_state = new_state
        self.state_history.append((datetime.utcnow(), new_state))
        
        logger.info(
            f"Action state transitioned to {new_state}",
            extra={"metadata": metadata} if metadata else {}
        )
        
        return True
    
    def is_terminal_state(self) -> bool:
        """Check if current state is terminal."""
        return self.current_state in self.TERMINAL_STATES
    
    def get_state_duration(self) -> float:
        """Get duration in current state (seconds)."""
        if not self.state_history:
            return 0.0
        last_transition_time = self.state_history[-1][0]
        return (datetime.utcnow() - last_transition_time).total_seconds()
