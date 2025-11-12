# Hyundai MQTT Integration

MQTT-driven integration with Hyundai Bluelink API for battery and EV data automation.

## Overview

This service connects your Hyundai/Kia/Genesis electric vehicle to an MQTT broker, allowing you to:
- Retrieve battery level, charging status, and EV range data
- Trigger data updates via MQTT commands (no periodic polling)
- Integrate with smart home systems like Home Assistant
- Support multiple refresh strategies (cached, force, smart)

## Features

- **Event-Driven**: No periodic polling - updates only when you request them via MQTT
- **Three Refresh Modes**:
  - `cached`: Fast, uses locally cached data
  - `force`: Contacts vehicle directly for fresh data
  - `smart`: Conditionally refreshes based on data age
- **Multi-Region Support**: Works with Hyundai/Kia/Genesis across multiple regions
- **Robust Error Handling**: Circuit breaker pattern, automatic MQTT reconnection
- **Structured Logging**: JSON-formatted logs for observability

## Installation

### Prerequisites

- Python 3.10 or higher
- MQTT broker (e.g., Mosquitto)
- Hyundai/Kia/Genesis Bluelink account

### Install Dependencies

```bash
pip install -e .
```

Or manually install:

```bash
pip install hyundai-kia-connect-api paho-mqtt python-dotenv
```

## Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` with your credentials:

```bash
# Hyundai API Configuration
HYUNDAI_USERNAME=your_email@example.com
HYUNDAI_PASSWORD=your_password
HYUNDAI_PIN=your_pin
HYUNDAI_REGION=1  # 1=Europe, 2=Canada, 3=USA, etc.
HYUNDAI_BRAND=1   # 1=Hyundai, 2=Kia, 3=Genesis

# MQTT Configuration
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_BASE_TOPIC=hyundai

# Application Configuration
LOG_LEVEL=INFO
INITIAL_REFRESH=true
```

### Region Codes

- 1 = Europe
- 2 = Canada
- 3 = USA
- 4 = China
- 5 = Australia
- 6 = India
- 7 = New Zealand
- 8 = Brazil

### Brand Codes

- 1 = Hyundai
- 2 = Kia
- 3 = Genesis

## Usage

### Start the Service

```bash
python main.py
```

Or run from src:

```bash
python -m src.main
```

### MQTT Topics

#### Published Topics (Vehicle Data)

```
hyundai/{vehicle_id}/battery/level
hyundai/{vehicle_id}/battery/charging_status
hyundai/{vehicle_id}/battery/plug_status
hyundai/{vehicle_id}/battery/temperature
hyundai/{vehicle_id}/ev/range
hyundai/{vehicle_id}/ev/charge_time_100
hyundai/{vehicle_id}/ev/charge_time_target
hyundai/{vehicle_id}/ev/charge_limit
hyundai/{vehicle_id}/ev/energy_consumption
hyundai/{vehicle_id}/status/last_updated
hyundai/{vehicle_id}/status/data_source
hyundai/{vehicle_id}/status/update_method
```

#### Command Topic (Subscribe)

```
hyundai/{vehicle_id}/commands/refresh
```

### MQTT Commands

Send commands to trigger data updates:

#### Cached Refresh (Fast)
```bash
mosquitto_pub -t "hyundai/YOUR_VEHICLE_ID/commands/refresh" -m "cached"
```

#### Force Refresh (Fresh Data)
```bash
mosquitto_pub -t "hyundai/YOUR_VEHICLE_ID/commands/refresh" -m "force"
```

#### Smart Refresh (Conditional)
```bash
# Only refresh if data is older than 300 seconds (5 minutes)
mosquitto_pub -t "hyundai/YOUR_VEHICLE_ID/commands/refresh" -m "smart:300"
```

### Message Format

All published messages follow this JSON format:

```json
{
  "value": 85.5,
  "unit": "%",
  "timestamp": "2025-11-07T10:30:00Z"
}
```

## Architecture

### Project Structure

```
hyundai_mqtt/
├── src/
│   ├── config/          # Configuration management
│   ├── hyundai/         # Hyundai API client and data mapping
│   ├── mqtt/            # MQTT client and topic management
│   ├── commands/        # Command parsing and execution
│   ├── utils/           # Logging and error handling
│   └── main.py          # Main service orchestration
├── main.py              # Entry point
├── pyproject.toml       # Dependencies
├── .env.example         # Example configuration
└── README.md            # This file
```

### Components

1. **Configuration Layer** (`src/config/`)
   - Loads settings from environment variables
   - Validates configuration on startup

2. **Hyundai API Layer** (`src/hyundai/`)
   - Wraps `hyundai_kia_connect_api` library
   - Implements three refresh strategies
   - Maps vehicle data to structured models
   - Includes circuit breaker for resilience

3. **MQTT Layer** (`src/mqtt/`)
   - Manages MQTT connection and reconnection
   - Publishes vehicle data to topics
   - Subscribes to command topics
   - Handles message formatting

4. **Command Processing** (`src/commands/`)
   - Parses MQTT commands
   - Executes refresh operations
   - Implements command throttling

5. **Utilities** (`src/utils/`)
   - Structured JSON logging
   - Custom exception classes
   - Error context tracking

## Integration Examples

### Home Assistant

Add to your Home Assistant MQTT configuration:

```yaml
mqtt:
  sensor:
    - name: "Car Battery Level"
      state_topic: "hyundai/YOUR_VEHICLE_ID/battery/level"
      value_template: "{{ value_json.value }}"
      unit_of_measurement: "%"
      device_class: battery
      
    - name: "Car Range"
      state_topic: "hyundai/YOUR_VEHICLE_ID/ev/range"
      value_template: "{{ value_json.value }}"
      unit_of_measurement: "km"
      
    - name: "Car Charging Status"
      state_topic: "hyundai/YOUR_VEHICLE_ID/battery/charging_status"
      value_template: "{{ value_json.value }}"

  button:
    - name: "Refresh Car Data"
      command_topic: "hyundai/YOUR_VEHICLE_ID/commands/refresh"
      payload_press: "force"
```

### Node-RED

Use MQTT nodes to subscribe to topics and trigger automations based on battery level, charging status, etc.

## Troubleshooting

### Service Won't Start

1. Check your `.env` file has all required credentials
2. Verify MQTT broker is running: `mosquitto -v`
3. Check logs for specific error messages

### No Data Published

1. Ensure initial refresh is enabled: `INITIAL_REFRESH=true`
2. Send a manual refresh command via MQTT
3. Check circuit breaker hasn't opened due to API errors

### Connection Issues

- **MQTT**: Verify broker host/port, check firewall
- **Hyundai API**: Verify credentials, check region/brand codes
- **Network**: Ensure internet connectivity

### Enable Debug Logging

Set in `.env`:
```bash
LOG_LEVEL=DEBUG
```

## Rate Limits and Best Practices

- Use `cached` refresh for frequent queries
- Use `smart` refresh for automatic updates (e.g., `smart:300` for 5-minute caching)
- Use `force` refresh sparingly (wakes the vehicle)
- Implement command throttling in your automation (minimum 5 seconds between commands)

## License

This project is open source. See LICENSE file for details.

## Contributing

Contributions welcome! Please open an issue or pull request.

## Development

This project was developed using [aisanity](https://github.com/pigmej/aisanity) - an AI-assisted software development framework that enables rapid, intelligent code generation and debugging.

## Acknowledgments

- Built on [hyundai_kia_connect_api](https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api)
- Uses [paho-mqtt](https://www.eclipse.org/paho/index.php?page=clients/python/index.php) for MQTT communication
- Developed with [aisanity](https://github.com/pigmej/aisanity) for AI-assisted development
