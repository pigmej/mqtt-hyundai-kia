# Architectural Analysis: Implement EU Vehicle Control with Confirmation

## Context Analysis

### Problem Domain
The current Hyundai MQTT integration is read-only, supporting only data retrieval (battery, EV metrics). The system lacks vehicle control capabilities (doors, windows, climate) despite these being available in the underlying `hyundai_kia_connect_api` library. The critical requirement is implementing control functions with proper confirmation handling - no blind success assumptions.

### Key Constraints
- **Confirmation Pattern**: All control commands must execute → receive action_id → poll status → return final state
- **EU-Specific Features**: Heat status value 4, charging current levels, power consumption metrics
- **Real-time Updates**: Publish MQTT status updates during polling, not just final results
- **Async Safety**: All VehicleManager calls must use `asyncio.to_thread()` to prevent event loop blocking
- **Circuit Breaker**: Protection against repeated API failures must apply to control commands

### Current Architecture Assessment
The existing system provides a solid foundation:
- **API Client**: Well-structured with circuit breaker protection and refresh strategies
- **Data Mapping**: Clean dataclass-based models with proper serialization
- **Command Handling**: Queue-based command processing with error handling
- **MQTT Integration**: Topic management with QoS and retain configurations

## Technology Recommendations

### Core Architecture Patterns
1. **Command-Query Responsibility Segregation (CQRS)**
   - Separate read-only data retrieval from control commands
   - Maintain distinct data flows for status updates vs control execution

2. **Action State Machine Pattern**
   - Model action lifecycle: PENDING → (SUCCESS/FAILED/TIMEOUT/UNKNOWN)
   - Track action state with comprehensive status history
   - Support real-time status updates during execution

3. **Event-Driven Architecture**
   - Use MQTT for bidirectional communication
   - Publish action status updates as events during polling
   - Subscribe to command topics for control input

4. **Circuit Breaker Pattern**
   - Extend existing circuit breaker to protect control commands
   - Configure different thresholds for control vs read operations
   - Implement half-open state for graceful recovery

### Data Modeling Recommendations
1. **Immutable Data Classes**
   - Use dataclasses with `frozen=True` for command objects
   - Implement proper `__eq__` and `__hash__` for tracking
   - Support serialization to/from JSON for MQTT transport

2. **Action Tracking Data Model**
   - Track action_id, request_id, command_type, vehicle_id
   - Maintain timestamped status history
   - Support metadata for EU-specific configurations

3. **Extended Vehicle Data Model**
   - Comprehensive dataclasses for all vehicle systems
   - Support both current state and historical data
   - EU-specific metrics with proper units and conversions

### Async Patterns
1. **Thread Pool Integration**
   - All blocking VehicleManager calls via `asyncio.to_thread()`
   - Configure appropriate thread pool size for control operations
   - Implement proper timeout handling for thread execution

2. **Concurrent Action Management**
   - Support multiple concurrent actions per vehicle
   - Implement action deduplication and conflict resolution
   - Use asyncio.gather for parallel status polling when appropriate

## System Architecture

### Component Diagram
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MQTT Client   │    │  Command Handler │    │   API Client    │
│                 │    │                  │    │                 │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │Topic Manager│ │    │ │Action Tracker│ │    │ │Circuit Break│ │
│ └─────────────┘ │    │ └──────────────┘ │    │ │     er      │ │
│                 │    │                  │    │ └─────────────┘ │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                        ┌─────────────────┐
                        │  Data Mapper    │
                        │                 │
                        │ ┌─────────────┐ │
                        │ │Vehicle Data │ │
                        │ │  Models     │ │
                        │ └─────────────┘ │
                        └─────────────────┘
```

### Data Flow for Control Commands
1. **Command Reception**: MQTT command topic → Command Handler → Action Tracker
2. **Command Execution**: API Client → VehicleManager (via thread pool) → action_id
3. **Status Polling**: Action Tracker → API Client → VehicleManager → status updates
4. **Status Publication**: Action Tracker → MQTT status topics → real-time updates
5. **Completion**: Final status → MQTT action confirmation topics → cleanup

### Error Handling Architecture
- **EU Error Classification**: Pattern-based error recognition for EU-specific issues
- **Retry Logic**: Configurable retry policies per command type
- **Circuit Breaker States**: Different thresholds for control vs read operations
- **Graceful Degradation**: Fallback to cached data when control is unavailable

## Integration Patterns

### MQTT Topic Structure
```
Command Topics (Input):
hyundai/{vehicle_id}/commands/lock
hyundai/{vehicle_id}/commands/climate
hyundai/{vehicle_id}/commands/windows
hyundai/{vehicle_id}/commands/charge_port
hyundai/{vehicle_id}/commands/charging_current

Status Topics (Output):
hyundai/{vehicle_id}/status/doors/locked
hyundai/{vehicle_id}/status/windows/front_left
hyundai/{vehicle_id}/status/climate/temperature
hyundai/{vehicle_id}/status/location/latitude

Action Confirmation Topics:
hyundai/{vehicle_id}/status/action/{action_id}/status
hyundai/{vehicle_id}/status/action/{action_id}/error
```

### Command Payload Patterns
- **JSON-based Commands**: Structured payloads with action type and parameters
- **Validation Schema**: Validate all command inputs before execution
- **EU-Specific Parameters**: Support for EU-only features and configurations

### Status Update Patterns
- **Real-time Updates**: Publish status during polling, not just final results
- **Action Tracking**: Unique action_id for tracking command lifecycle
- **Timestamped Events**: Include timestamps for all status updates

### Data Mapping Integration
- **Bidirectional Mapping**: API objects ↔ structured data models
- **EU-Specific Mappings**: Handle EU-only metrics and configurations
- **Unit Conversions**: Support different units based on vehicle configuration

## Implementation Guidance

### Phase 1: Core Control Infrastructure
1. **Extend API Client** (`src/hyundai/api_client.py`)
   - Add control functions with confirmation patterns
   - Implement action status checking with polling
   - Ensure all calls use `asyncio.to_thread()`

2. **Create EU Action Status Module** (`src/hyundai/eu_action_status.py`)
   - EU-specific action status checking
   - Error pattern recognition and classification
   - Action state machine implementation

### Phase 2: Data Models and Mapping
1. **Extend Data Mapper** (`src/hyundai/data_mapper.py`)
   - Add comprehensive dataclasses for all vehicle systems
   - Implement EU-specific data mappings
   - Support extended vehicle status data

2. **Command Data Models** (`src/commands/handler.py`)
   - Define control command dataclasses
   - Implement command parsing and validation
   - Add action tracking functionality

### Phase 3: MQTT Integration
1. **Extend Topic Manager** (`src/mqtt/topics.py`)
   - Add control command topics
   - Add extended status topics
   - Support action confirmation topics

2. **Enhance MQTT Client** (`src/mqtt/client.py`)
   - Publish real-time status updates
   - Handle action confirmation messages
   - Support EU-specific topic configurations

### Phase 4: Command Processing
1. **Extended Command Handler**
   - Process control commands with confirmation
   - Manage action lifecycle and status polling
   - Implement EU-specific error handling

2. **Action Tracking System**
   - Track multiple concurrent actions
   - Maintain status history and metadata
   - Support action cancellation and timeout

### Critical Implementation Decisions

IMPORTANT: **No Blind Success Assumptions**
- Every control command must wait for vehicle confirmation via `check_action_status()`
- Never report success based on command execution alone
- Implement proper timeout and failure handling

IMPORTANT: **Async Safety**
- All VehicleManager calls must use `asyncio.to_thread()`
- Configure appropriate timeouts for thread execution
- Implement proper error handling for thread pool operations

IMPORTANT: **EU-Specific Considerations**
- Use heat status value 4 for "Steering Wheel and Rear Window" in EU region
- Support charging current levels (1=100%, 2=90%, 3=60%) for EU-only feature
- Implement EU-specific timeout configurations per command type
- Support EU power consumption metrics (total_power_consumed, total_power_regenerated, power_consumption_30d)

IMPORTANT: **Real-time Status Updates**
- Publish MQTT status updates during polling, not just final results
- Use action_id for tracking command lifecycle
- Support both transient status updates and persistent state

### Testing Strategy
1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test command execution and status polling
3. **EU Feature Tests**: Test EU-specific features and configurations
4. **Error Scenario Tests**: Test timeout, failure, and retry logic
5. **Concurrency Tests**: Test multiple concurrent actions
6. **Async Safety Tests**: Verify no event loop blocking

### Performance Considerations
- **Thread Pool Sizing**: Configure appropriate thread pool for control operations
- **Polling Intervals**: Optimize polling frequency vs responsiveness
- **MQTT QoS**: Use appropriate QoS levels for different message types
- **Circuit Breaker**: Tune thresholds for control vs read operations

This architectural analysis provides the foundation for implementing comprehensive vehicle control with proper confirmation handling, focusing on EU-specific requirements and maintaining the existing system's reliability and safety patterns.