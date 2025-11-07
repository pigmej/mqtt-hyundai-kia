# Task: 10 - Implement Hyundai Bluelink MQTT Integration

## Problem Statement
User needs a tool to integrate Hyundai Bluelink with MQTT for smarthome automation, specifically focused on battery and EV functionalities. The integration should be MQTT-driven with no periodic updates, only updating when triggered via MQTT commands.

## Requirements
- Use Python with `hyundai_kia_connect_api` library
- Focus on battery and EV data only (other vehicle data can wait)
- MQTT-triggered updates only (no periodic polling)
- Support both cached and force refresh via MQTT commands
- Bidirectional MQTT communication (publish data, subscribe to commands)
- Handle multiple regions (Europe, Canada, USA, China, Australia, India, NZ, Brazil)
- Support multiple brands (Kia, Hyundai, Genesis)

## Expected Outcome
A working Python application that:
1. Connects to Hyundai Bluelink API using provided credentials
2. Establishes MQTT connection to broker
3. Publishes battery and EV data to structured MQTT topics
4. Listens for MQTT commands to trigger data refresh
5. Supports cached, force, and smart refresh modes
6. Handles errors gracefully with proper logging

## MQTT Topic Structure
```
hyundai/{vehicle_id}/
├── battery/
│   ├── level (percentage)
│   ├── charging_status
│   ├── plug_status
│   └── temperature
├── ev/
│   ├── range
│   ├── charge_time_100
│   ├── charge_time_target
│   ├── charge_limit
│   └── energy_consumption
├── status/
│   ├── last_updated (timestamp)
│   └── data_source ("cached" or "fresh")
└── commands/
    └── refresh (subscribe for commands)
```

## MQTT Commands
- `"cached"` -> Fast cached update using `update_vehicle_with_cached_state()`
- `"force"` -> Force refresh from car using `force_refresh_vehicle_state()`
- `"smart:300"` -> Smart refresh using `check_and_force_update_vehicle(300)`

## Other Important Agreements
- **No periodic updates**: Only update when triggered via MQTT
- **Smart refresh strategy**: Leverage library's built-in `check_and_force_update_vehicle()` method
- **API efficiency**: Respect rate limits by preferring cached updates when possible
- **Initial data fetch**: Load cached data on startup, then wait for MQTT commands
- **Configuration via environment variables**: Credentials and MQTT settings via .env file
- **Error handling**: Robust error handling with reconnection logic for both API and MQTT

## Implementation Components
1. Update `pyproject.toml` with dependencies
2. Create configuration module for credentials and MQTT settings
3. Implement MQTT client wrapper with bidirectional communication
4. Create Hyundai API wrapper using VehicleManager
5. Implement battery and EV data transformation to MQTT topics
6. Add MQTT command listener for refresh functionality
7. Implement initial data fetch on startup
8. Add logging and error handling
9. Create example configuration file and documentation

## Dependencies to Add
- `hyundai_kia_connect_api`
- `paho-mqtt`
- `python-dotenv`