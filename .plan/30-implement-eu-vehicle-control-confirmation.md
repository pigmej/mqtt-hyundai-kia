# Implementation Plan: EU Vehicle Control with Confirmation

## Implementation Overview

This implementation extends the existing Hyundai MQTT integration from read-only data retrieval to full bidirectional vehicle control with **confirmed execution**. The critical design principle is "no blind success assumptions" - every control command must wait for actual vehicle confirmation via status polling before reporting success.

### Core Architecture Extension

The implementation follows a **Command-Query Responsibility Segregation (CQRS)** pattern:
- **Query Path**: Existing read-only data retrieval (battery, EV metrics) remains unchanged
- **Command Path**: New control command execution with confirmation tracking

### Key Components to Modify/Create

1. **API Client Extension** (`src/hyundai/api_client.py`)
   - Add control command methods with action_id return
   - Implement action status polling with EU-specific timeouts
   - Extend circuit breaker to protect control operations

2. **Data Mapper Extension** (`src/hyundai/data_mapper.py`)
   - Add comprehensive dataclasses for all vehicle systems
   - Implement EU-specific data mappings
   - Support extended vehicle status data

3. **Command Handler Extension** (`src/commands/handler.py`)
   - Add control command parsing and validation
   - Implement action tracking and status polling
   - Support real-time MQTT status updates

4. **Topic Manager Extension** (`src/mqtt/topics.py`)
   - Add control command topics
   - Add extended status topics for all vehicle systems
   - Add action confirmation topics

5. **New EU Action Status Module** (`src/hyundai/eu_action_status.py`)
   - EU-specific action status checking
   - Error pattern recognition and classification
   - Action state machine implementation

### Implementation Phases

1. **Phase 1**: Core control infrastructure and action tracking
2. **Phase 2**: Extended data models and mapping
3. **Phase 3**: MQTT topic integration
4. **Phase 4**: Command processing and status polling
5. **Phase 5**: Testing and validation

---

## Component Details

### 1. API Client Extensions (`src/hyundai/api_client.py`)

#### Control Command Methods

Add methods to execute vehicle control commands with confirmation pattern:

```python
async def lock_vehicle(self, vehicle_id: str) -> str:
    """
    Lock vehicle doors.
    
    Returns:
        action_id: Unique identifier for tracking command execution
    
    Raises:
        HyundaiAPIError: If circuit breaker is open or execution fails
    """
    if not self.circuit_breaker.can_execute():
        raise HyundaiAPIError("Circuit breaker is open")
    
    try:
        logger.info(f"Executing lock command for vehicle {vehicle_id}")
        
        if not self.vehicle_manager:
            raise HyundaiAPIError("VehicleManager not initialized")
        
        # Execute via thread pool - DO NOT assume success
        action_id = await asyncio.to_thread(
            self.vehicle_manager.lock,
            vehicle_id
        )
        
        self.circuit_breaker.record_success()
        logger.info(f"Lock command initiated with action_id: {action_id}")
        return action_id
        
    except Exception as e:
        self.circuit_breaker.record_failure()
        logger.error(f"Lock command failed for vehicle {vehicle_id}: {e}")
        raise HyundaiAPIError(f"Lock command failed: {e}")
```

**Similar methods to implement**:
- `unlock_vehicle(vehicle_id: str) -> str`
- `start_climate(vehicle_id: str, options: ClimateRequestOptions) -> str`
- `stop_climate(vehicle_id: str) -> str`
- `set_windows_state(vehicle_id: str, options: WindowRequestOptions) -> str`
- `open_charge_port(vehicle_id: str) -> str`
- `close_charge_port(vehicle_id: str) -> str`
- `set_charging_current(vehicle_id: str, level: int) -> str` (EU-specific)

#### Action Status Checking

Implement status polling with EU-specific configurations:

```python
async def check_action_status(
    self,
    vehicle_id: str,
    action_id: str,
    synchronous: bool = True,
    timeout_seconds: int = 60
) -> str:
    """
    Check status of vehicle action.
    
    Args:
        vehicle_id: Vehicle identifier
        action_id: Action identifier from control command
        synchronous: If True, poll until completion; if False, return immediately
        timeout_seconds: Maximum time to wait for completion (EU-specific)
    
    Returns:
        Final status: "SUCCESS", "FAILED", "TIMEOUT", or "UNKNOWN"
    
    Implementation:
        - Polls every 5 seconds if synchronous=True
        - Returns immediately with current status if synchronous=False
        - Uses EU-specific timeout configurations per command type
    """
    if not self.circuit_breaker.can_execute():
        raise HyundaiAPIError("Circuit breaker is open")
    
    try:
        if not self.vehicle_manager:
            raise HyundaiAPIError("VehicleManager not initialized")
        
        if synchronous:
            # Poll until completion or timeout
            start_time = datetime.utcnow()
            while True:
                # Check status via thread pool
                status_response = await asyncio.to_thread(
                    self.vehicle_manager.check_action_status,
                    vehicle_id,
                    action_id
                )
                
                # Parse status from response
                status = self._parse_action_status(status_response)
                
                # Terminal states
                if status in ["SUCCESS", "FAILED", "UNKNOWN"]:
                    return status
                
                # Check timeout
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed >= timeout_seconds:
                    logger.warning(f"Action {action_id} timed out after {elapsed}s")
                    return "TIMEOUT"
                
                # Wait before next poll
                await asyncio.sleep(5)
        else:
            # Single status check
            status_response = await asyncio.to_thread(
                self.vehicle_manager.check_action_status,
                vehicle_id,
                action_id
            )
            return self._parse_action_status(status_response)
            
    except Exception as e:
        self.circuit_breaker.record_failure()
        logger.error(f"Action status check failed: {e}")
        raise HyundaiAPIError(f"Action status check failed: {e}")
```

#### EU-Specific Timeout Configuration

```python
# EU-specific timeout configurations per command type
EU_COMMAND_TIMEOUTS = {
    "lock": 60,
    "unlock": 60,
    "climate_start": 120,
    "climate_stop": 120,
    "windows": 90,
    "charge_port": 60,
    "charging_current": 120,  # EU-only feature
}
```

#### Circuit Breaker Enhancement

Extend circuit breaker to differentiate between control and read operations:

```python
class CircuitBreaker:
    def __init__(
        self,
        read_failure_threshold: int = 5,
        control_failure_threshold: int = 3,  # More sensitive for control
        timeout: int = 60
    ) -> None:
        self.read_failure_threshold = read_failure_threshold
        self.control_failure_threshold = control_failure_threshold
        self.timeout = timeout
        self.read_failure_count = 0
        self.control_failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None
    
    def can_execute(self, operation_type: str = "read") -> bool:
        """Check if circuit allows execution for operation type."""
        # Implementation distinguishes read vs control operations
        pass
```

---

### 2. Data Mapper Extensions (`src/hyundai/data_mapper.py`)

#### New Dataclasses for Vehicle Systems

**Door Data**:
```python
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
```

**Window Data**:
```python
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
        WINDOW_STATE_MAP = {
            0: "CLOSED",
            1: "OPEN",
            2: "VENTILATION"
        }
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                result[key] = {
                    "value": value,
                    "state": WINDOW_STATE_MAP.get(value, "UNKNOWN")
                }
        return result
```

**Climate Data**:
```python
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
```

**Location Data**:
```python
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
```

**Tire Data**:
```python
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
```

**Service Data**:
```python
@dataclass
class ServiceData:
    """Service interval information."""
    next_service_distance: Optional[float] = None
    next_service_unit: Optional[str] = None  # "km" or "mi"
    last_service_distance: Optional[float] = None
    last_service_unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
```

**Engine Data**:
```python
@dataclass
class EngineData:
    """Engine status for ICE/PHEV/HEV vehicles."""
    is_running: Optional[bool] = None
    fuel_level: Optional[float] = None  # Percentage
    fuel_range: Optional[float] = None  # km or mi
    fuel_unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
```

#### Extended VehicleData Dataclass

```python
@dataclass
class VehicleData:
    """Complete vehicle data payload with all systems."""
    vehicle_id: str
    battery: BatteryData
    ev: EVData
    status: StatusData
    # New fields
    doors: DoorData
    windows: WindowData
    climate: ClimateData
    location: LocationData
    tires: TireData
    service: ServiceData
    engine: EngineData
    # EU-specific power consumption metrics
    total_power_consumed: Optional[float] = None  # Wh
    total_power_regenerated: Optional[float] = None  # Wh
    power_consumption_30d: Optional[float] = None  # Wh
    
    def to_mqtt_messages(self) -> List[Tuple[str, Union[str, int, float, Dict]]]:
        """Convert to list of (metric_path, data) tuples for MQTT publishing."""
        messages = []
        
        # Existing battery and EV data
        for key, value in self.battery.to_dict().items():
            messages.append((f"battery/{key}", value))
        
        for key, value in self.ev.to_dict().items():
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
        
        # Status metadata
        for key, value in self.status.to_dict().items():
            messages.append((f"status/{key}", value))
        
        return messages
```

#### Mapping Functions

```python
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
```

#### Updated map_vehicle_data Function

```python
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
```

---

### 3. Topic Manager Extensions (`src/mqtt/topics.py`)

#### New Topic Methods

```python
class TopicManager:
    """Manages MQTT topic structure and message formatting."""
    
    # Existing methods remain unchanged
    
    # Control command topics (input)
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
    
    # All control commands subscription
    def all_control_commands_topic(self) -> str:
        """Subscribe to all control commands: hyundai/+/commands/#"""
        return f"{self.base_topic}/+/commands/#"
    
    # Extended status topics (output)
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
    
    # Action confirmation topics
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
    
    # Helper to parse command topics
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
```

#### Extended TOPIC_CONFIG

```python
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
```

---

### 4. Command Handler Extensions (`src/commands/handler.py`)

#### Control Command Dataclasses

```python
@dataclass
class ControlCommand:
    """Base class for control commands."""
    command_type: str  # "lock", "unlock", "climate", etc.
    vehicle_id: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @staticmethod
    def parse(topic: str, payload: str, topic_manager: TopicManager) -> 'ControlCommand':
        """
        Parse MQTT command topic and payload to ControlCommand.
        
        Topic format: hyundai/{vehicle_id}/commands/{command_type}
        Payload: JSON string with command parameters
        """
        parsed = topic_manager.parse_command_topic(topic)
        if not parsed:
            raise CommandError(f"Invalid command topic: {topic}")
        
        vehicle_id, command_type = parsed
        
        try:
            payload_dict = json.loads(payload)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON payload: {e}")
        
        # Validate command type
        valid_types = ["lock", "unlock", "climate", "windows", "charge_port", "charging_current"]
        if command_type not in valid_types:
            raise CommandError(f"Invalid command type: {command_type}")
        
        return ControlCommand(
            command_type=command_type,
            vehicle_id=vehicle_id,
            payload=payload_dict
        )


@dataclass
class LockCommand:
    """Lock/unlock command."""
    action: str  # "lock" or "unlock"
    vehicle_id: str
    
    @staticmethod
    def from_control_command(cmd: ControlCommand) -> 'LockCommand':
        action = cmd.payload.get("action")
        if action not in ["lock", "unlock"]:
            raise CommandError(f"Invalid lock action: {action}")
        return LockCommand(action=action, vehicle_id=cmd.vehicle_id)


@dataclass
class ClimateCommand:
    """Climate control command."""
    action: str  # "start_climate" or "stop_climate"
    vehicle_id: str
    set_temp: Optional[float] = None
    duration: Optional[int] = None  # minutes
    defrost: Optional[bool] = None
    climate: Optional[bool] = None
    steering_wheel: Optional[int] = None  # EU: 4 for "Steering Wheel and Rear Window"
    front_left_seat: Optional[int] = None  # 0-8
    front_right_seat: Optional[int] = None  # 0-8
    rear_left_seat: Optional[int] = None  # 0-8
    rear_right_seat: Optional[int] = None  # 0-8
    
    @staticmethod
    def from_control_command(cmd: ControlCommand) -> 'ClimateCommand':
        action = cmd.payload.get("action")
        if action not in ["start_climate", "stop_climate"]:
            raise CommandError(f"Invalid climate action: {action}")
        
        return ClimateCommand(
            action=action,
            vehicle_id=cmd.vehicle_id,
            set_temp=cmd.payload.get("set_temp"),
            duration=cmd.payload.get("duration"),
            defrost=cmd.payload.get("defrost"),
            climate=cmd.payload.get("climate"),
            steering_wheel=cmd.payload.get("steering_wheel"),
            front_left_seat=cmd.payload.get("front_left_seat"),
            front_right_seat=cmd.payload.get("front_right_seat"),
            rear_left_seat=cmd.payload.get("rear_left_seat"),
            rear_right_seat=cmd.payload.get("rear_right_seat"),
        )


@dataclass
class WindowsCommand:
    """Window control command."""
    vehicle_id: str
    front_left: Optional[int] = None  # 0=CLOSED, 1=OPEN, 2=VENTILATION
    front_right: Optional[int] = None
    back_left: Optional[int] = None
    back_right: Optional[int] = None
    
    @staticmethod
    def from_control_command(cmd: ControlCommand) -> 'WindowsCommand':
        # Validate window state values
        for key in ["front_left", "front_right", "back_left", "back_right"]:
            value = cmd.payload.get(key)
            if value is not None and value not in [0, 1, 2]:
                raise CommandError(f"Invalid window state for {key}: {value}")
        
        return WindowsCommand(
            vehicle_id=cmd.vehicle_id,
            front_left=cmd.payload.get("front_left"),
            front_right=cmd.payload.get("front_right"),
            back_left=cmd.payload.get("back_left"),
            back_right=cmd.payload.get("back_right"),
        )


@dataclass
class ChargePortCommand:
    """Charge port control command."""
    action: str  # "open" or "close"
    vehicle_id: str
    
    @staticmethod
    def from_control_command(cmd: ControlCommand) -> 'ChargePortCommand':
        action = cmd.payload.get("action")
        if action not in ["open", "close"]:
            raise CommandError(f"Invalid charge port action: {action}")
        return ChargePortCommand(action=action, vehicle_id=cmd.vehicle_id)


@dataclass
class ChargingCurrentCommand:
    """Charging current control command (EU-only)."""
    level: int  # 1=100%, 2=90%, 3=60%
    vehicle_id: str
    
    @staticmethod
    def from_control_command(cmd: ControlCommand) -> 'ChargingCurrentCommand':
        level = cmd.payload.get("level")
        if level not in [1, 2, 3]:
            raise CommandError(f"Invalid charging current level: {level}. Must be 1, 2, or 3.")
        return ChargingCurrentCommand(level=level, vehicle_id=cmd.vehicle_id)
```

#### Action Tracking

```python
@dataclass
class ActionTracker:
    """Track lifecycle of vehicle control actions."""
    action_id: str
    request_id: str
    command_type: str
    vehicle_id: str
    started_at: datetime
    last_status: Optional[str] = None  # "PENDING", "SUCCESS", "FAILED", "TIMEOUT", "UNKNOWN"
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    status_history: List[Tuple[datetime, str]] = field(default_factory=list)
    
    def update_status(self, status: str, error: Optional[str] = None) -> None:
        """Update action status and record in history."""
        self.last_status = status
        self.status_history.append((datetime.utcnow(), status))
        if error:
            self.error_message = error
        if status in ["SUCCESS", "FAILED", "TIMEOUT", "UNKNOWN"]:
            self.completed_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MQTT publishing."""
        return {
            "action_id": self.action_id,
            "request_id": self.request_id,
            "command_type": self.command_type,
            "vehicle_id": self.vehicle_id,
            "started_at": self.started_at.isoformat() + "Z",
            "last_status": self.last_status,
            "completed_at": self.completed_at.isoformat() + "Z" if self.completed_at else None,
            "error_message": self.error_message,
        }
```

#### Extended CommandHandler Class

```python
class CommandHandler:
    """Process MQTT commands and coordinate refresh/control operations."""
    
    def __init__(self, api_client: 'HyundaiAPIClient', mqtt_client: 'MQTTClient') -> None:
        self.api_client = api_client
        self.mqtt_client = mqtt_client
        self._command_queue = asyncio.Queue()
        self._control_command_queue = asyncio.Queue()  # Separate queue for control commands
        self._last_command_time = {}
        self._min_command_interval = 5
        self._active_actions: Dict[str, ActionTracker] = {}  # Track active actions by action_id
    
    # Existing handle_command, enqueue_command, process_commands remain unchanged
    
    async def enqueue_control_command(self, topic: str, payload: str) -> None:
        """Add control command to processing queue."""
        try:
            logger.info(f"enqueue_control_command called with topic={topic}, payload={payload}")
            command = ControlCommand.parse(topic, payload, self.mqtt_client.topic_manager)
            logger.debug(f"Control command parsed successfully: {command}")
            await self._control_command_queue.put(command)
            logger.info(f"Control command enqueued: {command.command_type} for vehicle {command.vehicle_id}")
        except CommandError as e:
            logger.error(f"Failed to parse control command: {e}")
        except Exception as e:
            logger.error(f"Failed to enqueue control command: {e}", exc_info=True)
    
    async def handle_control_command(self, command: ControlCommand) -> None:
        """
        Execute control command with confirmation pattern.
        
        Flow:
        1. Execute command → receive action_id
        2. Create ActionTracker for status polling
        3. Publish initial "PENDING" status to MQTT
        4. Start status polling task
        5. Publish real-time status updates during polling
        6. Publish final status when completed
        """
        vehicle_id = command.vehicle_id
        try:
            logger.info(f"Executing {command.command_type} control command for vehicle {vehicle_id}")
            
            # Execute command and get action_id
            action_id = await self._execute_command(command)
            
            # Create action tracker
            request_id = f"{vehicle_id}_{command.command_type}_{int(datetime.utcnow().timestamp())}"
            tracker = ActionTracker(
                action_id=action_id,
                request_id=request_id,
                command_type=command.command_type,
                vehicle_id=vehicle_id,
                started_at=datetime.utcnow(),
                last_status="PENDING"
            )
            self._active_actions[action_id] = tracker
            
            # Publish initial status
            await self._publish_action_status(tracker, "PENDING")
            
            # Start status polling task (non-blocking)
            asyncio.create_task(self._poll_action_status(tracker))
            
            logger.info(f"Control command initiated with action_id: {action_id}")
            
        except Exception as e:
            logger.error(f"Control command execution failed for vehicle {vehicle_id}: {e}")
            # Publish error status
            try:
                await self.mqtt_client.publish_error_status(
                    vehicle_id,
                    {
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "command_type": command.command_type,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                )
            except Exception as pub_error:
                logger.error(f"Failed to publish error status: {pub_error}")
    
    async def _execute_command(self, command: ControlCommand) -> str:
        """
        Execute specific control command and return action_id.
        
        Dispatches to appropriate API client method based on command type.
        """
        vehicle_id = command.vehicle_id
        
        if command.command_type == "lock":
            lock_cmd = LockCommand.from_control_command(command)
            if lock_cmd.action == "lock":
                return await self.api_client.lock_vehicle(vehicle_id)
            else:
                return await self.api_client.unlock_vehicle(vehicle_id)
        
        elif command.command_type == "climate":
            climate_cmd = ClimateCommand.from_control_command(command)
            if climate_cmd.action == "start_climate":
                # Create ClimateRequestOptions from command
                options = self._create_climate_options(climate_cmd)
                return await self.api_client.start_climate(vehicle_id, options)
            else:
                return await self.api_client.stop_climate(vehicle_id)
        
        elif command.command_type == "windows":
            windows_cmd = WindowsCommand.from_control_command(command)
            options = self._create_windows_options(windows_cmd)
            return await self.api_client.set_windows_state(vehicle_id, options)
        
        elif command.command_type == "charge_port":
            charge_cmd = ChargePortCommand.from_control_command(command)
            if charge_cmd.action == "open":
                return await self.api_client.open_charge_port(vehicle_id)
            else:
                return await self.api_client.close_charge_port(vehicle_id)
        
        elif command.command_type == "charging_current":
            current_cmd = ChargingCurrentCommand.from_control_command(command)
            return await self.api_client.set_charging_current(vehicle_id, current_cmd.level)
        
        else:
            raise CommandError(f"Unknown command type: {command.command_type}")
    
    async def _poll_action_status(self, tracker: ActionTracker) -> None:
        """
        Poll action status until completion.
        
        Publishes real-time status updates to MQTT during polling.
        Uses EU-specific timeout configurations per command type.
        """
        from ..hyundai.api_client import EU_COMMAND_TIMEOUTS
        
        timeout = EU_COMMAND_TIMEOUTS.get(tracker.command_type, 60)
        
        try:
            logger.info(f"Starting status polling for action {tracker.action_id}")
            
            # Poll until completion or timeout
            final_status = await self.api_client.check_action_status(
                tracker.vehicle_id,
                tracker.action_id,
                synchronous=True,
                timeout_seconds=timeout
            )
            
            # Update tracker
            tracker.update_status(final_status)
            
            # Publish final status
            await self._publish_action_status(tracker, final_status)
            
            # If successful, refresh vehicle data to get updated state
            if final_status == "SUCCESS":
                logger.info(f"Action {tracker.action_id} completed successfully, refreshing vehicle data")
                data = await self.api_client.refresh_force(tracker.vehicle_id)
                await self.mqtt_client.publish_vehicle_data(data)
            
            logger.info(f"Status polling completed for action {tracker.action_id}: {final_status}")
            
        except Exception as e:
            logger.error(f"Status polling failed for action {tracker.action_id}: {e}")
            tracker.update_status("FAILED", str(e))
            await self._publish_action_status(tracker, "FAILED", str(e))
        
        finally:
            # Cleanup
            if tracker.action_id in self._active_actions:
                del self._active_actions[tracker.action_id]
    
    async def _publish_action_status(
        self,
        tracker: ActionTracker,
        status: str,
        error: Optional[str] = None
    ) -> None:
        """Publish action status to MQTT action confirmation topics."""
        topic_manager = self.mqtt_client.topic_manager
        
        # Publish status
        status_topic = topic_manager.action_status_topic(tracker.vehicle_id, tracker.action_id)
        await self.mqtt_client.publish(status_topic, status, qos=1, retain=False)
        
        # Publish started_at timestamp
        if tracker.started_at:
            started_topic = topic_manager.action_started_topic(tracker.vehicle_id, tracker.action_id)
            await self.mqtt_client.publish(
                started_topic,
                tracker.started_at.isoformat() + "Z",
                qos=1,
                retain=False
            )
        
        # Publish completed_at timestamp if completed
        if tracker.completed_at:
            completed_topic = topic_manager.action_completed_topic(tracker.vehicle_id, tracker.action_id)
            await self.mqtt_client.publish(
                completed_topic,
                tracker.completed_at.isoformat() + "Z",
                qos=1,
                retain=False
            )
        
        # Publish error if present
        if error:
            error_topic = topic_manager.action_error_topic(tracker.vehicle_id, tracker.action_id)
            await self.mqtt_client.publish(error_topic, error, qos=1, retain=False)
        
        logger.debug(f"Published action status: {status} for action {tracker.action_id}")
    
    def _create_climate_options(self, cmd: ClimateCommand) -> Dict[str, Any]:
        """Create ClimateRequestOptions dictionary from ClimateCommand."""
        options = {}
        if cmd.set_temp is not None:
            options["set_temp"] = cmd.set_temp
        if cmd.duration is not None:
            options["duration"] = cmd.duration
        if cmd.defrost is not None:
            options["defrost"] = cmd.defrost
        if cmd.climate is not None:
            options["climate"] = cmd.climate
        if cmd.steering_wheel is not None:
            options["steering_wheel"] = cmd.steering_wheel
        if cmd.front_left_seat is not None:
            options["front_left_seat"] = cmd.front_left_seat
        if cmd.front_right_seat is not None:
            options["front_right_seat"] = cmd.front_right_seat
        if cmd.rear_left_seat is not None:
            options["rear_left_seat"] = cmd.rear_left_seat
        if cmd.rear_right_seat is not None:
            options["rear_right_seat"] = cmd.rear_right_seat
        return options
    
    def _create_windows_options(self, cmd: WindowsCommand) -> Dict[str, Any]:
        """Create WindowRequestOptions dictionary from WindowsCommand."""
        options = {}
        if cmd.front_left is not None:
            options["front_left"] = cmd.front_left
        if cmd.front_right is not None:
            options["front_right"] = cmd.front_right
        if cmd.back_left is not None:
            options["back_left"] = cmd.back_left
        if cmd.back_right is not None:
            options["back_right"] = cmd.back_right
        return options
    
    async def process_control_commands(self) -> None:
        """Process control commands from queue (main control command loop)."""
        logger.info("Starting control command processing loop")
        
        while True:
            try:
                logger.debug("Waiting for control command from queue...")
                command = await self._control_command_queue.get()
                logger.info(f"Retrieved control command from queue: {command.command_type} for vehicle {command.vehicle_id}")
                await self.handle_control_command(command)
                logger.debug("Control command handling completed")
            except asyncio.CancelledError:
                logger.info("Control command processing loop cancelled")
                raise
            except Exception as e:
                logger.error(f"Error processing control command: {e}", exc_info=True)
```

---

### 5. New EU Action Status Module (`src/hyundai/eu_action_status.py`)

This new module provides EU-specific action status handling:

```python
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
```

---

## Data Structures

### Command Payload Examples

**Lock Command**:
```json
{
  "action": "lock"
}
```

**Unlock Command**:
```json
{
  "action": "unlock"
}
```

**Start Climate (EU-specific)**:
```json
{
  "action": "start_climate",
  "set_temp": 22.0,
  "duration": 15,
  "defrost": true,
  "climate": true,
  "steering_wheel": 4,
  "front_left_seat": 6,
  "front_right_seat": 6,
  "rear_left_seat": 0,
  "rear_right_seat": 0
}
```

**Stop Climate**:
```json
{
  "action": "stop_climate"
}
```

**Set Windows**:
```json
{
  "action": "set_windows",
  "front_left": 2,
  "front_right": 0,
  "back_left": 0,
  "back_right": 0
}
```

**Open Charge Port**:
```json
{
  "action": "open"
}
```

**Set Charging Current (EU-only)**:
```json
{
  "action": "set_charging_current",
  "level": 2
}
```

### Action Status Response Structure

Published to MQTT action confirmation topics:

```json
{
  "action_id": "abc123def456",
  "request_id": "XYZ789_lock_1730982000",
  "command_type": "lock",
  "vehicle_id": "XYZ789",
  "started_at": "2025-11-07T10:00:00Z",
  "last_status": "SUCCESS",
  "completed_at": "2025-11-07T10:00:45Z",
  "error_message": null
}
```

### Extended Vehicle Data Structure

Example of complete VehicleData published to MQTT:

```json
{
  "vehicle_id": "ABC123",
  "battery": {
    "level": 85,
    "charging_status": "not_charging",
    "plug_status": "disconnected"
  },
  "ev": {
    "range": 320,
    "charge_limit": 90,
    "total_power_consumed": 15000,
    "total_power_regenerated": 3000,
    "power_consumption_30d": 450
  },
  "doors": {
    "locked": true,
    "front_left_open": false,
    "trunk_open": false
  },
  "windows": {
    "front_left": {
      "value": 0,
      "state": "CLOSED"
    }
  },
  "climate": {
    "is_on": false,
    "set_temperature": 22.0,
    "front_left_seat_status": {
      "value": 0,
      "level": "OFF"
    }
  },
  "location": {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "address": "London, UK"
  }
}
```

---

## API Design

### Control Command API Flow

```
1. User/System publishes command to MQTT
   Topic: hyundai/{vehicle_id}/commands/lock
   Payload: {"action": "lock"}

2. MQTT Client receives message
   → Routes to CommandHandler.enqueue_control_command()

3. CommandHandler parses and validates command
   → Creates ControlCommand object
   → Adds to _control_command_queue

4. CommandHandler.process_control_commands() retrieves command
   → Calls handle_control_command()

5. handle_control_command() executes command
   → Calls APIClient.lock_vehicle()
   → Receives action_id
   → Creates ActionTracker
   → Publishes "PENDING" status to MQTT

6. Async task starts status polling
   → Calls _poll_action_status()
   → Polls every 5 seconds via check_action_status()
   → Publishes real-time status updates to MQTT

7. Final status received
   → Updates ActionTracker
   → Publishes final status to MQTT
   → If SUCCESS: force refresh vehicle data
   → Cleanup action tracker

8. Updated vehicle data published to MQTT
   → All status topics updated with fresh data
```

### Action Status Polling Pattern

```python
# Synchronous polling (used by action tracker)
status = await api_client.check_action_status(
    vehicle_id="ABC123",
    action_id="xyz789",
    synchronous=True,  # Poll until completion
    timeout_seconds=60
)
# Returns: "SUCCESS" | "FAILED" | "TIMEOUT" | "UNKNOWN"

# Asynchronous single check (used internally)
status = await api_client.check_action_status(
    vehicle_id="ABC123",
    action_id="xyz789",
    synchronous=False,  # Return immediately
    timeout_seconds=0
)
# Returns: Current status
```

### Error Handling Pattern

```python
try:
    action_id = await api_client.lock_vehicle(vehicle_id)
except HyundaiAPIError as e:
    # Handle API errors
    classification = EUActionErrorHandler.classify_eu_error(str(e))
    if classification.is_retryable:
        # Implement retry logic
        pass
    else:
        # Publish error to MQTT
        pass
```

---

## Testing Strategy

### 1. Unit Tests

**API Client Control Methods** (`tests/test_api_client_control.py`):
```python
async def test_lock_vehicle_returns_action_id():
    """Test lock_vehicle returns action_id, not success status."""
    pass

async def test_check_action_status_synchronous_polls_until_completion():
    """Test synchronous polling continues until terminal state."""
    pass

async def test_check_action_status_respects_timeout():
    """Test polling stops after timeout and returns TIMEOUT."""
    pass

async def test_circuit_breaker_protects_control_operations():
    """Test circuit breaker opens after control command failures."""
    pass
```

**Data Mapper Extensions** (`tests/test_data_mapper_extended.py`):
```python
def test_map_door_data():
    """Test door data mapping from vehicle object."""
    pass

def test_map_window_data_with_state_enum():
    """Test window data maps WINDOW_STATE integers correctly."""
    pass

def test_map_climate_data_eu_specific():
    """Test climate data maps EU-specific heat status value 4."""
    pass

def test_map_eu_power_consumption():
    """Test EU power consumption metrics mapping."""
    pass

def test_vehicle_data_to_mqtt_messages_includes_all_systems():
    """Test complete vehicle data converts to MQTT messages."""
    pass
```

**Command Parsing** (`tests/test_command_parsing.py`):
```python
def test_parse_lock_command():
    """Test lock command parsing from MQTT payload."""
    pass

def test_parse_climate_command_with_eu_options():
    """Test climate command parsing with EU-specific options."""
    pass

def test_parse_windows_command_validates_state():
    """Test windows command validates state values (0, 1, 2)."""
    pass

def test_parse_charging_current_validates_level():
    """Test charging current command validates EU levels (1, 2, 3)."""
    pass

def test_invalid_command_raises_error():
    """Test invalid command raises CommandError."""
    pass
```

**Action Tracking** (`tests/test_action_tracking.py`):
```python
def test_action_tracker_status_updates():
    """Test action tracker updates status correctly."""
    pass

def test_action_tracker_maintains_history():
    """Test action tracker maintains status history."""
    pass

def test_action_tracker_records_error():
    """Test action tracker records error messages."""
    pass

def test_action_tracker_to_dict():
    """Test action tracker converts to dictionary for MQTT."""
    pass
```

### 2. Integration Tests

**Control Command Execution** (`tests/integration/test_control_execution.py`):
```python
async def test_lock_command_full_flow():
    """
    Test complete lock command flow:
    1. Publish command to MQTT
    2. Command handler executes
    3. Action status polled
    4. Final status published
    5. Vehicle data refreshed
    """
    pass

async def test_climate_command_with_eu_options():
    """Test climate command with EU-specific options."""
    pass

async def test_multiple_concurrent_commands():
    """Test multiple actions can be tracked concurrently."""
    pass

async def test_command_timeout_scenario():
    """Test command that times out publishes TIMEOUT status."""
    pass

async def test_command_failure_scenario():
    """Test command that fails publishes FAILED status with error."""
    pass
```

**MQTT Topic Integration** (`tests/integration/test_mqtt_topics.py`):
```python
async def test_control_command_topics_subscribed():
    """Test all control command topics are subscribed."""
    pass

async def test_action_status_published_to_correct_topics():
    """Test action status published to action confirmation topics."""
    pass

async def test_extended_vehicle_data_published_to_all_topics():
    """Test extended vehicle data published to all status topics."""
    pass
```

### 3. EU Feature Tests

**EU-Specific Functionality** (`tests/eu/test_eu_features.py`):
```python
async def test_eu_climate_heat_status_value_4():
    """Test EU climate command uses heat status value 4."""
    pass

async def test_eu_charging_current_levels():
    """Test EU charging current levels (1=100%, 2=90%, 3=60%)."""
    pass

async def test_eu_power_consumption_metrics():
    """Test EU power consumption metrics are mapped and published."""
    pass

async def test_eu_action_timeouts():
    """Test EU-specific timeout configurations per command type."""
    pass

async def test_eu_error_classification():
    """Test EU error patterns are recognized correctly."""
    pass
```

### 4. Error Scenario Tests

**Error Handling** (`tests/test_error_scenarios.py`):
```python
async def test_timeout_returns_timeout_status():
    """Test action that times out returns TIMEOUT status."""
    pass

async def test_failure_returns_failed_status_with_error():
    """Test action that fails returns FAILED status with error message."""
    pass

async def test_retryable_error_classification():
    """Test retryable errors are classified correctly."""
    pass

async def test_non_retryable_error_classification():
    """Test non-retryable errors are classified correctly."""
    pass

async def test_circuit_breaker_opens_on_repeated_failures():
    """Test circuit breaker opens after threshold failures."""
    pass

async def test_circuit_breaker_recovers_in_half_open():
    """Test circuit breaker recovers after timeout in HALF_OPEN state."""
    pass
```

### 5. Concurrency Tests

**Concurrent Operations** (`tests/test_concurrency.py`):
```python
async def test_multiple_vehicles_concurrent_commands():
    """Test commands for multiple vehicles execute concurrently."""
    pass

async def test_same_vehicle_sequential_commands():
    """Test sequential commands for same vehicle are queued correctly."""
    pass

async def test_action_tracker_cleanup():
    """Test action trackers are cleaned up after completion."""
    pass
```

### 6. Async Safety Tests

**Event Loop Blocking** (`tests/test_async_safety.py`):
```python
async def test_no_blocking_calls_in_control_methods():
    """Test all VehicleManager calls use asyncio.to_thread()."""
    pass

async def test_high_command_volume_no_blocking():
    """Test high volume of commands doesn't block event loop."""
    pass

async def test_status_polling_non_blocking():
    """Test status polling doesn't block other operations."""
    pass
```

### Testing Tools and Mocks

**Mock Vehicle Manager**:
```python
class MockVehicleManager:
    """Mock VehicleManager for testing without real API calls."""
    
    def lock(self, vehicle_id: str) -> str:
        """Return mock action_id."""
        return "mock_action_123"
    
    def check_action_status(self, vehicle_id: str, action_id: str) -> dict:
        """Return mock status response."""
        return {"status": "SUCCESS"}
```

**Test Fixtures**:
```python
@pytest.fixture
async def api_client():
    """Fixture providing configured API client."""
    pass

@pytest.fixture
async def mqtt_client():
    """Fixture providing configured MQTT client."""
    pass

@pytest.fixture
async def command_handler(api_client, mqtt_client):
    """Fixture providing configured command handler."""
    pass
```

---

## Development Phases

### Phase 1: Core Control Infrastructure (Days 1-3)

**Objectives**:
- Extend API client with control command methods
- Implement action status checking with polling
- Extend circuit breaker for control operations

**Deliverables**:
1. `api_client.py` extended with:
   - `lock_vehicle()`, `unlock_vehicle()`
   - `start_climate()`, `stop_climate()`
   - `set_windows_state()`
   - `open_charge_port()`, `close_charge_port()`
   - `set_charging_current()`
   - `check_action_status()` with synchronous/asynchronous modes
   - EU_COMMAND_TIMEOUTS configuration
   - Enhanced CircuitBreaker class

2. Unit tests for all control methods
3. Integration tests for action status polling

**Success Criteria**:
- All control methods execute and return action_id
- Status polling continues until terminal state
- Timeout handling works correctly
- Circuit breaker protects control operations
- No blocking calls (all use `asyncio.to_thread()`)

---

### Phase 2: Extended Data Models and Mapping (Days 4-5)

**Objectives**:
- Add comprehensive dataclasses for all vehicle systems
- Implement mapping functions from Vehicle objects
- Support EU-specific data metrics

**Deliverables**:
1. `data_mapper.py` extended with:
   - DoorData, WindowData, ClimateData dataclasses
   - LocationData, TireData, ServiceData, EngineData dataclasses
   - Extended VehicleData dataclass
   - All mapping functions
   - EU power consumption mapping
   - Updated `to_mqtt_messages()` method

2. Unit tests for all dataclasses and mapping functions
3. EU-specific data mapping tests

**Success Criteria**:
- All vehicle systems have dataclass representations
- Mapping functions extract all available data
- EU-specific metrics are included
- WINDOW_STATE enum values mapped correctly
- SEAT_STATUS values mapped to levels
- Extended vehicle data converts to MQTT messages

---

### Phase 3: MQTT Topic Integration (Days 6-7)

**Objectives**:
- Extend topic manager with control and status topics
- Add action confirmation topics
- Update MQTT client for extended publishing

**Deliverables**:
1. `topics.py` extended with:
   - Control command topic methods
   - Extended status topic methods
   - Action confirmation topic methods
   - Topic parsing helpers
   - Extended TOPIC_CONFIG

2. `client.py` updated for:
   - Publishing extended vehicle data
   - Publishing action status updates
   - Subscribing to all control command topics

3. Integration tests for topic publishing/subscription

**Success Criteria**:
- All control command topics defined
- All extended status topics defined
- Action confirmation topics defined
- QoS and retain settings configured correctly
- MQTT client publishes to all extended topics
- Topic parsing works correctly

---

### Phase 4: Command Processing and Status Polling (Days 8-10)

**Objectives**:
- Extend command handler with control command processing
- Implement action tracking and status polling
- Create EU action status module
- Support real-time MQTT status updates

**Deliverables**:
1. `handler.py` extended with:
   - ControlCommand and specific command dataclasses
   - ActionTracker class
   - Control command parsing and validation
   - `handle_control_command()` method
   - `_execute_command()` dispatcher
   - `_poll_action_status()` polling loop
   - `_publish_action_status()` status publisher
   - `process_control_commands()` main loop

2. New `eu_action_status.py` module with:
   - EUActionStatusChecker class
   - EUActionErrorHandler class
   - EUActionStateMachine class
   - EU-specific configurations

3. Integration tests for complete command flow
4. EU feature tests
5. Error scenario tests
6. Concurrency tests

**Success Criteria**:
- Control commands parsed and validated correctly
- Commands execute and return action_id
- ActionTracker manages lifecycle correctly
- Status polling continues until completion
- Real-time status updates published to MQTT
- EU-specific timeouts respected
- EU error patterns recognized
- No blind success assumptions
- Multiple concurrent actions supported
- Vehicle data refreshed after successful commands

---

### Phase 5: Testing and Validation (Days 11-12)

**Objectives**:
- Comprehensive testing of all components
- Integration testing with real API (if available)
- Performance and load testing
- Documentation and examples

**Deliverables**:
1. Complete test suite:
   - Unit tests (>90% coverage)
   - Integration tests
   - EU feature tests
   - Error scenario tests
   - Concurrency tests
   - Async safety tests

2. Test documentation and examples
3. Command payload examples
4. MQTT topic documentation
5. Troubleshooting guide

**Success Criteria**:
- All tests passing
- >90% code coverage
- No event loop blocking detected
- Circuit breaker functioning correctly
- EU-specific features validated
- Error handling comprehensive
- Performance acceptable under load
- Documentation complete

---

## Key Implementation Guidelines

### IMPORTANT: No Blind Success Assumptions

**Every control command MUST**:
1. Execute command via API client
2. Receive action_id (NOT success status)
3. Create ActionTracker with "PENDING" status
4. Poll action status every 5 seconds
5. Publish real-time status updates during polling
6. Wait for terminal state: SUCCESS, FAILED, TIMEOUT, or UNKNOWN
7. Only report success after receiving SUCCESS from vehicle

**NEVER**:
- Assume command succeeded based on execution alone
- Report success without polling action status
- Skip timeout handling
- Ignore FAILED or UNKNOWN states

### IMPORTANT: Async Safety

**All blocking operations MUST use `asyncio.to_thread()`**:
```python
# CORRECT
action_id = await asyncio.to_thread(
    self.vehicle_manager.lock,
    vehicle_id
)

# WRONG - blocks event loop
action_id = self.vehicle_manager.lock(vehicle_id)
```

**Apply to**:
- All VehicleManager method calls
- Action status checking
- Token refresh operations
- Vehicle data updates

### IMPORTANT: EU-Specific Considerations

**Heat Status Value**:
- Use value `4` for "Steering Wheel and Rear Window" in EU region
- NOT value `1` (different meaning in EU vs other regions)

**Charging Current Levels**:
- EU-only feature not available in other regions
- Valid levels: 1=100%, 2=90%, 3=60%
- Validate level before sending command

**Power Consumption Metrics**:
- Only available in EU region
- Include in data mapping: total_power_consumed, total_power_regenerated, power_consumption_30d
- Units: Wh (Watt-hours)

**Timeout Configurations**:
- Use EU-specific timeouts per command type
- Different from other regions
- Configuration in `EU_COMMAND_TIMEOUTS`

### IMPORTANT: Real-time Status Updates

**Status updates during polling**:
- Publish to action confirmation topics immediately when received
- Don't wait for completion to publish updates
- Use QoS 1, retain=False for transient status
- Include timestamps for all status changes

**Action confirmation topics**:
```
hyundai/{vehicle_id}/action/{action_id}/status
hyundai/{vehicle_id}/action/{action_id}/started_at
hyundai/{vehicle_id}/action/{action_id}/completed_at
hyundai/{vehicle_id}/action/{action_id}/error
```

### IMPORTANT: Error Handling

**EU error classification**:
- Use pattern matching to classify errors
- Distinguish retryable vs non-retryable errors
- Provide suggested actions for error types
- Log detailed error information

**Circuit breaker**:
- Different thresholds for control vs read operations
- Control operations more sensitive (threshold=3)
- Read operations less sensitive (threshold=5)
- Recovery in HALF_OPEN state after timeout

### IMPORTANT: Data Integrity

**WINDOW_STATE Enum**:
- Use IntEnum values: 0=CLOSED, 1=OPEN, 2=VENTILATION
- NOT strings like "closed", "open"
- Validate values before sending commands

**SEAT_STATUS Mapping**:
- Map integer values (0-8) to levels: OFF, LOW, MED, HIGH
- Provide both raw value and human-readable level in MQTT

**Temperature Units**:
- Handle both °C and °F based on vehicle configuration
- Convert appropriately for display

**Distance Units**:
- Handle both km and miles based on vehicle configuration
- Include unit in MQTT payload

---

## Summary

This implementation plan provides a comprehensive roadmap for extending the Hyundai MQTT integration with full vehicle control capabilities, focusing on:

1. **Confirmed Execution**: No blind success assumptions - all commands wait for vehicle confirmation
2. **EU-Specific Features**: Heat status value 4, charging current levels, power consumption metrics
3. **Real-time Updates**: MQTT status updates during polling, not just final results
4. **Async Safety**: All blocking calls wrapped in `asyncio.to_thread()`
5. **Comprehensive Data**: Extended data models for all vehicle systems
6. **Robust Error Handling**: EU-specific error classification and retry logic
7. **Action Tracking**: Complete lifecycle management with status history

The implementation is structured in 5 phases over 12 days, with clear deliverables and success criteria for each phase. The plan maintains backward compatibility with existing read-only functionality while adding new control capabilities through a CQRS architecture pattern.
