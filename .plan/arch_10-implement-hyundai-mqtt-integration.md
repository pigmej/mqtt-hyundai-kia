# Architecture Analysis: Hyundai Bluelink MQTT Integration

## Context Analysis

This project involves creating a Python-based integration bridge between Hyundai's Bluelink API and MQTT for smart home automation. The key architectural challenge is designing an event-driven system that responds to MQTT commands while efficiently managing API interactions and respecting rate limits.

**Core Architectural Drivers:**
- **Event-driven architecture**: MQTT-triggered updates only (no polling)
- **API efficiency**: Smart refresh strategies to minimize unnecessary API calls
- **Multi-region support**: Global deployment across different Hyundai/Kia regions
- **Real-time responsiveness**: Quick response to MQTT commands while managing API latency
- **Reliability**: Robust error handling and reconnection logic

## Technology Recommendations

### Core Technologies
- **Python 3.10++**: Primary language with strong async support
- **hyundai_kia_connect_api**: Official Hyundai/Kia API client library
- **paho-mqtt**: Industry-standard MQTT client with SSL/TLS support
- **python-dotenv**: Environment-based configuration management

### Architecture Patterns
- **Adapter Pattern**: Abstract Hyundai API behind a consistent interface
- **Observer Pattern**: MQTT client observes API state changes
- **Strategy Pattern**: Different refresh strategies (cached, force, smart)
- **Circuit Breaker Pattern**: Handle API failures gracefully

## System Architecture

### High-Level Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MQTT Broker   │◄──►│  Integration     │◄──►│  Hyundai API    │
│ (External)      │    │  Service         │    │  (Cloud)        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  Configuration  │
                       │  (.env file)    │
                       └─────────────────┘
```

### Component Architecture
```
Integration Service
├── Main Application (main.py)
│   ├── Service Orchestration
│   └── Lifecycle Management
├── Configuration Layer
│   ├── Environment Variables
│   └── Validation
├── Hyundai API Layer
│   ├── VehicleManager Wrapper
│   ├── Region/Brand Handling
│   └── Refresh Strategies
├── MQTT Layer
│   ├── Connection Management
│   ├── Topic Publishing
│   └── Command Subscription
├── Data Transformation Layer
│   ├── Battery Data Mapping
│   ├── EV Data Mapping
│   └── Status Metadata
└── Error Handling Layer
    ├── Logging Framework
    ├── Retry Logic
    └── Circuit Breaker
```

## Integration Patterns

### 1. MQTT Integration Pattern
**IMPORTANT**: Implement bidirectional MQTT communication with structured topic hierarchy.

**Publish Pattern:**
- Topic: `hyundai/{vehicle_id}/{category}/{metric}`
- Payload: JSON with value, timestamp, and metadata
- QoS: At least once (QoS 1) for critical data
- Retain: True for status topics, False for real-time data

**Subscribe Pattern:**
- Topic: `hyundai/{vehicle_id}/commands/refresh`
- QoS: At least once (QoS 1)
- Payload: String command ("cached", "force", "smart:N")

### 2. API Integration Pattern
**IMPORTANT**: Implement smart refresh strategy to respect API rate limits.

**Refresh Strategies:**
- **Cached**: `update_vehicle_with_cached_state()` - Fast, local data
- **Force**: `force_refresh_vehicle_state()` - Fresh data from vehicle
- **Smart**: `check_and_force_update_vehicle(seconds)` - Conditional refresh

### 3. Error Handling Pattern
**IMPORTANT**: Implement circuit breaker pattern for API resilience.

**Error Recovery:**
- Exponential backoff for API failures
- MQTT reconnection with automatic retry
- Graceful degradation when API unavailable
- Comprehensive logging for troubleshooting

## Implementation Guidance

### Phase 1: Foundation Setup
1. **Project Structure**
   ```
   hyundai_mqtt/
   ├── src/
   │   ├── __init__.py
   │   ├── main.py
   │   ├── config/
   │   │   ├── __init__.py
   │   │   └── settings.py
   │   ├── hyundai/
   │   │   ├── __init__.py
   │   │   ├── api_client.py
   │   │   └── data_mapper.py
   │   ├── mqtt/
   │   │   ├── __init__.py
   │   │   ├── client.py
   │   │   └── topics.py
   │   └── utils/
   │       ├── __init__.py
   │       ├── logger.py
   │       └── errors.py
   ├── .env.example
   ├── pyproject.toml
   └── README.md
   ```

2. **Configuration Management**
   - Environment-based configuration using python-dotenv
   - Validation of required parameters on startup
   - Support for multiple vehicle profiles

### Phase 2: Core Integration
1. **Hyundai API Wrapper**
   - Abstract VehicleManager behind service class
   - Handle region/brand initialization
   - Implement refresh strategy pattern
   - Add error handling and retry logic

2. **MQTT Client Implementation**
   - Connection management with SSL/TLS support
   - Automatic reconnection with exponential backoff
   - Topic publishing with proper QoS settings
   - Command subscription and processing

### Phase 3: Data Transformation
1. **Battery Data Mapping**
   ```python
   # Example mapping structure
   battery_data = {
       "level": vehicle.ev_battery_percentage,
       "charging_status": vehicle.ev_charge_port_state,
       "plug_status": vehicle.ev_plug_to_vehicle_state,
       "temperature": vehicle.ev_battery_temperature
   }
   ```

2. **EV Data Mapping**
   ```python
   ev_data = {
       "range": vehicle.ev_driving_range,
       "charge_time_100": vehicle.ev_time_to_full_charge,
       "charge_time_target": vehicle.ev_target_range_charge_time,
       "charge_limit": vehicle.ev_max_charge_limit,
       "energy_consumption": vehicle.ev_energy_consumption
   }
   ```

### Phase 4: Command Processing
1. **Command Handler**
   - Parse MQTT command payloads
   - Execute appropriate refresh strategy
   - Publish updated data after refresh
   - Handle command errors gracefully

2. **Smart Refresh Logic**
   - Parse smart refresh parameters (e.g., "smart:300")
   - Implement time-based cache validation
   - Balance freshness vs. API efficiency

### Phase 5: Error Handling & Monitoring
1. **Logging Strategy**
   - Structured logging with JSON format
   - Different log levels for different components
   - Sensitive data redaction
   - Performance metrics logging

2. **Error Recovery**
   - Circuit breaker for API failures
   - MQTT connection health monitoring
   - Graceful shutdown handling
   - Status reporting via MQTT

## Critical Design Decisions

### IMPORTANT: Event-Driven Architecture
- **Decision**: No periodic polling, strictly MQTT-triggered updates
- **Rationale**: Reduces unnecessary API calls, respects rate limits, aligns with event-driven smart home patterns
- **Trade-off**: Requires explicit MQTT commands for updates, but provides better control and efficiency

### IMPORTANT: Smart Refresh Strategy
- **Decision**: Implement three-tier refresh strategy (cached/force/smart)
- **Rationale**: Balances data freshness with API efficiency and rate limit compliance
- **Trade-off**: Increased complexity in command processing, but provides optimal user experience

### IMPORTANT: Structured Topic Hierarchy
- **Decision**: Use hierarchical MQTT topics with vehicle ID separation
- **Rationale**: Supports multiple vehicles, enables selective subscription, provides clear data organization
- **Trade-off**: More complex topic management, but enables scalability and flexibility

## Security Considerations

1. **Credential Management**
   - Store credentials in environment variables only
   - Never log sensitive information
   - Implement credential validation on startup

2. **MQTT Security**
   - Use TLS/SSL encryption for MQTT connections
   - Implement authentication (username/password or certificates)
   - Consider access control lists (ACLs) for topic restrictions

3. **API Security**
   - Respect rate limits and implement backoff strategies
   - Handle authentication token refresh automatically
   - Validate API responses before processing

## Performance Considerations

1. **API Efficiency**
   - Prefer cached data when appropriate
   - Implement smart refresh to minimize unnecessary calls
   - Batch operations where possible

2. **MQTT Performance**
   - Use appropriate QoS levels (QoS 1 for critical data)
   - Implement connection pooling for multiple vehicles
   - Optimize payload size (JSON compression if needed)

3. **Memory Management**
   - Efficient data structures for vehicle state
   - Proper cleanup of unused resources
   - Monitor memory usage for long-running processes

## Scalability Considerations

1. **Multi-Vehicle Support**
   - Design for handling multiple vehicle IDs
   - Parallel processing for independent vehicles
   - Resource isolation per vehicle

2. **Region Expansion**
   - Modular region configuration
   - Easy addition of new regions/brands
   - Region-specific API endpoint handling

3. **Monitoring & Observability**
   - Health check endpoints
   - Performance metrics collection
   - Error rate monitoring

This architecture provides a solid foundation for a reliable, efficient, and scalable Hyundai Bluelink MQTT integration that meets all specified requirements while following industry best practices.
