"""Data mapping from Hyundai API objects to structured models."""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class BatteryData:
    """Battery-related metrics from vehicle."""
    level: Optional[float] = None  # Battery percentage (0-100)
    charging_status: Optional[str] = None  # "charging", "not_charging", etc.
    plug_status: Optional[str] = None  # "connected", "disconnected"
    temperature: Optional[float] = None  # Battery temperature in Celsius

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class EVData:
    """Electric vehicle-specific metrics."""
    range: Optional[float] = None  # Remaining range in km
    charge_time_100: Optional[int] = None  # Minutes to 100% charge
    charge_time_target: Optional[int] = None  # Minutes to target charge
    charge_limit: Optional[int] = None  # Max charge limit (%)
    energy_consumption: Optional[float] = None  # kWh/100km or similar

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class StatusData:
    """Metadata about the data fetch."""
    last_updated: datetime  # When data was last updated
    data_source: str  # "cached" or "fresh"
    update_method: str  # "cached", "force", or "smart"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO formatted timestamp."""
        return {
            "last_updated": self.last_updated.isoformat() + "Z",
            "data_source": self.data_source,
            "update_method": self.update_method
        }


@dataclass
class VehicleData:
    """Complete vehicle data payload."""
    vehicle_id: str
    battery: BatteryData
    ev: EVData
    status: StatusData

    def to_mqtt_messages(self) -> List[Tuple[str, Union[str, int, float]]]:
        """Convert to list of (metric_name, data) tuples for MQTT publishing."""
        messages: List[Tuple[str, Union[str, int, float]]] = []
        
        # Battery data
        battery_dict = self.battery.to_dict()
        for key, value in battery_dict.items():
            messages.append((f"battery/{key}", value))
        
        # EV data
        ev_dict = self.ev.to_dict()
        for key, value in ev_dict.items():
            messages.append((f"ev/{key}", value))
        
        # Status data
        status_dict = self.status.to_dict()
        for key, value in status_dict.items():
            messages.append((f"status/{key}", value))
        
        return messages


def map_battery_data(vehicle: Any) -> BatteryData:
    """Extract battery data from hyundai_kia_connect_api vehicle object."""
    return BatteryData(
        level=getattr(vehicle, 'ev_battery_percentage', None),
        charging_status=_map_charging_status(
            getattr(vehicle, 'ev_battery_is_charging', None)
        ),
        plug_status=_map_plug_status(
            getattr(vehicle, 'ev_battery_is_plugged_in', None)
        ),
        temperature=getattr(vehicle, 'ev_battery_temperature', None)
    )


def map_ev_data(vehicle: Any) -> EVData:
    """Extract EV data from vehicle object."""
    return EVData(
        range=getattr(vehicle, 'ev_driving_range', None),
        charge_time_100=getattr(vehicle, 'ev_estimated_current_charge_duration', None),
        charge_time_target=getattr(vehicle, 'ev_target_range_charge_ac', None),
        charge_limit=getattr(vehicle, 'ev_charge_limits_ac', None),
        energy_consumption=getattr(vehicle, 'ev_energy_consumption', None)
    )


def map_vehicle_data(vehicle: Any, data_source: str, update_method: str) -> VehicleData:
    """Map complete vehicle data to VehicleData model."""
    return VehicleData(
        vehicle_id=getattr(vehicle, 'id', 'unknown'),
        battery=map_battery_data(vehicle),
        ev=map_ev_data(vehicle),
        status=StatusData(
            last_updated=datetime.utcnow(),
            data_source=data_source,
            update_method=update_method
        )
    )


def _map_charging_status(is_charging: Optional[bool]) -> Optional[str]:
    """Convert boolean to human-readable status."""
    if is_charging is None:
        return None
    return "charging" if is_charging else "not_charging"


def _map_plug_status(is_plugged: Optional[bool]) -> Optional[str]:
    """Convert boolean to human-readable status."""
    if is_plugged is None:
        return None
    return "connected" if is_plugged else "disconnected"
