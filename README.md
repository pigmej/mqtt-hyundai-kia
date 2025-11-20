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

### Option 1: Docker (Recommended)

#### Using Pre-built Image

```bash
docker run -d \
  --name hyundai-mqtt \
  --restart unless-stopped \
  -e HYUNDAI_USERNAME=your_email@example.com \
  -e HYUNDAI_PASSWORD=your_password \
  -e HYUNDAI_PIN=your_pin \
  -e HYUNDAI_REGION=1 \
  -e HYUNDAI_BRAND=1 \
  -e MQTT_BROKER_HOST=your_mqtt_broker \
  -e MQTT_BROKER_PORT=1883 \
  ghcr.io/yourusername/hyundai-mqtt:latest
```

#### Building Locally

```bash
# Clone the repository
git clone https://github.com/yourusername/hyundai-mqtt.git
cd hyundai-mqtt

# Build the Docker image
docker build -t hyundai-mqtt .

# Run the container
docker run -d \
  --name hyundai-mqtt \
  --restart unless-stopped \
  -e HYUNDAI_USERNAME=your_email@example.com \
  -e HYUNDAI_PASSWORD=your_password \
  -e HYUNDAI_PIN=your_pin \
  -e HYUNDAI_REGION=1 \
  -e HYUNDAI_BRAND=1 \
  -e MQTT_BROKER_HOST=your_mqtt_broker \
  hyundai-mqtt
```

#### Docker Compose (Development)

```bash
# Clone the repository
git clone https://github.com/yourusername/hyundai-mqtt.git
cd hyundai-mqtt

# Copy and edit environment file
cp .env.example .env
# Edit .env with your credentials

# Start with Docker Compose (includes Mosquitto broker)
docker-compose up -d

# View logs
docker-compose logs -f hyundai-mqtt

# Stop services
docker-compose down
```

### Option 2: Python Installation

#### Prerequisites

- Python 3.10 or higher
- MQTT broker (e.g., Mosquitto)
- Hyundai/Kia/Genesis Bluelink account

#### Install Dependencies

```bash
pip install -e .
```

Or manually install:

```bash
pip install hyundai-kia-connect-api paho-mqtt python-dotenv
```

## Configuration

### Environment Variables

The service can be configured via environment variables. These work for both Docker and Python installations.

#### Required Variables

- `HYUNDAI_USERNAME`: Your Hyundai/Kia/Genesis account email
- `HYUNDAI_PASSWORD`: Your account password
- `HYUNDAI_PIN`: Your vehicle PIN (for control commands)
- `MQTT_BROKER_HOST`: MQTT broker hostname or IP address

#### Optional Variables

```bash
# Hyundai API Configuration
HYUNDAI_REGION=1        # 1=Europe, 2=Canada, 3=USA, etc.
HYUNDAI_BRAND=1         # 1=Hyundai, 2=Kia, 3=Genesis

# MQTT Configuration
MQTT_BROKER_PORT=1883   # MQTT broker port
MQTT_USERNAME=          # MQTT authentication username (optional)
MQTT_PASSWORD=          # MQTT authentication password (optional)
MQTT_BASE_TOPIC=hyundai # Base topic for MQTT messages

# Application Configuration
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
INITIAL_REFRESH=true    # Load cached data on startup
REFRESH_INTERVAL=60     # Default refresh interval in seconds
```

### Setup Instructions

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

### Docker Issues

#### Container Won't Start

```bash
# Check container logs
docker logs hyundai-mqtt

# Check container status
docker ps -a

# Inspect container configuration
docker inspect hyundai-mqtt
```

#### Health Check Issues

```bash
# Check container health status
docker inspect --format='{{.State.Health.Status}}' hyundai-mqtt

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' hyundai-mqtt
```

#### Docker Compose Issues

```bash
# View all service logs
docker-compose logs

# View specific service logs
docker-compose logs hyundai-mqtt
docker-compose logs mosquitto

# Restart services
docker-compose restart hyundai-mqtt

# Rebuild and restart
docker-compose up --build -d
```

### Python Installation Issues

#### Service Won't Start

1. Check your `.env` file has all required credentials
2. Verify MQTT broker is running: `mosquitto -v`
3. Check logs for specific error messages

#### No Data Published

1. Ensure initial refresh is enabled: `INITIAL_REFRESH=true`
2. Send a manual refresh command via MQTT
3. Check circuit breaker hasn't opened due to API errors

### Connection Issues

- **MQTT**: Verify broker host/port, check firewall
- **Hyundai API**: Verify credentials, check region/brand codes
- **Network**: Ensure internet connectivity

### Enable Debug Logging

Set in `.env` or via environment variable:
```bash
LOG_LEVEL=DEBUG
```

For Docker:
```bash
docker run -d \
  --name hyundai-mqtt \
  -e LOG_LEVEL=DEBUG \
  # ... other environment variables
  ghcr.io/yourusername/hyundai-mqtt:latest
```

## Monitoring and Maintenance

### Docker Monitoring

#### Container Health Monitoring

```bash
# Monitor container health in real-time
watch -n 5 'docker inspect --format="{{.Name}}: {{.State.Health.Status}}" $(docker ps -q)'

# Check resource usage
docker stats hyundai-mqtt

# View live logs
docker logs -f hyundai-mqtt
```

#### Automated Health Checks

The container includes built-in health checks that verify:
- Service initialization completion
- MQTT broker connectivity
- API client status

Health check status can be monitored via:
- Docker health status (`docker ps`)
- Container orchestration systems (Kubernetes, Docker Swarm)
- Monitoring tools that support Docker health checks

### Log Management

#### Docker Logs

```bash
# View recent logs
docker logs --tail 100 hyundai-mqtt

# Follow logs in real-time
docker logs -f hyundai-mqtt

# Export logs to file
docker logs hyundai-mqtt > hyundai-mqtt.log
```

#### Structured Logging

The service outputs structured JSON logs when running in containers:
```json
{
  "timestamp": "2025-11-19T10:30:00Z",
  "level": "INFO",
  "message": "Service initialized successfully",
  "component": "HyundaiMQTTService"
}
```

### Updates and Maintenance

#### Updating Docker Image

```bash
# Pull latest image
docker pull ghcr.io/yourusername/hyundai-mqtt:latest

# Recreate container with new image
docker-compose down
docker-compose pull
docker-compose up -d
```

#### Backup Configuration

```bash
# Backup environment configuration
cp .env .env.backup

# Backup Docker Compose configuration
cp docker-compose.yml docker-compose.yml.backup
```

## Rate Limits and Best Practices

- Use `cached` refresh for frequent queries
- Use `smart` refresh for automatic updates (e.g., `smart:300` for 5-minute caching)
- Use `force` refresh sparingly (wakes the vehicle)
- Implement command throttling in your automation (minimum 5 seconds between commands)
- Monitor container health and resource usage
- Use structured logging for better observability in production

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
