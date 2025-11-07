"""Topic structure and message formatting for MQTT."""

import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


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

    def all_control_commands_topic(self) -> str:
        """Subscribe to all control commands: hyundai/+/commands/#"""
        return f"{self.base_topic}/+/commands/#"

    def extract_vehicle_id_from_topic(self, topic: str) -> Optional[str]:
        """Extract vehicle ID from command topic."""
        parts = topic.split("/")
        if len(parts) >= 2:
            return parts[1]
        return None

    # ===== Control Command Topics (Input) =====

    def lock_command_topic(self, vehicle_id: str) -> str:
        """Format: hyundai/{vehicle_id}/commands/lock"""
        return f"{self.base_topic}/{vehicle_id}/commands/lock"

    def climate_command_topic(self, vehicle_id: str) -> str:
        """Format: hyundai/{vehicle_id}/commands/climate"""
        return f"{self.base_topic}/{vehicle_id}/commands/climate"

    def windows_command_topic(self, vehicle_id: str) -> str:
        """Format: hyundai/{vehicle_id}/commands/windows"""
        return f"{self.base_topic}/{vehicle_id}/commands/windows"

    def charge_port_command_topic(self, vehicle_id: str) -> str:
        """Format: hyundai/{vehicle_id}/commands/charge_port"""
        return f"{self.base_topic}/{vehicle_id}/commands/charge_port"

    def charging_current_command_topic(self, vehicle_id: str) -> str:
        """Format: hyundai/{vehicle_id}/commands/charging_current"""
        return f"{self.base_topic}/{vehicle_id}/commands/charging_current"

    # ===== Extended Status Topics (Output) =====

    def door_topic(self, vehicle_id: str, metric: str) -> str:
        """Format: hyundai/{vehicle_id}/status/doors/{metric}"""
        return f"{self.base_topic}/{vehicle_id}/status/doors/{metric}"

    def window_topic(self, vehicle_id: str, window: str) -> str:
        """Format: hyundai/{vehicle_id}/status/windows/{window}"""
        return f"{self.base_topic}/{vehicle_id}/status/windows/{window}"

    def climate_topic(self, vehicle_id: str, metric: str) -> str:
        """Format: hyundai/{vehicle_id}/status/climate/{metric}"""
        return f"{self.base_topic}/{vehicle_id}/status/climate/{metric}"

    def location_topic(self, vehicle_id: str, metric: str) -> str:
        """Format: hyundai/{vehicle_id}/status/location/{metric}"""
        return f"{self.base_topic}/{vehicle_id}/status/location/{metric}"

    def tire_topic(self, vehicle_id: str, metric: str) -> str:
        """Format: hyundai/{vehicle_id}/status/tires/{metric}"""
        return f"{self.base_topic}/{vehicle_id}/status/tires/{metric}"

    def service_topic(self, vehicle_id: str, metric: str) -> str:
        """Format: hyundai/{vehicle_id}/status/service/{metric}"""
        return f"{self.base_topic}/{vehicle_id}/status/service/{metric}"

    def engine_topic(self, vehicle_id: str, metric: str) -> str:
        """Format: hyundai/{vehicle_id}/status/engine/{metric}"""
        return f"{self.base_topic}/{vehicle_id}/status/engine/{metric}"

    # ===== Action Confirmation Topics =====

    def action_status_topic(self, vehicle_id: str, action_id: str) -> str:
        """Format: hyundai/{vehicle_id}/action/{action_id}/status"""
        return f"{self.base_topic}/{vehicle_id}/action/{action_id}/status"

    def action_started_topic(self, vehicle_id: str, action_id: str) -> str:
        """Format: hyundai/{vehicle_id}/action/{action_id}/started_at"""
        return f"{self.base_topic}/{vehicle_id}/action/{action_id}/started_at"

    def action_completed_topic(self, vehicle_id: str, action_id: str) -> str:
        """Format: hyundai/{vehicle_id}/action/{action_id}/completed_at"""
        return f"{self.base_topic}/{vehicle_id}/action/{action_id}/completed_at"

    def action_error_topic(self, vehicle_id: str, action_id: str) -> str:
        """Format: hyundai/{vehicle_id}/action/{action_id}/error"""
        return f"{self.base_topic}/{vehicle_id}/action/{action_id}/error"

    # ===== Topic Parsing =====

    def parse_command_topic(self, topic: str) -> Optional[Tuple[str, str]]:
        """
        Parse command topic to extract vehicle_id and command_type.
        
        Returns:
            (vehicle_id, command_type) or None if invalid
        
        Example:
            "hyundai/ABC123/commands/lock" -> ("ABC123", "lock")
        """
        parts = topic.split("/")
        if len(parts) >= 4 and parts[0] == self.base_topic and parts[2] == "commands":
            return (parts[1], parts[3])
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


# Extended topic configuration with QoS and retain settings
TOPIC_CONFIG = {
    # Existing battery and EV topics
    "battery/level": {"qos": 1, "retain": True, "unit": "%"},
    "battery/charging_status": {"qos": 1, "retain": True},
    "battery/plug_status": {"qos": 1, "retain": True},
    "battery/temperature": {"qos": 0, "retain": False, "unit": "°C"},
    "ev/range": {"qos": 1, "retain": True, "unit": "km"},
    "ev/charge_time_100": {"qos": 0, "retain": False, "unit": "min"},
    "ev/charge_time_target": {"qos": 0, "retain": False, "unit": "min"},
    "ev/charge_limit": {"qos": 1, "retain": True, "unit": "%"},
    "ev/energy_consumption": {"qos": 0, "retain": False, "unit": "kWh/100km"},
    
    # EU-specific power consumption
    "ev/total_power_consumed": {"qos": 1, "retain": True, "unit": "Wh"},
    "ev/total_power_regenerated": {"qos": 1, "retain": True, "unit": "Wh"},
    "ev/power_consumption_30d": {"qos": 1, "retain": True, "unit": "Wh"},
    
    # Door status topics
    "doors/locked": {"qos": 1, "retain": True},
    "doors/front_left_open": {"qos": 1, "retain": True},
    "doors/front_right_open": {"qos": 1, "retain": True},
    "doors/back_left_open": {"qos": 1, "retain": True},
    "doors/back_right_open": {"qos": 1, "retain": True},
    "doors/trunk_open": {"qos": 1, "retain": True},
    "doors/hood_open": {"qos": 1, "retain": True},
    
    # Window status topics
    "windows/front_left": {"qos": 1, "retain": True},
    "windows/front_right": {"qos": 1, "retain": True},
    "windows/back_left": {"qos": 1, "retain": True},
    "windows/back_right": {"qos": 1, "retain": True},
    "windows/sunroof": {"qos": 1, "retain": True},
    
    # Climate status topics
    "climate/is_on": {"qos": 1, "retain": True},
    "climate/set_temperature": {"qos": 1, "retain": True, "unit": "°C"},
    "climate/current_temperature": {"qos": 0, "retain": False, "unit": "°C"},
    "climate/defrost": {"qos": 1, "retain": True},
    "climate/heated_steering_wheel": {"qos": 1, "retain": True},
    "climate/front_left_seat_status": {"qos": 1, "retain": True},
    "climate/front_right_seat_status": {"qos": 1, "retain": True},
    
    # Location topics (fire and forget to reduce overhead)
    "location/latitude": {"qos": 0, "retain": False},
    "location/longitude": {"qos": 0, "retain": False},
    "location/speed": {"qos": 0, "retain": False, "unit": "km/h"},
    "location/address": {"qos": 0, "retain": False},
    
    # Tire topics
    "tires/all_normal": {"qos": 1, "retain": True},
    "tires/front_left_warning": {"qos": 1, "retain": True},
    "tires/front_right_warning": {"qos": 1, "retain": True},
    
    # Service topics
    "service/next_service_distance": {"qos": 1, "retain": True},
    
    # Engine topics
    "engine/is_running": {"qos": 1, "retain": True},
    "engine/fuel_level": {"qos": 1, "retain": True, "unit": "%"},
    "engine/fuel_range": {"qos": 1, "retain": True, "unit": "km"},
    
    # Action confirmation topics (transient status, no retain)
    "action/*/status": {"qos": 1, "retain": False},
    "action/*/started_at": {"qos": 1, "retain": False},
    "action/*/completed_at": {"qos": 1, "retain": False},
    "action/*/error": {"qos": 1, "retain": False},
    
    # Status and error topics
    "status/last_updated": {"qos": 0, "retain": True},
    "status/data_source": {"qos": 0, "retain": True},
    "status/update_method": {"qos": 0, "retain": True},
    "status/error": {"qos": 0, "retain": True},
}
