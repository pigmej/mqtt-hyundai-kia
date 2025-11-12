# Task: 30 - Implement EU Vehicle Control with Confirmation

## Problem Statement
The current Hyundai MQTT integration only supports read-only data retrieval (battery, EV metrics). The system lacks vehicle control capabilities (doors, windows, climate) which are available in the underlying `hyundai_kia_connect_api` library. User requires implementation of these control functions **with proper confirmation handling** - no blind success assumptions. All control commands must wait for actual vehicle confirmation before reporting success.

### User Requirements
User specifically requested:
> "I'd like to have doors, windows, climate, but we need to make sure that we have the confirmations implemented, not assume blindly the success."

Target region: **EU (Europe)** with EU-specific features and configurations.

## Requirements

### 1. Vehicle Control Functions (EU-Specific)
Must implement control functions with EU regional considerations:
- **Lock/Unlock**: Door lock control
- **Climate Control**: Temperature, duration, defrost, seat heaters, steering wheel heater
  - EU-specific: Heat status value `4` for "Steering Wheel and Rear Window"
  - Support: temperature, duration (minutes), defrost, climate on/off, seat heaters (0-8), steering wheel (EU value 4)
- **Window Control**: Open/Close/Ventilation for each window
  - Support WINDOW_STATE: 0=CLOSED, 1=OPEN, 2=VENTILATION
- **Charge Port**: Open/Close charge port
- **Charging Current** (EU-only feature): Set AC charging current limit
  - Levels: 1=100%, 2=90%, 3=60%

### 2. Confirmation Pattern (Critical Requirement)
**No blind success assumptions** - all control commands must:
1. Execute command → receive `action_id`
2. Poll action status every 5 seconds until completion
3. Return only one of: `SUCCESS`, `FAILED`, `TIMEOUT`, `UNKNOWN`
4. Publish real-time status updates to MQTT during polling
5. Handle EU-specific timeout configurations:
   - Lock/unlock: 60 seconds
   - Climate control: 120 seconds
   - Windows: 90 seconds
   - Charge port: 60 seconds
   - Charging current: 120 seconds

### 3. Extended Data Mapping
Extend `data_mapper.py` to include comprehensive vehicle status data:
- **DoorData**: Overall lock status, individual door locks/open status, trunk, hood
- **WindowData**: WINDOW_STATE for front_left, front_right, back_left, back_right, sunroof
- **ClimateData**: Temperature, air control, defrost, heaters (steering wheel, back window, side mirrors), seat heater status
- **LocationData**: GPS coordinates, geocoded address, place name, last updated
- **TireData**: Tire pressure warnings for all tires
- **ServiceData**: Next/last service distance and units
- **EngineData**: Running status, fuel level, fuel range (for ICE/PHEV/HEV)
- **EU-Specific EV Data**: 
  - `total_power_consumed` (Wh)
  - `total_power_regenerated` (Wh)
  - `power_consumption_30d` (Wh)

### 4. MQTT Topic Structure

#### Command Topics (Input)
```
hyundai/{vehicle_id}/commands/lock
hyundai/{vehicle_id}/commands/climate
hyundai/{vehicle_id}/commands/windows
hyundai/{vehicle_id}/commands/charge_port
hyundai/{vehicle_id}/commands/charging_current  # EU-specific
```

#### Status Topics (Output)
```
hyundai/{vehicle_id}/status/doors/locked
hyundai/{vehicle_id}/status/doors/front_left_open
hyundai/{vehicle_id}/status/windows/front_left
hyundai/{vehicle_id}/status/climate/temperature
hyundai/{vehicle_id}/status/climate/steering_wheel_heater
hyundai/{vehicle_id}/status/location/latitude
hyundai/{vehicle_id}/status/location/address
hyundai/{vehicle_id}/status/ev/charging_current  # EU-specific
hyundai/{vehicle_id}/status/ev/power_consumed   # EU-specific
```

#### Action Confirmation Topics
```
hyundai/{vehicle_id}/status/action/{action_id}/status
hyundai/{vehicle_id}/status/action/{action_id}/started_at
hyundai/{vehicle_id}/status/action/{action_id}/completed_at
hyundai/{vehicle_id}/status/action/{action_id}/error
```

### 5. Command Payloads (JSON)

#### Lock/Unlock
```json
{"action": "lock"}  // or "unlock"
```

#### Climate Control (EU-specific)
```json
{
  "action": "start_climate",
  "set_temp": 22.0,
  "duration": 15,
  "defrost": true,
  "climate": true,
  "steering_wheel": 4,
  "front_left_seat": 6,
  "front_right_seat": 6
}
```

#### Windows
```json
{
  "action": "set_windows",
  "front_left": 2,  // 0=CLOSED, 1=OPEN, 2=VENTILATION
  "back_right": 0
}
```

#### Charging Current (EU only)
```json
{
  "action": "set_charging_current",
  "level": 2  // 1=100%, 2=90%, 3=60%
}
```

## Expected Outcome

### Deliverables
1. **Extended `api_client.py`** with control functions:
   - `lock_vehicle()`, `unlock_vehicle()`
   - `start_climate()`, `stop_climate()`
   - `set_windows_state()`
   - `open_charge_port()`, `close_charge_port()`
   - `set_charging_current()` (EU-specific)
   - `check_action_status()` with synchronous/asynchronous modes

2. **Extended `data_mapper.py`** with comprehensive data models:
   - All dataclasses for doors, windows, climate, location, tires, service, engine
   - Mapping functions from Vehicle object to structured data
   - EU-specific power consumption data mapping

3. **Extended `topics.py`** with control topics:
   - Topic generators for all control commands
   - Topic generators for extended status data
   - Topic generators for action confirmations
   - EU-specific topic configurations with QoS and retain settings

4. **Extended `handler.py`** with control command handling:
   - Command parsers for all control types
   - Action tracker for managing action confirmations
   - Status polling loop with EU-specific timeouts
   - EU error classification and handling
   - Action state machine with status history

5. **Comprehensive Testing** demonstrating:
   - Lock command → PENDING → SUCCESS confirmation
   - Climate command → PENDING → SUCCESS confirmation
   - Failed command → PENDING → FAILED with error message
   - Timeout scenario → PENDING → TIMEOUT
   - Real-time MQTT status updates during execution

### Success Criteria
- ✅ Control commands execute and return action_id
- ✅ Action status is polled until final state (SUCCESS/FAILED/TIMEOUT)
- ✅ MQTT publishes real-time status updates during polling
- ✅ No command reports success without vehicle confirmation
- ✅ Extended vehicle data (doors, windows, climate, location) published to MQTT
- ✅ EU-specific features (charging current, power consumption) working
- ✅ All async operations use `asyncio.to_thread()` for blocking calls
- ✅ Circuit breaker protection applies to control commands
- ✅ Error handling with EU-specific error pattern recognition

## Implementation Components

### 1. API Client Extensions (`src/hyundai/api_client.py`)
```python
# Control functions with confirmation
async def lock_vehicle(vehicle_id: str) -> str:
async def unlock_vehicle(vehicle_id: str) -> str:
async def start_climate(vehicle_id: str, options: ClimateRequestOptions) -> str:
async def stop_climate(vehicle_id: str) -> str:
async def set_windows_state(vehicle_id: str, options: WindowRequestOptions) -> str:
async def open_charge_port(vehicle_id: str) -> str:
async def close_charge_port(vehicle_id: str) -> str:
async def set_charging_current(vehicle_id: str, level: int) -> str:  # EU-only

# Action status checking
async def check_action_status(vehicle_id: str, action_id: str, synchronous: bool, timeout: int) -> ORDER_STATUS:
```

### 2. Data Mapper Extensions (`src/hyundai/data_mapper.py`)
```python
# New dataclasses
@dataclass DoorData
@dataclass WindowData
@dataclass ClimateData
@dataclass LocationData
@dataclass TireData
@dataclass ServiceData
@dataclass EngineData

# Extended VehicleData
@dataclass VehicleData:
    # ... existing fields
    doors: DoorData
    windows: WindowData
    climate: ClimateData
    location: LocationData
    tires: TireData
    service: ServiceData
    engine: EngineData
    # EU-specific
    total_power_consumed: Optional[float]
    total_power_regenerated: Optional[float]
    power_consumption_30d: Optional[float]

# Mapping functions
def map_door_data(vehicle: Vehicle) -> DoorData
def map_window_data(vehicle: Vehicle) -> WindowData
def map_climate_data(vehicle: Vehicle) -> ClimateData
def map_location_data(vehicle: Vehicle) -> LocationData
```

### 3. Topic Manager Extensions (`src/mqtt/topics.py`)
```python
def door_topic(vehicle_id: str, metric: str) -> str
def window_topic(vehicle_id: str, window: str) -> str
def climate_topic(vehicle_id: str, metric: str) -> str
def location_topic(vehicle_id: str, metric: str) -> str
def action_status_topic(vehicle_id: str, action_id: str, metric: str) -> str
def control_command_topic(vehicle_id: str, command_type: str) -> str
```

### 4. Command Handler Extensions (`src/commands/handler.py`)
```python
# Command dataclasses
@dataclass ControlCommand
@dataclass LockCommand
@dataclass ClimateCommand
@dataclass WindowsCommand
@dataclass ChargePortCommand
@dataclass ChargingCurrentCommand

# Action tracking
@dataclass ActionTracker:
    action_id: str
    request_id: str
    command_type: str
    vehicle_id: str
    started_at: datetime
    last_status: Optional[ORDER_STATUS]

# Extended handler
class ExtendedCommandHandler(CommandHandler):
    async def handle_control_command(command: ControlCommand) -> None
    async def _execute_command(command: ControlCommand) -> str
    async def _poll_action_status(tracker: ActionTracker, timeout: int) -> None
    async def _publish_action_status(tracker: ActionTracker, status: str) -> None
```

### 5. EU Action Status Module (`src/hyundai/eu_action_status.py`)
```python
class EUActionStatusChecker:
    eu_polling_intervals: dict
    eu_timeout_config: dict
    async def check_eu_action_status(...) -> ORDER_STATUS

class EUActionErrorHandler:
    EU_ERROR_PATTERNS: dict
    def classify_eu_error(error_message: str) -> dict

class EUActionStateMachine:
    async def update_action_state(...)
    async def _handle_pending_state(...)
    async def _handle_success_state(...)
    async def _handle_failed_state(...)
```

## Other Important Agreements

### EU-Specific Considerations
- **Heat Status**: Use value `4` (not `1`) for "Steering Wheel and Rear Window" in EU region
- **Charging Current**: EU-exclusive feature not available in other regions
- **Power Consumption Metrics**: Only available in EU (`total_power_consumed`, `total_power_regenerated`, `power_consumption_30d`)
- **Language Support**: EU supports multiple languages (en, de, fr, it, es, sv, nl, no, cs, sk, hu, da, pl, fi, pt)
- **Timeout Configurations**: Different command types have different EU-specific timeouts

### Architectural Decisions
- **No Blind Success**: Every control command must wait for vehicle confirmation via `check_action_status()`
- **Async Thread Pool**: All VehicleManager calls wrapped in `asyncio.to_thread()` to prevent event loop blocking
- **Action Tracking**: Maintain state for all active actions with status history
- **Real-time Updates**: Publish MQTT status updates during polling, not just final result
- **Error Classification**: EU-specific error pattern recognition for better handling
- **State Machine**: Comprehensive action lifecycle management with EU regional logic

### Data Integrity
- **WINDOW_STATE Enum**: Use IntEnum values (0=CLOSED, 1=OPEN, 2=VENTILATION), not strings
- **SEAT_STATUS Mapping**: Map integer values (0-8) to human-readable strings
- **Temperature Units**: Handle both °C and °F based on vehicle configuration
- **Distance Units**: Handle both km and miles based on vehicle configuration
- **Geocoding**: Support both OpenStreetMap and Google providers

### MQTT Quality of Service
- **Control Commands**: QoS 1 (at least once delivery)
- **Status Updates**: QoS 1 with retain for persistent state
- **Action Status**: QoS 1 without retain (transient status)
- **Location Data**: QoS 0 (fire and forget) to reduce overhead

### Testing Requirements
- Test all control commands with actual vehicle confirmation
- Test timeout scenarios (vehicle not responding)
- Test failure scenarios (vehicle rejects command)
- Test concurrent commands (multiple actions in flight)
- Test EU-specific features (charging current, power consumption)
- Test error classification and retry logic
- Verify no event loop blocking with high command volume

## Dependencies to Add
- No new dependencies required (all functionality available in existing `hyundai_kia_connect_api`)
- Ensure `hyundai_kia_connect_api` version supports all required features

## Files to Create/Modify
1. **Modify**: `src/hyundai/api_client.py` - Add control functions
2. **Modify**: `src/hyundai/data_mapper.py` - Add extended data models
3. **Modify**: `src/mqtt/topics.py` - Add control and status topics
4. **Modify**: `src/commands/handler.py` - Add control command handling
5. **Create**: `src/hyundai/eu_action_status.py` - EU-specific action status handling
6. **Modify**: `src/mqtt/client.py` - Add publishing for extended data

## Additional Context
This implementation builds upon the existing working foundation:
- Task 10: Initial MQTT integration with battery/EV data ✅
- Task 20: Fixed async blocking issues with `asyncio.to_thread()` ✅
- Task 30: Now adding full vehicle control with confirmations

The comprehensive planning discussion covered:
- Analysis of full VehicleManager API capabilities
- Confirmation pattern design (action_id → status polling → final state)
- EU-specific features and regional differences
- Data mapping for all vehicle systems
- MQTT topic structure for bidirectional control
- Command handling with action tracking
- EU error patterns and retry logic
- State machine for action lifecycle management

Critical design principle: **"No blind success assumptions"** - every control command must be confirmed by the vehicle before reporting success to the user.
