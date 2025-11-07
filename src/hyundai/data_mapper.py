"""Data mapping from Hyundai API objects to structured models."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union


# Seat status mapping for climate control
SEAT_STATUS_MAP = {
    0: "OFF",
    1: "LOW",
    2: "LOW",
    3: "MED",
    4: "MED",
    5: "MED",
    6: "HIGH",
    7: "HIGH",
    8: "HIGH"
}

# Window state mapping
WINDOW_STATE_MAP = {
    0: "CLOSED",
    1: "OPEN",
    2: "VENTILATION"
}


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
class DoorData:
    """Door lock and open status."""
    locked: Optional[bool] = None  # Overall lock status
    front_left_open: Optional[bool] = None
    front_right_open: Optional[bool] = None
    back_left_open: Optional[bool] = None
    back_right_open: Optional[bool] = None
    trunk_open: Optional[bool] = None
    hood_open: Optional[bool] = None
    front_left_locked: Optional[bool] = None
    front_right_locked: Optional[bool] = None
    back_left_locked: Optional[bool] = None
    back_right_locked: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class WindowData:
    """Window state (WINDOW_STATE: 0=CLOSED, 1=OPEN, 2=VENTILATION)."""
    front_left: Optional[int] = None
    front_right: Optional[int] = None
    back_left: Optional[int] = None
    back_right: Optional[int] = None
    sunroof: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with human-readable values."""
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                result[key] = {
                    "value": value,
                    "state": WINDOW_STATE_MAP.get(value, "UNKNOWN")
                }
        return result


@dataclass
class ClimateData:
    """Climate control status."""
    is_on: Optional[bool] = None
    set_temperature: Optional[float] = None  # °C or °F
    current_temperature: Optional[float] = None
    defrost: Optional[bool] = None
    heated_steering_wheel: Optional[int] = None  # EU: 4 = "Steering Wheel and Rear Window"
    heated_side_mirror: Optional[bool] = None
    heated_rear_window: Optional[bool] = None
    air_control: Optional[bool] = None
    front_left_seat_status: Optional[int] = None  # 0-8 heating level
    front_right_seat_status: Optional[int] = None
    rear_left_seat_status: Optional[int] = None
    rear_right_seat_status: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with seat status mappings."""
        result = {}
        for key, value in asdict(self).items():
            if value is None:
                continue
            if "seat_status" in key:
                result[key] = {
                    "value": value,
                    "level": SEAT_STATUS_MAP.get(value, "UNKNOWN")
                }
            else:
                result[key] = value
        return result


@dataclass
class LocationData:
    """Vehicle location and geocoded information."""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: Optional[float] = None  # km/h
    heading: Optional[int] = None  # degrees (0-360)
    altitude: Optional[float] = None  # meters
    address: Optional[str] = None  # Geocoded address
    place_name: Optional[str] = None  # Place name (if available)
    last_updated: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO formatted timestamp."""
        result = {k: v for k, v in asdict(self).items() if v is not None}
        if self.last_updated:
            result["last_updated"] = self.last_updated.isoformat() + "Z"
        return result


@dataclass
class TireData:
    """Tire pressure warnings."""
    front_left_warning: Optional[bool] = None
    front_right_warning: Optional[bool] = None
    back_left_warning: Optional[bool] = None
    back_right_warning: Optional[bool] = None
    all_normal: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ServiceData:
    """Service interval information."""
    next_service_distance: Optional[float] = None
    next_service_unit: Optional[str] = None  # "km" or "mi"
    last_service_distance: Optional[float] = None
    last_service_unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class EngineData:
    """Engine status for ICE/PHEV/HEV vehicles."""
    is_running: Optional[bool] = None
    fuel_level: Optional[float] = None  # Percentage
    fuel_range: Optional[float] = None  # km or mi
    fuel_unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class VehicleData:
    """Complete vehicle data payload with all systems."""
    vehicle_id: str
    battery: BatteryData
    ev: EVData
    status: StatusData
    # New fields with default_factory
    doors: DoorData = field(default_factory=lambda: DoorData())
    windows: WindowData = field(default_factory=lambda: WindowData())
    climate: ClimateData = field(default_factory=lambda: ClimateData())
    location: LocationData = field(default_factory=lambda: LocationData())
    tires: TireData = field(default_factory=lambda: TireData())
    service: ServiceData = field(default_factory=lambda: ServiceData())
    engine: EngineData = field(default_factory=lambda: EngineData())
    # EU-specific power consumption metrics
    total_power_consumed: Optional[float] = None  # Wh
    total_power_regenerated: Optional[float] = None  # Wh
    power_consumption_30d: Optional[float] = None  # Wh

    def to_mqtt_messages(self) -> List[Tuple[str, Union[str, int, float, Dict]]]:
        """Convert to list of (metric_name, data) tuples for MQTT publishing."""
        messages: List[Tuple[str, Union[str, int, float, Dict]]] = []
        
        # Battery data
        battery_dict = self.battery.to_dict()
        for key, value in battery_dict.items():
            messages.append((f"battery/{key}", value))
        
        # EV data
        ev_dict = self.ev.to_dict()
        for key, value in ev_dict.items():
            messages.append((f"ev/{key}", value))
        
        # New system data
        for key, value in self.doors.to_dict().items():
            messages.append((f"doors/{key}", value))
        
        for key, value in self.windows.to_dict().items():
            messages.append((f"windows/{key}", value))
        
        for key, value in self.climate.to_dict().items():
            messages.append((f"climate/{key}", value))
        
        for key, value in self.location.to_dict().items():
            messages.append((f"location/{key}", value))
        
        for key, value in self.tires.to_dict().items():
            messages.append((f"tires/{key}", value))
        
        for key, value in self.service.to_dict().items():
            messages.append((f"service/{key}", value))
        
        for key, value in self.engine.to_dict().items():
            messages.append((f"engine/{key}", value))
        
        # EU-specific power consumption
        if self.total_power_consumed is not None:
            messages.append(("ev/total_power_consumed", self.total_power_consumed))
        if self.total_power_regenerated is not None:
            messages.append(("ev/total_power_regenerated", self.total_power_regenerated))
        if self.power_consumption_30d is not None:
            messages.append(("ev/power_consumption_30d", self.power_consumption_30d))
        
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


def map_door_data(vehicle: Any) -> DoorData:
    """Extract door data from vehicle object."""
    return DoorData(
        locked=getattr(vehicle, 'door_locked', None),
        front_left_open=getattr(vehicle, 'front_left_door_open', None),
        front_right_open=getattr(vehicle, 'front_right_door_open', None),
        back_left_open=getattr(vehicle, 'back_left_door_open', None),
        back_right_open=getattr(vehicle, 'back_right_door_open', None),
        trunk_open=getattr(vehicle, 'trunk_open', None),
        hood_open=getattr(vehicle, 'hood_open', None),
        front_left_locked=getattr(vehicle, 'front_left_door_locked', None),
        front_right_locked=getattr(vehicle, 'front_right_door_locked', None),
        back_left_locked=getattr(vehicle, 'back_left_door_locked', None),
        back_right_locked=getattr(vehicle, 'back_right_door_locked', None),
    )


def map_window_data(vehicle: Any) -> WindowData:
    """Extract window data from vehicle object."""
    return WindowData(
        front_left=getattr(vehicle, 'front_left_window_state', None),
        front_right=getattr(vehicle, 'front_right_window_state', None),
        back_left=getattr(vehicle, 'back_left_window_state', None),
        back_right=getattr(vehicle, 'back_right_window_state', None),
        sunroof=getattr(vehicle, 'sunroof_state', None),
    )


def map_climate_data(vehicle: Any) -> ClimateData:
    """Extract climate data from vehicle object."""
    return ClimateData(
        is_on=getattr(vehicle, 'air_ctrl_is_on', None),
        set_temperature=getattr(vehicle, 'set_temperature', None),
        current_temperature=getattr(vehicle, 'car_battery_temperature', None),
        defrost=getattr(vehicle, 'defrost_is_on', None),
        heated_steering_wheel=getattr(vehicle, 'steering_wheel_heater_is_on', None),
        heated_side_mirror=getattr(vehicle, 'side_mirror_heater_is_on', None),
        heated_rear_window=getattr(vehicle, 'back_window_heater_is_on', None),
        air_control=getattr(vehicle, 'air_control_is_on', None),
        front_left_seat_status=getattr(vehicle, 'front_left_seat_status', None),
        front_right_seat_status=getattr(vehicle, 'front_right_seat_status', None),
        rear_left_seat_status=getattr(vehicle, 'rear_left_seat_status', None),
        rear_right_seat_status=getattr(vehicle, 'rear_right_seat_status', None),
    )


def map_location_data(vehicle: Any) -> LocationData:
    """Extract location data from vehicle object."""
    location = getattr(vehicle, 'location', None)
    if location:
        return LocationData(
            latitude=getattr(location, 'latitude', None),
            longitude=getattr(location, 'longitude', None),
            speed=getattr(location, 'speed', None),
            heading=getattr(location, 'heading', None),
            altitude=getattr(location, 'altitude', None),
            address=getattr(location, 'address', None),
            place_name=getattr(location, 'place_name', None),
            last_updated=getattr(location, 'last_updated', None),
        )
    return LocationData()


def map_tire_data(vehicle: Any) -> TireData:
    """Extract tire data from vehicle object."""
    return TireData(
        front_left_warning=getattr(vehicle, 'tire_pressure_front_left_warning', None),
        front_right_warning=getattr(vehicle, 'tire_pressure_front_right_warning', None),
        back_left_warning=getattr(vehicle, 'tire_pressure_back_left_warning', None),
        back_right_warning=getattr(vehicle, 'tire_pressure_back_right_warning', None),
        all_normal=getattr(vehicle, 'tire_pressure_all_normal', None),
    )


def map_service_data(vehicle: Any) -> ServiceData:
    """Extract service data from vehicle object."""
    return ServiceData(
        next_service_distance=getattr(vehicle, 'next_service_distance', None),
        next_service_unit=getattr(vehicle, 'next_service_distance_unit', None),
        last_service_distance=getattr(vehicle, 'last_service_distance', None),
        last_service_unit=getattr(vehicle, 'last_service_distance_unit', None),
    )


def map_engine_data(vehicle: Any) -> EngineData:
    """Extract engine data from vehicle object."""
    return EngineData(
        is_running=getattr(vehicle, 'engine_is_running', None),
        fuel_level=getattr(vehicle, 'fuel_level', None),
        fuel_range=getattr(vehicle, 'fuel_driving_range', None),
        fuel_unit=getattr(vehicle, 'fuel_distance_unit', None),
    )


def map_eu_power_consumption(vehicle: Any) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Extract EU-specific power consumption metrics."""
    return (
        getattr(vehicle, 'total_power_consumed', None),
        getattr(vehicle, 'total_power_regenerated', None),
        getattr(vehicle, 'power_consumption_30d', None),
    )


def map_vehicle_data(vehicle: Any, data_source: str, update_method: str) -> VehicleData:
    """Map complete vehicle data to VehicleData model."""
    total_consumed, total_regen, consumption_30d = map_eu_power_consumption(vehicle)
    
    return VehicleData(
        vehicle_id=getattr(vehicle, 'id', 'unknown'),
        battery=map_battery_data(vehicle),
        ev=map_ev_data(vehicle),
        status=StatusData(
            last_updated=datetime.utcnow(),
            data_source=data_source,
            update_method=update_method
        ),
        doors=map_door_data(vehicle),
        windows=map_window_data(vehicle),
        climate=map_climate_data(vehicle),
        location=map_location_data(vehicle),
        tires=map_tire_data(vehicle),
        service=map_service_data(vehicle),
        engine=map_engine_data(vehicle),
        total_power_consumed=total_consumed,
        total_power_regenerated=total_regen,
        power_consumption_30d=consumption_30d,
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
