"""Topic structure and message formatting for MQTT."""

import json
from datetime import datetime
from typing import Any, Dict, Optional


class TopicManager:
    """
    Manages MQTT topic structure and message formatting.
    """

    def __init__(self, base_topic: str = "hyundai") -> None:
        self.base_topic: str = base_topic

    def battery_topic(self, vehicle_id: str, metric: str) -> str:
        """Format: hyundai/{vehicle_id}/battery/{metric}"""
        return f"{self.base_topic}/{vehicle_id}/battery/{metric}"

    def ev_topic(self, vehicle_id: str, metric: str) -> str:
        """Format: hyundai/{vehicle_id}/ev/{metric}"""
        return f"{self.base_topic}/{vehicle_id}/ev/{metric}"

    def status_topic(self, vehicle_id: str, metric: str) -> str:
        """Format: hyundai/{vehicle_id}/status/{metric}"""
        return f"{self.base_topic}/{vehicle_id}/status/{metric}"

    def command_topic(self, vehicle_id: str) -> str:
        """Format: hyundai/{vehicle_id}/commands/refresh"""
        return f"{self.base_topic}/{vehicle_id}/commands/refresh"

    def all_commands_topic(self) -> str:
        """Subscribe to all vehicle command topics: hyundai/+/commands/refresh"""
        return f"{self.base_topic}/+/commands/refresh"

    def extract_vehicle_id_from_topic(self, topic: str) -> Optional[str]:
        """Extract vehicle ID from command topic."""
        parts = topic.split("/")
        if len(parts) >= 2:
            return parts[1]
        return None

    def format_message(self, value: Any, unit: Optional[str] = None, timestamp: Optional[datetime] = None) -> str:
        """
        Format message payload as JSON with value and metadata.
        Example: {"value": 85, "timestamp": "2025-11-07T10:30:00Z", "unit": "%"}
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        payload: Dict[str, Any] = {
            "value": value,
            "timestamp": timestamp.isoformat() + "Z"
        }
        
        if unit:
            payload["unit"] = unit
        
        return json.dumps(payload)


# Topic configuration with QoS and retain settings
TOPIC_CONFIG = {
    "battery/level": {"qos": 1, "retain": True, "unit": "%"},
    "battery/charging_status": {"qos": 1, "retain": True},
    "battery/plug_status": {"qos": 1, "retain": True},
    "battery/temperature": {"qos": 0, "retain": False, "unit": "°C"},
    "ev/range": {"qos": 1, "retain": True, "unit": "km"},
    "ev/charge_time_100": {"qos": 0, "retain": False, "unit": "min"},
    "ev/charge_time_target": {"qos": 0, "retain": False, "unit": "min"},
    "ev/charge_limit": {"qos": 1, "retain": True, "unit": "%"},
    "ev/energy_consumption": {"qos": 0, "retain": False, "unit": "kWh/100km"},
    "status/last_updated": {"qos": 0, "retain": True},
    "status/data_source": {"qos": 0, "retain": True},
    "status/update_method": {"qos": 0, "retain": True},
    "status/error": {"qos": 0, "retain": True},
}
