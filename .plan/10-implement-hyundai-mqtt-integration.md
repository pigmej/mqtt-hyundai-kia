# Implementation Plan: Hyundai Bluelink MQTT Integration

## Implementation Overview

This document outlines the detailed implementation plan for the Hyundai Bluelink MQTT integration service. The system is designed as an event-driven bridge that connects Hyundai's vehicle API to MQTT for smart home automation, with a focus on battery and EV data management.

**Core Implementation Principles:**
1. Event-driven architecture with MQTT-triggered updates only
2. Three-tier refresh strategy (cached, force, smart)
3. Robust error handling with circuit breaker pattern
4. Structured logging and observability
5. Configuration-driven multi-region and multi-brand support

**Technology Stack:**
- Python 3.10+
- hyundai_kia_connect_api (Hyundai/Kia API client)
- paho-mqtt (MQTT client library)
- python-dotenv (Configuration management)

---

## Component Details

### 1. Configuration Layer (`src/config/`)

**Purpose:** Centralized configuration management with validation and environment-based settings.

**Files:**
- `settings.py` - Configuration dataclasses and validation
- `__init__.py` - Package exports

**Key Responsibilities:**
- Load and validate environment variables from `.env` file
- Define configuration schemas for Hyundai API and MQTT
- Provide typed configuration objects to other components
- Validate required credentials on startup

**Configuration Schema:**

```python
# Illustrative structure
@dataclass
class HyundaiConfig:
    username: str
    password: str
    pin: str
    region: int  # REGIONS enum value
    brand: int   # BRANDS enum value
    vehicle_id: Optional[str]

@dataclass
class MQTTConfig:
    broker_host: str
    broker_port: int
    username: Optional[str]
    password: Optional[str]
    use_tls: bool
    client_id: str
    qos_level: int
    base_topic: str  # e.g., "hyundai"

@dataclass
class AppConfig:
    hyundai: HyundaiConfig
    mqtt: MQTTConfig
    log_level: str
    initial_refresh: bool  # Load cached data on startup
```

**Environment Variables:**
```bash
# Hyundai API Configuration
HYUNDAI_USERNAME=user@example.com
HYUNDAI_PASSWORD=secret
HYUNDAI_PIN=1234
HYUNDAI_REGION=1  # Europe=1, Canada=2, USA=3, etc.
HYUNDAI_BRAND=1   # Hyundai=1, Kia=2, Genesis=3
HYUNDAI_VEHICLE_ID=  # Optional, auto-detect if empty

# MQTT Configuration
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_USE_TLS=false
MQTT_CLIENT_ID=hyundai_mqtt
MQTT_QOS=1
MQTT_BASE_TOPIC=hyundai

# Application Configuration
LOG_LEVEL=INFO
INITIAL_REFRESH=true
```

**IMPORTANT:** Implement validation to fail fast on startup if required configuration is missing or invalid.

---

### 2. Hyundai API Layer (`src/hyundai/`)

**Purpose:** Abstract Hyundai API interactions and implement refresh strategies.

**Files:**
- `api_client.py` - VehicleManager wrapper and refresh strategies
- `data_mapper.py` - Transform vehicle data to MQTT payload format
- `__init__.py` - Package exports

#### 2.1 API Client (`api_client.py`)

**Key Responsibilities:**
- Initialize VehicleManager with region and brand configuration
- Implement three refresh strategies (cached, force, smart)
- Handle API authentication and token refresh
- Implement circuit breaker for API resilience
- Extract battery and EV data from vehicle objects

**Class Structure:**

```python
# Illustrative structure
class HyundaiAPIClient:
    """
    Wrapper for hyundai_kia_connect_api VehicleManager.
    Implements refresh strategies and error handling.
    """

    def __init__(self, config: HyundaiConfig):
        # Initialize VehicleManager
        # Setup circuit breaker state
        # Configure retry parameters
        pass

    async def initialize(self) -> None:
        """
        Authenticate and discover vehicles.
        Called once on startup.
        """
        pass

    async def refresh_cached(self, vehicle_id: str) -> VehicleData:
        """
        Fast cached update using update_vehicle_with_cached_state().
        Returns local cached data without API call.
        """
        pass

    async def refresh_force(self, vehicle_id: str) -> VehicleData:
        """
        Force refresh from vehicle using force_refresh_vehicle_state().
        Makes real API call to vehicle for fresh data.
        """
        pass

    async def refresh_smart(self, vehicle_id: str, max_age_seconds: int) -> VehicleData:
        """
        Smart refresh using check_and_force_update_vehicle(seconds).
        Only refreshes if data is older than max_age_seconds.
        """
        pass

    def get_vehicle_ids(self) -> List[str]:
        """Return list of available vehicle IDs."""
        pass

    def _extract_vehicle_data(self, vehicle) -> VehicleData:
        """Extract battery and EV data from vehicle object."""
        pass
```

**Refresh Strategy Implementation:**

```python
# Illustrative refresh strategy pattern
class RefreshStrategy(ABC):
    @abstractmethod
    async def execute(self, vehicle_manager, vehicle_id: str) -> VehicleData:
        pass

class CachedRefreshStrategy(RefreshStrategy):
    async def execute(self, vehicle_manager, vehicle_id: str) -> VehicleData:
        # Call update_vehicle_with_cached_state()
        # Return cached data immediately
        pass

class ForceRefreshStrategy(RefreshStrategy):
    async def execute(self, vehicle_manager, vehicle_id: str) -> VehicleData:
        # Call force_refresh_vehicle_state()
        # Wait for fresh data from vehicle
        pass

class SmartRefreshStrategy(RefreshStrategy):
    def __init__(self, max_age_seconds: int):
        self.max_age_seconds = max_age_seconds

    async def execute(self, vehicle_manager, vehicle_id: str) -> VehicleData:
        # Call check_and_force_update_vehicle(max_age_seconds)
        # Conditionally refresh based on data age
        pass
```

**Circuit Breaker Pattern:**

```python
# Illustrative circuit breaker implementation
class CircuitBreaker:
    """
    Prevents repeated API calls when service is down.
    States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing)
    """

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None

    async def call(self, func, *args, **kwargs):
        # Check circuit state
        # Execute function if CLOSED or HALF_OPEN
        # Track failures and open circuit if threshold exceeded
        # Auto-reset after timeout
        pass
```

**IMPORTANT:** Implement exponential backoff for retries and respect API rate limits.

#### 2.2 Data Mapper (`data_mapper.py`)

**Key Responsibilities:**
- Transform vehicle API objects to structured data models
- Extract battery-specific metrics
- Extract EV-specific metrics
- Add metadata (timestamp, data source)

**Data Models:**

```python
# Illustrative data structures
@dataclass
class BatteryData:
    """Battery-related metrics from vehicle."""
    level: Optional[float]           # Battery percentage (0-100)
    charging_status: Optional[str]   # "charging", "not_charging", etc.
    plug_status: Optional[str]       # "connected", "disconnected"
    temperature: Optional[float]     # Battery temperature in Celsius

@dataclass
class EVData:
    """Electric vehicle-specific metrics."""
    range: Optional[float]                  # Remaining range in km
    charge_time_100: Optional[int]          # Minutes to 100% charge
    charge_time_target: Optional[int]       # Minutes to target charge
    charge_limit: Optional[int]             # Max charge limit (%)
    energy_consumption: Optional[float]     # kWh/100km or similar

@dataclass
class StatusData:
    """Metadata about the data fetch."""
    last_updated: datetime              # When data was last updated
    data_source: str                    # "cached" or "fresh"
    update_method: str                  # "cached", "force", or "smart"

@dataclass
class VehicleData:
    """Complete vehicle data payload."""
    vehicle_id: str
    battery: BatteryData
    ev: EVData
    status: StatusData
```

**Mapping Functions:**

```python
# Illustrative mapping functions
def map_battery_data(vehicle) -> BatteryData:
    """Extract battery data from hyundai_kia_connect_api vehicle object."""
    return BatteryData(
        level=vehicle.ev_battery_percentage,
        charging_status=_map_charging_status(vehicle.ev_charge_port_state),
        plug_status=_map_plug_status(vehicle.ev_plug_to_vehicle_state),
        temperature=vehicle.ev_battery_temperature
    )

def map_ev_data(vehicle) -> EVData:
    """Extract EV data from vehicle object."""
    return EVData(
        range=vehicle.ev_driving_range,
        charge_time_100=vehicle.ev_time_to_full_charge,
        charge_time_target=vehicle.ev_target_range_charge_time,
        charge_limit=vehicle.ev_max_charge_limit,
        energy_consumption=vehicle.ev_energy_consumption
    )

def _map_charging_status(raw_status) -> str:
    """Normalize charging status to consistent strings."""
    # Map API-specific values to standard strings
    pass

def _map_plug_status(raw_status) -> str:
    """Normalize plug status to consistent strings."""
    # Map API-specific values to standard strings
    pass
```

**IMPORTANT:** Handle missing or None values gracefully - not all vehicles may provide all metrics.

---

### 3. MQTT Layer (`src/mqtt/`)

**Purpose:** Manage MQTT connections, publish data, and subscribe to commands.

**Files:**
- `client.py` - MQTT client wrapper with connection management
- `topics.py` - Topic structure and message formatting
- `__init__.py` - Package exports

#### 3.1 MQTT Client (`client.py`)

**Key Responsibilities:**
- Establish and maintain MQTT connection
- Implement automatic reconnection with exponential backoff
- Publish vehicle data to structured topics
- Subscribe to command topics
- Handle connection callbacks and errors

**Class Structure:**

```python
# Illustrative structure
class MQTTClient:
    """
    Wrapper for paho.mqtt.client with reconnection logic.
    """

    def __init__(self, config: MQTTConfig, on_command_callback):
        self.config = config
        self.on_command_callback = on_command_callback
        self.client = mqtt.Client(client_id=config.client_id)
        self._setup_callbacks()
        self._setup_authentication()
        self._setup_tls()

    def _setup_callbacks(self):
        """Configure MQTT callbacks for connection events."""
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        """Handle successful connection - subscribe to command topics."""
        # Subscribe to: hyundai/{vehicle_id}/commands/refresh
        pass

    def _on_disconnect(self, client, userdata, rc):
        """Handle disconnection - trigger reconnection logic."""
        pass

    def _on_message(self, client, userdata, msg):
        """Route incoming messages to command handler."""
        # Parse command and call on_command_callback
        pass

    async def connect(self):
        """Establish MQTT connection with retry logic."""
        pass

    async def publish_vehicle_data(self, vehicle_data: VehicleData):
        """Publish all vehicle data to respective topics."""
        pass

    async def publish_battery_data(self, vehicle_id: str, battery: BatteryData):
        """Publish battery metrics to topics."""
        pass

    async def publish_ev_data(self, vehicle_id: str, ev: EVData):
        """Publish EV metrics to topics."""
        pass

    async def publish_status_data(self, vehicle_id: str, status: StatusData):
        """Publish status metadata to topics."""
        pass

    def disconnect(self):
        """Gracefully disconnect from MQTT broker."""
        pass
```

**Reconnection Logic:**

```python
# Illustrative reconnection pattern
class ReconnectionHandler:
    """Handles MQTT reconnection with exponential backoff."""

    def __init__(self, initial_delay: int = 1, max_delay: int = 300):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.current_delay = initial_delay

    async def reconnect(self, client):
        """Attempt reconnection with exponential backoff."""
        while True:
            try:
                client.reconnect()
                self.current_delay = self.initial_delay
                break
            except Exception as e:
                logger.warning(f"Reconnection failed: {e}")
                await asyncio.sleep(self.current_delay)
                self.current_delay = min(self.current_delay * 2, self.max_delay)
```

**IMPORTANT:** Use QoS 1 for critical data (battery level, charging status) and QoS 0 for less critical metrics.

#### 3.2 Topic Manager (`topics.py`)

**Key Responsibilities:**
- Define topic structure and naming conventions
- Format messages for publishing
- Parse command topics
- Handle retain flags appropriately

**Topic Structure:**

```python
# Illustrative topic management
class TopicManager:
    """
    Manages MQTT topic structure and message formatting.
    """

    def __init__(self, base_topic: str = "hyundai"):
        self.base_topic = base_topic

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

    def format_message(self, value: Any, timestamp: datetime = None) -> str:
        """
        Format message payload as JSON with value and metadata.
        Example: {"value": 85, "timestamp": "2025-11-07T10:30:00Z"}
        """
        pass

    def parse_command(self, payload: str) -> CommandType:
        """
        Parse command payload into structured command.
        Examples: "cached", "force", "smart:300"
        """
        pass
```

**Message Format:**

```python
# Illustrative message formatting
class MessageFormatter:
    """Formats MQTT message payloads."""

    @staticmethod
    def format_value(value: Any, unit: str = None) -> dict:
        """
        Standard message format with value and optional unit.
        """
        payload = {
            "value": value,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        if unit:
            payload["unit"] = unit
        return payload

    @staticmethod
    def format_battery_level(level: float) -> dict:
        """Format battery level with percentage unit."""
        return MessageFormatter.format_value(level, unit="%")

    @staticmethod
    def format_range(range_km: float) -> dict:
        """Format range with km unit."""
        return MessageFormatter.format_value(range_km, unit="km")
```

**Topic Configuration:**

```python
# Illustrative topic configuration
TOPIC_CONFIG = {
    "battery/level": {"qos": 1, "retain": True},
    "battery/charging_status": {"qos": 1, "retain": True},
    "battery/plug_status": {"qos": 1, "retain": True},
    "battery/temperature": {"qos": 0, "retain": False},
    "ev/range": {"qos": 1, "retain": True},
    "ev/charge_time_100": {"qos": 0, "retain": False},
    "ev/charge_time_target": {"qos": 0, "retain": False},
    "ev/charge_limit": {"qos": 1, "retain": True},
    "ev/energy_consumption": {"qos": 0, "retain": False},
    "status/last_updated": {"qos": 0, "retain": True},
    "status/data_source": {"qos": 0, "retain": True},
}
```

**IMPORTANT:** Use retain flag for status topics (last_updated, data_source) so new subscribers get current state immediately.

---

### 4. Command Processing Layer (`src/commands/`)

**Purpose:** Parse and execute MQTT commands, coordinate refresh operations.

**Files:**
- `handler.py` - Command parsing and execution
- `__init__.py` - Package exports

**Command Handler:**

```python
# Illustrative command handler
@dataclass
class RefreshCommand:
    """Parsed refresh command."""
    command_type: str  # "cached", "force", "smart"
    vehicle_id: str
    max_age_seconds: Optional[int] = None  # For smart refresh

class CommandHandler:
    """
    Processes MQTT commands and coordinates refresh operations.
    """

    def __init__(self, api_client: HyundaiAPIClient, mqtt_client: MQTTClient):
        self.api_client = api_client
        self.mqtt_client = mqtt_client
        self._command_queue = asyncio.Queue()

    def parse_command(self, topic: str, payload: str) -> RefreshCommand:
        """
        Parse MQTT command from topic and payload.

        Examples:
        - payload="cached" -> RefreshCommand(command_type="cached")
        - payload="force" -> RefreshCommand(command_type="force")
        - payload="smart:300" -> RefreshCommand(command_type="smart", max_age_seconds=300)
        """
        pass

    async def handle_command(self, command: RefreshCommand):
        """Execute refresh command and publish results."""
        try:
            # Execute appropriate refresh strategy
            if command.command_type == "cached":
                data = await self.api_client.refresh_cached(command.vehicle_id)
            elif command.command_type == "force":
                data = await self.api_client.refresh_force(command.vehicle_id)
            elif command.command_type == "smart":
                data = await self.api_client.refresh_smart(
                    command.vehicle_id,
                    command.max_age_seconds
                )

            # Publish updated data to MQTT
            await self.mqtt_client.publish_vehicle_data(data)

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            # Publish error status to MQTT
            pass

    async def enqueue_command(self, topic: str, payload: str):
        """Add command to processing queue."""
        command = self.parse_command(topic, payload)
        await self._command_queue.put(command)

    async def process_commands(self):
        """Process commands from queue (main command loop)."""
        while True:
            command = await self._command_queue.get()
            await self.handle_command(command)
```

**Command Validation:**

```python
# Illustrative command validation
class CommandValidator:
    """Validates parsed commands before execution."""

    @staticmethod
    def validate_refresh_command(command: RefreshCommand) -> bool:
        """Validate refresh command parameters."""
        # Check command type is valid
        if command.command_type not in ["cached", "force", "smart"]:
            return False

        # Check smart command has valid max_age
        if command.command_type == "smart":
            if not command.max_age_seconds or command.max_age_seconds < 0:
                return False

        return True
```

**IMPORTANT:** Implement command throttling to prevent MQTT command spam from overwhelming the API.

---

### 5. Utilities Layer (`src/utils/`)

**Purpose:** Shared utilities for logging, error handling, and monitoring.

**Files:**
- `logger.py` - Structured logging configuration
- `errors.py` - Custom exception classes
- `__init__.py` - Package exports

#### 5.1 Logger (`logger.py`)

**Logging Strategy:**

```python
# Illustrative logging configuration
import logging
import json
from datetime import datetime

class StructuredLogger:
    """
    Structured JSON logging for better observability.
    """

    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level))
        self._setup_handlers()

    def _setup_handlers(self):
        """Configure console and file handlers."""
        # Console handler with JSON formatting
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(console_handler)

    def log(self, level: str, message: str, **context):
        """Log with additional context fields."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            **context
        }
        getattr(self.logger, level.lower())(json.dumps(log_data))

    def redact_sensitive(self, data: dict) -> dict:
        """Remove sensitive information from log data."""
        sensitive_keys = ["password", "pin", "token", "authorization"]
        return {
            k: "***REDACTED***" if k.lower() in sensitive_keys else v
            for k, v in data.items()
        }
```

**Log Levels and Usage:**

```python
# Illustrative log level guidance
# DEBUG: Detailed diagnostic information
logger.debug("API response received", vehicle_id="abc123", data_size=1024)

# INFO: General informational messages
logger.info("Vehicle data refreshed", vehicle_id="abc123", method="cached")

# WARNING: Warning messages for non-critical issues
logger.warning("API response slow", vehicle_id="abc123", duration_ms=5000)

# ERROR: Error messages for failures
logger.error("API request failed", vehicle_id="abc123", error=str(e))

# CRITICAL: Critical failures requiring immediate attention
logger.critical("MQTT connection lost", retry_count=5)
```

**IMPORTANT:** Never log sensitive data (passwords, PINs, tokens). Always redact before logging.

#### 5.2 Error Handling (`errors.py`)

**Custom Exceptions:**

```python
# Illustrative exception hierarchy
class HyundaiMQTTError(Exception):
    """Base exception for all application errors."""
    pass

class ConfigurationError(HyundaiMQTTError):
    """Invalid or missing configuration."""
    pass

class HyundaiAPIError(HyundaiMQTTError):
    """Hyundai API errors."""
    pass

class MQTTConnectionError(HyundaiMQTTError):
    """MQTT connection errors."""
    pass

class RefreshError(HyundaiMQTTError):
    """Vehicle data refresh errors."""
    pass

class CommandError(HyundaiMQTTError):
    """Command processing errors."""
    pass
```

**Error Context:**

```python
# Illustrative error context
@dataclass
class ErrorContext:
    """Additional context for error reporting."""
    component: str
    operation: str
    vehicle_id: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

def handle_error(error: Exception, context: ErrorContext):
    """Centralized error handling with logging and recovery."""
    logger.error(
        f"{context.component} error during {context.operation}",
        error_type=type(error).__name__,
        error_message=str(error),
        **asdict(context)
    )

    # Implement recovery strategies based on error type
    # - API errors: Circuit breaker
    # - MQTT errors: Reconnection
    # - Transient errors: Retry with backoff
```

---

### 6. Main Application (`src/main.py`)

**Purpose:** Application entry point, lifecycle management, and orchestration.

**Application Structure:**

```python
# Illustrative main application
class HyundaiMQTTService:
    """
    Main service orchestrator for Hyundai MQTT integration.
    """

    def __init__(self):
        self.config = None
        self.api_client = None
        self.mqtt_client = None
        self.command_handler = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self):
        """Initialize all components."""
        # Load and validate configuration
        self.config = load_config()

        # Initialize Hyundai API client
        self.api_client = HyundaiAPIClient(self.config.hyundai)
        await self.api_client.initialize()

        # Initialize command handler
        self.command_handler = CommandHandler(self.api_client, None)

        # Initialize MQTT client with command callback
        self.mqtt_client = MQTTClient(
            self.config.mqtt,
            on_command_callback=self.command_handler.enqueue_command
        )
        self.command_handler.mqtt_client = self.mqtt_client

        # Connect to MQTT broker
        await self.mqtt_client.connect()

        logger.info("Service initialized successfully")

    async def load_initial_data(self):
        """Load cached data on startup if configured."""
        if not self.config.initial_refresh:
            logger.info("Skipping initial data load")
            return

        logger.info("Loading initial cached data")
        for vehicle_id in self.api_client.get_vehicle_ids():
            try:
                data = await self.api_client.refresh_cached(vehicle_id)
                await self.mqtt_client.publish_vehicle_data(data)
                logger.info(f"Initial data loaded for vehicle {vehicle_id}")
            except Exception as e:
                logger.error(f"Failed to load initial data: {e}")

    async def run(self):
        """Main service loop."""
        try:
            await self.initialize()
            await self.load_initial_data()

            # Start command processing loop
            command_task = asyncio.create_task(
                self.command_handler.process_commands()
            )

            # Wait for shutdown signal
            await self._shutdown_event.wait()

            # Cancel tasks
            command_task.cancel()

        except Exception as e:
            logger.critical(f"Service failed: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown of all components."""
        logger.info("Shutting down service")

        if self.mqtt_client:
            self.mqtt_client.disconnect()

        logger.info("Service shutdown complete")

    def signal_handler(self, sig, frame):
        """Handle shutdown signals (SIGINT, SIGTERM)."""
        logger.info(f"Received signal {sig}, initiating shutdown")
        self._shutdown_event.set()

async def main():
    """Application entry point."""
    service = HyundaiMQTTService()

    # Register signal handlers
    import signal
    signal.signal(signal.SIGINT, service.signal_handler)
    signal.signal(signal.SIGTERM, service.signal_handler)

    # Run service
    await service.run()

if __name__ == "__main__":
    asyncio.run(main())
```

**IMPORTANT:** Implement graceful shutdown to ensure MQTT disconnect and API cleanup.

---

## Data Structures

### Core Data Models

**Vehicle Data Model:**
```python
@dataclass
class VehicleData:
    """Complete vehicle data snapshot."""
    vehicle_id: str
    battery: BatteryData
    ev: EVData
    status: StatusData

    def to_mqtt_messages(self) -> List[Tuple[str, dict]]:
        """Convert to list of (topic, payload) tuples for MQTT publishing."""
        pass

@dataclass
class BatteryData:
    """Battery metrics."""
    level: Optional[float]           # 0-100 percentage
    charging_status: Optional[str]   # "charging", "not_charging", "complete"
    plug_status: Optional[str]       # "connected", "disconnected"
    temperature: Optional[float]     # Celsius

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}

@dataclass
class EVData:
    """Electric vehicle metrics."""
    range: Optional[float]                  # km
    charge_time_100: Optional[int]          # minutes
    charge_time_target: Optional[int]       # minutes
    charge_limit: Optional[int]             # percentage
    energy_consumption: Optional[float]     # kWh/100km

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

@dataclass
class StatusData:
    """Metadata about data freshness."""
    last_updated: datetime
    data_source: str        # "cached" or "fresh"
    update_method: str      # "cached", "force", "smart"

    def to_dict(self) -> dict:
        return {
            "last_updated": self.last_updated.isoformat() + "Z",
            "data_source": self.data_source,
            "update_method": self.update_method
        }
```

### Configuration Models

**Configuration Dataclasses:**
```python
from enum import IntEnum

class Region(IntEnum):
    """Supported regions from hyundai_kia_connect_api."""
    EUROPE = 1
    CANADA = 2
    USA = 3
    CHINA = 4
    AUSTRALIA = 5
    INDIA = 6
    NEW_ZEALAND = 7
    BRAZIL = 8

class Brand(IntEnum):
    """Supported brands."""
    HYUNDAI = 1
    KIA = 2
    GENESIS = 3

@dataclass
class HyundaiConfig:
    username: str
    password: str
    pin: str
    region: Region
    brand: Brand
    vehicle_id: Optional[str] = None

    @staticmethod
    def from_env() -> 'HyundaiConfig':
        """Load from environment variables with validation."""
        username = os.getenv("HYUNDAI_USERNAME")
        password = os.getenv("HYUNDAI_PASSWORD")
        pin = os.getenv("HYUNDAI_PIN")
        region = Region(int(os.getenv("HYUNDAI_REGION", "1")))
        brand = Brand(int(os.getenv("HYUNDAI_BRAND", "1")))

        # Validate required fields
        if not all([username, password, pin]):
            raise ConfigurationError("Missing required Hyundai credentials")

        return HyundaiConfig(
            username=username,
            password=password,
            pin=pin,
            region=region,
            brand=brand,
            vehicle_id=os.getenv("HYUNDAI_VEHICLE_ID")
        )
```

### Command Models

**Command Processing:**
```python
@dataclass
class RefreshCommand:
    """Parsed refresh command from MQTT."""
    command_type: str  # "cached", "force", "smart"
    vehicle_id: str
    max_age_seconds: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def parse(topic: str, payload: str) -> 'RefreshCommand':
        """
        Parse MQTT message to RefreshCommand.

        Topic format: hyundai/{vehicle_id}/commands/refresh
        Payload examples: "cached", "force", "smart:300"
        """
        # Extract vehicle_id from topic
        parts = topic.split("/")
        vehicle_id = parts[1] if len(parts) > 1 else None

        # Parse command type and parameters
        if ":" in payload:
            cmd_type, param = payload.split(":", 1)
            max_age = int(param) if cmd_type == "smart" else None
        else:
            cmd_type = payload
            max_age = None

        return RefreshCommand(
            command_type=cmd_type,
            vehicle_id=vehicle_id,
            max_age_seconds=max_age
        )
```

---

## API Design

### Hyundai API Integration

**VehicleManager Initialization:**
```python
# Illustrative API initialization
from hyundai_kia_connect_api import VehicleManager, REGIONS, BRANDS

async def initialize_vehicle_manager(config: HyundaiConfig) -> VehicleManager:
    """
    Initialize VehicleManager with proper region and brand.
    """
    vehicle_manager = VehicleManager(
        region=config.region,
        brand=config.brand,
        username=config.username,
        password=config.password,
        pin=config.pin
    )

    # Authenticate and discover vehicles
    await vehicle_manager.check_and_refresh_token()
    await vehicle_manager.update_all_vehicles_with_cached_state()

    logger.info(
        f"Initialized VehicleManager",
        region=config.region.name,
        brand=config.brand.name,
        vehicle_count=len(vehicle_manager.vehicles)
    )

    return vehicle_manager
```

**Refresh Strategy Methods:**

```python
# Illustrative refresh implementations

async def refresh_cached(vehicle_manager: VehicleManager, vehicle_id: str):
    """
    Fast cached refresh - no API call to vehicle.
    Uses: update_vehicle_with_cached_state()
    """
    vehicle = vehicle_manager.get_vehicle(vehicle_id)
    await vehicle_manager.update_vehicle_with_cached_state(vehicle_id)
    return vehicle

async def refresh_force(vehicle_manager: VehicleManager, vehicle_id: str):
    """
    Force refresh - makes API call to vehicle for fresh data.
    Uses: force_refresh_vehicle_state()
    Note: This may take 30-60 seconds as it wakes the vehicle.
    """
    vehicle = vehicle_manager.get_vehicle(vehicle_id)
    await vehicle_manager.force_refresh_vehicle_state(vehicle_id)
    return vehicle

async def refresh_smart(
    vehicle_manager: VehicleManager,
    vehicle_id: str,
    max_age_seconds: int
):
    """
    Smart refresh - only refreshes if data is stale.
    Uses: check_and_force_update_vehicle(max_age_seconds)
    """
    vehicle = vehicle_manager.get_vehicle(vehicle_id)
    await vehicle_manager.check_and_force_update_vehicle(
        vehicle_id,
        max_age_seconds
    )
    return vehicle
```

**Data Extraction:**

```python
# Illustrative data extraction from vehicle object

def extract_battery_data(vehicle) -> BatteryData:
    """Extract battery metrics from vehicle object."""
    return BatteryData(
        level=getattr(vehicle, 'ev_battery_percentage', None),
        charging_status=_normalize_charging_status(
            getattr(vehicle, 'ev_battery_is_charging', None)
        ),
        plug_status=_normalize_plug_status(
            getattr(vehicle, 'ev_battery_is_plugged_in', None)
        ),
        temperature=getattr(vehicle, 'ev_battery_temperature', None)
    )

def extract_ev_data(vehicle) -> EVData:
    """Extract EV metrics from vehicle object."""
    return EVData(
        range=getattr(vehicle, 'ev_driving_range', None),
        charge_time_100=getattr(vehicle, 'ev_estimated_current_charge_duration', None),
        charge_time_target=getattr(vehicle, 'ev_target_range_charge_ac', None),
        charge_limit=getattr(vehicle, 'ev_charge_limits_ac', None),
        energy_consumption=getattr(vehicle, 'ev_energy_consumption', None)
    )

def _normalize_charging_status(is_charging: Optional[bool]) -> Optional[str]:
    """Convert boolean to human-readable status."""
    if is_charging is None:
        return None
    return "charging" if is_charging else "not_charging"
```

**IMPORTANT:** Use defensive programming with `getattr()` and None checks since not all vehicles expose all attributes.

### MQTT API Design

**Publishing API:**

```python
# Illustrative MQTT publishing API

class MQTTPublisher:
    """Handles all MQTT publishing operations."""

    async def publish_battery_level(
        self,
        vehicle_id: str,
        level: float,
        timestamp: datetime
    ):
        """Publish battery level to topic."""
        topic = f"hyundai/{vehicle_id}/battery/level"
        payload = {
            "value": level,
            "unit": "%",
            "timestamp": timestamp.isoformat() + "Z"
        }
        await self._publish(topic, json.dumps(payload), qos=1, retain=True)

    async def publish_complete_vehicle_data(self, data: VehicleData):
        """Publish all vehicle data in batch."""
        tasks = []

        # Battery data
        if data.battery.level is not None:
            tasks.append(self.publish_battery_level(
                data.vehicle_id, data.battery.level, data.status.last_updated
            ))

        # EV data
        if data.ev.range is not None:
            tasks.append(self.publish_ev_range(
                data.vehicle_id, data.ev.range, data.status.last_updated
            ))

        # Status data
        tasks.append(self.publish_status(data.vehicle_id, data.status))

        # Execute all publishes in parallel
        await asyncio.gather(*tasks)

    async def _publish(
        self,
        topic: str,
        payload: str,
        qos: int = 0,
        retain: bool = False
    ):
        """Low-level publish method."""
        result = self.client.publish(topic, payload, qos=qos, retain=retain)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise MQTTConnectionError(f"Publish failed: {result.rc}")
```

**Subscription API:**

```python
# Illustrative MQTT subscription API

class MQTTSubscriber:
    """Handles MQTT subscriptions and message routing."""

    def __init__(self, client, command_handler):
        self.client = client
        self.command_handler = command_handler
        self.subscriptions = {}

    async def subscribe_to_commands(self, vehicle_ids: List[str]):
        """Subscribe to command topics for all vehicles."""
        for vehicle_id in vehicle_ids:
            topic = f"hyundai/{vehicle_id}/commands/refresh"
            self.client.subscribe(topic, qos=1)
            self.subscriptions[topic] = self._handle_refresh_command
            logger.info(f"Subscribed to {topic}")

    def _handle_refresh_command(self, topic: str, payload: str):
        """Handle refresh command message."""
        try:
            command = RefreshCommand.parse(topic, payload)
            await self.command_handler.enqueue_command(command)
        except Exception as e:
            logger.error(f"Failed to handle command: {e}")
```

**Topic Hierarchy:**

```
hyundai/
└── {vehicle_id}/
    ├── battery/
    │   ├── level                    [QoS 1, Retain]
    │   ├── charging_status          [QoS 1, Retain]
    │   ├── plug_status              [QoS 1, Retain]
    │   └── temperature              [QoS 0, No Retain]
    ├── ev/
    │   ├── range                    [QoS 1, Retain]
    │   ├── charge_time_100          [QoS 0, No Retain]
    │   ├── charge_time_target       [QoS 0, No Retain]
    │   ├── charge_limit             [QoS 1, Retain]
    │   └── energy_consumption       [QoS 0, No Retain]
    ├── status/
    │   ├── last_updated             [QoS 0, Retain]
    │   └── data_source              [QoS 0, Retain]
    └── commands/
        └── refresh                  [QoS 1, No Retain] (subscribe only)
```

---

## Testing Strategy

### Unit Testing

**Test Coverage Areas:**
1. Configuration loading and validation
2. Data mapping and transformation
3. Command parsing and validation
4. Topic formatting and message construction
5. Error handling and exceptions

**Example Test Structure:**

```python
# Illustrative unit tests

class TestDataMapper:
    """Unit tests for data mapping functions."""

    def test_map_battery_data_complete(self):
        """Test battery data mapping with all fields present."""
        # Create mock vehicle object
        vehicle = MockVehicle(
            ev_battery_percentage=85.5,
            ev_battery_is_charging=True,
            ev_battery_is_plugged_in=True,
            ev_battery_temperature=25.0
        )

        # Map data
        battery_data = map_battery_data(vehicle)

        # Assertions
        assert battery_data.level == 85.5
        assert battery_data.charging_status == "charging"
        assert battery_data.plug_status == "connected"
        assert battery_data.temperature == 25.0

    def test_map_battery_data_partial(self):
        """Test battery data mapping with missing fields."""
        vehicle = MockVehicle(ev_battery_percentage=50.0)
        battery_data = map_battery_data(vehicle)

        assert battery_data.level == 50.0
        assert battery_data.charging_status is None
        assert battery_data.plug_status is None
        assert battery_data.temperature is None

class TestCommandParser:
    """Unit tests for command parsing."""

    def test_parse_cached_command(self):
        """Test parsing cached refresh command."""
        topic = "hyundai/vehicle123/commands/refresh"
        payload = "cached"

        command = RefreshCommand.parse(topic, payload)

        assert command.vehicle_id == "vehicle123"
        assert command.command_type == "cached"
        assert command.max_age_seconds is None

    def test_parse_smart_command(self):
        """Test parsing smart refresh command with parameter."""
        topic = "hyundai/vehicle123/commands/refresh"
        payload = "smart:300"

        command = RefreshCommand.parse(topic, payload)

        assert command.vehicle_id == "vehicle123"
        assert command.command_type == "smart"
        assert command.max_age_seconds == 300

    def test_parse_invalid_command(self):
        """Test handling of invalid command."""
        topic = "hyundai/vehicle123/commands/refresh"
        payload = "invalid"

        with pytest.raises(CommandError):
            RefreshCommand.parse(topic, payload)
```

### Integration Testing

**Test Scenarios:**
1. End-to-end MQTT command processing
2. Hyundai API interaction with mock responses
3. Circuit breaker behavior during API failures
4. MQTT reconnection logic
5. Multi-vehicle handling

**Example Integration Test:**

```python
# Illustrative integration tests

class TestMQTTIntegration:
    """Integration tests for MQTT operations."""

    @pytest.fixture
    async def mqtt_client(self):
        """Fixture providing configured MQTT client."""
        config = MQTTConfig(
            broker_host="localhost",
            broker_port=1883,
            client_id="test_client"
        )
        client = MQTTClient(config, on_command_callback=None)
        await client.connect()
        yield client
        client.disconnect()

    async def test_publish_vehicle_data(self, mqtt_client):
        """Test publishing complete vehicle data."""
        # Create test data
        vehicle_data = VehicleData(
            vehicle_id="test123",
            battery=BatteryData(level=85.0, charging_status="charging"),
            ev=EVData(range=250.0),
            status=StatusData(
                last_updated=datetime.utcnow(),
                data_source="cached",
                update_method="cached"
            )
        )

        # Publish data
        await mqtt_client.publish_vehicle_data(vehicle_data)

        # Verify messages were sent (using MQTT test broker)
        # Assert topic structure and payload format

class TestHyundaiAPIIntegration:
    """Integration tests for Hyundai API interactions."""

    @pytest.fixture
    async def api_client(self):
        """Fixture providing configured API client."""
        config = HyundaiConfig(
            username="test@example.com",
            password="test",
            pin="1234",
            region=Region.EUROPE,
            brand=Brand.HYUNDAI
        )
        client = HyundaiAPIClient(config)
        await client.initialize()
        return client

    async def test_cached_refresh(self, api_client):
        """Test cached data refresh."""
        vehicle_id = "test123"
        data = await api_client.refresh_cached(vehicle_id)

        assert data.vehicle_id == vehicle_id
        assert data.status.data_source == "cached"
        assert data.battery is not None
```

### System Testing

**Test Scenarios:**
1. Complete service startup and initialization
2. Initial data load on startup
3. Command processing flow (MQTT → API → MQTT)
4. Error recovery and circuit breaker
5. Graceful shutdown handling

**Example System Test:**

```python
# Illustrative system tests

class TestServiceLifecycle:
    """System tests for complete service lifecycle."""

    async def test_service_startup(self):
        """Test complete service initialization."""
        service = HyundaiMQTTService()

        # Initialize service
        await service.initialize()

        # Verify components initialized
        assert service.api_client is not None
        assert service.mqtt_client is not None
        assert service.command_handler is not None

        # Cleanup
        await service.shutdown()

    async def test_end_to_end_refresh_flow(self):
        """Test complete refresh command flow."""
        service = HyundaiMQTTService()
        await service.initialize()

        # Simulate MQTT command
        topic = "hyundai/vehicle123/commands/refresh"
        payload = "force"

        await service.command_handler.enqueue_command(topic, payload)

        # Wait for processing
        await asyncio.sleep(2)

        # Verify data was published to MQTT
        # (requires MQTT test subscriber)

        await service.shutdown()
```

### Mock Objects

**Mock Vehicle Object:**

```python
# Illustrative mock for testing

class MockVehicle:
    """Mock Hyundai vehicle object for testing."""

    def __init__(self, **kwargs):
        self.vehicle_id = kwargs.get('vehicle_id', 'test123')
        self.ev_battery_percentage = kwargs.get('ev_battery_percentage')
        self.ev_battery_is_charging = kwargs.get('ev_battery_is_charging')
        self.ev_battery_is_plugged_in = kwargs.get('ev_battery_is_plugged_in')
        self.ev_battery_temperature = kwargs.get('ev_battery_temperature')
        self.ev_driving_range = kwargs.get('ev_driving_range')
        self.ev_estimated_current_charge_duration = kwargs.get('ev_estimated_current_charge_duration')
        # ... other attributes

class MockVehicleManager:
    """Mock VehicleManager for testing."""

    def __init__(self):
        self.vehicles = [MockVehicle()]

    async def update_vehicle_with_cached_state(self, vehicle_id: str):
        """Mock cached update."""
        pass

    async def force_refresh_vehicle_state(self, vehicle_id: str):
        """Mock force refresh."""
        pass

    async def check_and_force_update_vehicle(
        self,
        vehicle_id: str,
        max_age_seconds: int
    ):
        """Mock smart refresh."""
        pass
```

**IMPORTANT:** Use pytest with async support (pytest-asyncio) for testing async code.

---

## Development Phases

### Phase 1: Foundation and Configuration (Week 1)

**Objectives:**
- Set up project structure
- Implement configuration management
- Create basic logging infrastructure

**Tasks:**
1. **Project Setup**
   - Create directory structure
   - Initialize `pyproject.toml` with dependencies
   - Create `.env.example` template
   - Set up `.gitignore`

2. **Configuration Module**
   - Implement `settings.py` with configuration dataclasses
   - Add environment variable loading with python-dotenv
   - Implement configuration validation
   - Create region and brand enums

3. **Logging Infrastructure**
   - Implement structured logger in `utils/logger.py`
   - Configure log levels and formatting
   - Add sensitive data redaction
   - Create logging utilities

4. **Error Handling Foundation**
   - Define custom exception hierarchy in `utils/errors.py`
   - Implement error context dataclass
   - Create basic error handling utilities

**Deliverables:**
- Working configuration system
- Structured logging
- Project skeleton ready for development

**Testing:**
- Unit tests for configuration loading
- Configuration validation tests
- Logger functionality tests

---

### Phase 2: Hyundai API Integration (Week 2)

**Objectives:**
- Integrate with hyundai_kia_connect_api
- Implement refresh strategies
- Create data mapping layer

**Tasks:**
1. **API Client Implementation**
   - Create `HyundaiAPIClient` class in `hyundai/api_client.py`
   - Implement VehicleManager initialization
   - Add authentication handling
   - Implement vehicle discovery

2. **Refresh Strategies**
   - Implement cached refresh method
   - Implement force refresh method
   - Implement smart refresh method
   - Add strategy pattern abstraction

3. **Data Mapping**
   - Create data model classes in `hyundai/data_mapper.py`
   - Implement battery data extraction
   - Implement EV data extraction
   - Add status metadata generation
   - Handle missing/None values gracefully

4. **Circuit Breaker**
   - Implement circuit breaker pattern
   - Add failure tracking and recovery
   - Configure thresholds and timeouts

**Deliverables:**
- Functional Hyundai API client
- All three refresh strategies working
- Robust data mapping with None handling

**Testing:**
- Unit tests for data mappers
- Integration tests with mock VehicleManager
- Circuit breaker behavior tests

---

### Phase 3: MQTT Integration (Week 3)

**Objectives:**
- Implement MQTT client wrapper
- Create topic management
- Implement publishing functionality

**Tasks:**
1. **MQTT Client Implementation**
   - Create `MQTTClient` class in `mqtt/client.py`
   - Implement connection management
   - Add TLS/SSL support
   - Implement authentication

2. **Reconnection Logic**
   - Add automatic reconnection with exponential backoff
   - Implement connection health monitoring
   - Handle connection callbacks

3. **Topic Management**
   - Create `TopicManager` class in `mqtt/topics.py`
   - Define topic structure and naming
   - Implement message formatting
   - Configure QoS and retain flags

4. **Publishing Implementation**
   - Implement battery data publishing
   - Implement EV data publishing
   - Implement status data publishing
   - Add batch publishing for complete vehicle data

**Deliverables:**
- Working MQTT client with reconnection
- Structured topic hierarchy
- Data publishing functionality

**Testing:**
- MQTT connection tests with test broker
- Topic formatting tests
- Publishing tests with message verification
- Reconnection logic tests

---

### Phase 4: Command Processing (Week 4)

**Objectives:**
- Implement MQTT subscription
- Create command parsing and validation
- Implement command execution flow

**Tasks:**
1. **Command Handler**
   - Create `CommandHandler` class in `commands/handler.py`
   - Implement command queue
   - Add command parsing logic
   - Implement command validation

2. **Subscription Implementation**
   - Subscribe to command topics on MQTT connection
   - Implement message callback routing
   - Add command queue management

3. **Command Execution**
   - Implement cached command execution
   - Implement force command execution
   - Implement smart command execution
   - Add error handling for command failures

4. **Command Throttling**
   - Add rate limiting for commands
   - Prevent command spam
   - Implement command deduplication

**Deliverables:**
- Full command processing pipeline
- MQTT → API → MQTT flow working
- Command throttling and validation

**Testing:**
- Command parsing tests
- Command execution integration tests
- End-to-end command flow tests
- Throttling behavior tests

---

### Phase 5: Service Orchestration (Week 5)

**Objectives:**
- Implement main service application
- Add lifecycle management
- Implement graceful shutdown

**Tasks:**
1. **Main Application**
   - Create `main.py` with service orchestration
   - Implement component initialization
   - Add startup sequence
   - Configure signal handlers

2. **Initial Data Load**
   - Implement startup data fetch
   - Add configuration option for initial refresh
   - Handle initial load failures gracefully

3. **Service Loop**
   - Implement main event loop
   - Coordinate component interactions
   - Add health monitoring

4. **Shutdown Handling**
   - Implement graceful shutdown
   - Clean up MQTT connections
   - Close API sessions
   - Cancel async tasks

**Deliverables:**
- Complete working application
- Proper startup and shutdown
- Service orchestration

**Testing:**
- Service lifecycle tests
- Initialization tests
- Shutdown tests
- Integration tests for complete flows

---

### Phase 6: Error Handling and Resilience (Week 6)

**Objectives:**
- Enhance error handling across all components
- Implement retry logic
- Add comprehensive logging

**Tasks:**
1. **Enhanced Error Handling**
   - Add try-catch blocks in critical paths
   - Implement error context tracking
   - Add error recovery strategies
   - Improve error messages

2. **Retry Logic**
   - Implement exponential backoff for API calls
   - Add retry logic for MQTT operations
   - Configure retry limits and timeouts

3. **Monitoring and Observability**
   - Add performance metrics logging
   - Implement health check status
   - Add debug logging for troubleshooting
   - Track API call counts and timing

4. **Error Reporting**
   - Publish error status to MQTT
   - Add error topic for monitoring
   - Implement error notifications

**Deliverables:**
- Robust error handling
- Retry mechanisms
- Enhanced observability

**Testing:**
- Error scenario tests
- Retry logic tests
- Circuit breaker recovery tests
- Failure injection tests

---

### Phase 7: Documentation and Polish (Week 7)

**Objectives:**
- Complete documentation
- Create user guides
- Final testing and refinement

**Tasks:**
1. **Code Documentation**
   - Add docstrings to all public methods
   - Document complex logic
   - Add type hints throughout

2. **User Documentation**
   - Create comprehensive README
   - Document configuration options
   - Provide example configurations
   - Add troubleshooting guide

3. **Configuration Templates**
   - Create `.env.example` with all options
   - Add configuration validation guide
   - Document region and brand codes

4. **Final Testing**
   - Comprehensive system tests
   - Performance testing
   - Load testing with multiple vehicles
   - Edge case testing

**Deliverables:**
- Complete documentation
- Production-ready application
- Configuration examples

**Testing:**
- Full regression test suite
- Performance benchmarks
- Multi-vehicle tests

---

### Phase 8: Deployment and Optimization (Week 8)

**Objectives:**
- Prepare for deployment
- Optimize performance
- Add advanced features (optional)

**Tasks:**
1. **Deployment Preparation**
   - Create Docker container (optional)
   - Add systemd service file
   - Document deployment options
   - Create installation guide

2. **Performance Optimization**
   - Profile application performance
   - Optimize MQTT payload sizes
   - Reduce API call overhead
   - Memory usage optimization

3. **Advanced Features (Optional)**
   - Multi-vehicle support enhancement
   - Homeassistant MQTT discovery
   - Custom topic configuration
   - WebSocket status dashboard

4. **Production Hardening**
   - Security review
   - Credential handling audit
   - Rate limit configuration
   - Production logging configuration

**Deliverables:**
- Deployment-ready application
- Performance optimizations
- Optional advanced features

**Testing:**
- Load testing
- Security testing
- Long-running stability tests
- Multi-vehicle concurrent tests

---

## Implementation Guidelines

### Code Organization Principles

1. **Separation of Concerns**
   - Each module has a single, well-defined responsibility
   - Clear boundaries between layers (API, MQTT, config, etc.)
   - No circular dependencies between modules

2. **Dependency Injection**
   - Components receive dependencies via constructor
   - Facilitates testing with mock objects
   - Makes dependencies explicit and manageable

3. **Async/Await Pattern**
   - Use async/await throughout for non-blocking I/O
   - Properly handle async context in all network operations
   - Use `asyncio.gather()` for concurrent operations

4. **Error Handling Strategy**
   - Use custom exceptions for different error types
   - Always include context in error messages
   - Log errors before re-raising or handling
   - Implement recovery strategies where appropriate

### Configuration Best Practices

1. **Environment Variables**
   - All secrets via environment variables only
   - Provide sensible defaults for non-sensitive config
   - Validate all configuration on startup
   - Fail fast with clear error messages

2. **Configuration Validation**
   - Check required fields are present
   - Validate data types and ranges
   - Verify region and brand codes
   - Test MQTT and API connectivity on startup

### Security Considerations

1. **Credential Management**
   - Never log credentials or tokens
   - Use environment variables for secrets
   - Redact sensitive data in logs
   - Clear credentials from memory when possible

2. **MQTT Security**
   - Support TLS/SSL encryption
   - Implement authentication
   - Use secure client IDs
   - Validate incoming command payloads

3. **API Security**
   - Respect rate limits strictly
   - Implement backoff for failures
   - Handle token refresh automatically
   - Validate API responses before processing

### Performance Considerations

1. **API Efficiency**
   - Default to cached refresh when possible
   - Use smart refresh to minimize unnecessary calls
   - Batch operations where supported
   - Monitor API call frequency

2. **MQTT Optimization**
   - Use appropriate QoS levels
   - Minimize payload sizes
   - Use retain flag judiciously
   - Batch publishes when possible

3. **Resource Management**
   - Clean up resources properly
   - Monitor memory usage
   - Limit queue sizes
   - Handle long-running tasks efficiently

### Testing Best Practices

1. **Test Coverage**
   - Aim for >80% code coverage
   - Test happy paths and error cases
   - Test edge cases and boundaries
   - Test concurrent operations

2. **Test Organization**
   - Separate unit, integration, and system tests
   - Use fixtures for common setup
   - Mock external dependencies
   - Use async test frameworks

3. **Test Data**
   - Use realistic test data
   - Test with None/missing values
   - Test with multiple vehicles
   - Test with different regions/brands

---

## Critical Success Factors

### IMPORTANT: Event-Driven Architecture

**Requirement:** No periodic polling - strictly MQTT-triggered updates.

**Implementation Strategy:**
- No background tasks that poll on schedule
- All data updates triggered by MQTT commands only
- Initial data load on startup, then wait for commands
- Use event loop to wait for MQTT messages

**Validation:**
- No `asyncio.sleep()` in loops for periodic checks
- All refresh calls originate from command handler
- Monitor API call patterns to verify no polling

### IMPORTANT: Smart Refresh Strategy

**Requirement:** Efficient API usage with three-tier refresh approach.

**Implementation Strategy:**
- Default to cached refresh for most queries
- Use smart refresh with reasonable max_age (e.g., 300 seconds)
- Only use force refresh when explicitly needed
- Respect API rate limits with circuit breaker

**Validation:**
- Track API call counts per refresh type
- Monitor cache hit rates
- Verify circuit breaker triggers under load
- Measure response times for each strategy

### IMPORTANT: Robust Error Handling

**Requirement:** Graceful handling of API and MQTT failures.

**Implementation Strategy:**
- Circuit breaker for API failures
- Exponential backoff for retries
- Automatic MQTT reconnection
- Comprehensive error logging

**Validation:**
- Test with API service down
- Test with MQTT broker down
- Test with network interruptions
- Verify recovery after failures

### IMPORTANT: Multi-Region Support

**Requirement:** Support all Hyundai/Kia regions and brands.

**Implementation Strategy:**
- Configuration-driven region selection
- Enum-based region and brand codes
- No hard-coded regional logic
- Extensible for new regions

**Validation:**
- Test with different region configurations
- Verify brand-specific behaviors
- Test with multiple vehicles from different regions

---

## Success Metrics

### Functional Metrics
- ✅ Successfully connects to Hyundai API
- ✅ Authenticates and discovers vehicles
- ✅ Publishes battery and EV data to MQTT
- ✅ Responds to all three command types (cached, force, smart)
- ✅ Handles errors gracefully without crashing
- ✅ Supports multiple regions and brands

### Performance Metrics
- ⚡ Cached refresh completes in <2 seconds
- ⚡ Smart refresh decision made in <1 second
- ⚡ Force refresh completes within API limits (30-60s)
- ⚡ MQTT publish latency <100ms
- ⚡ Memory usage stable over 24+ hours

### Reliability Metrics
- 🛡️ Automatic recovery from MQTT disconnections
- 🛡️ Circuit breaker prevents API overload
- 🛡️ No crashes during 7-day continuous run
- 🛡️ Graceful degradation when API unavailable
- 🛡️ All errors logged with context

### Quality Metrics
- 📊 >80% code coverage
- 📊 All unit tests passing
- 📊 Integration tests passing
- 📊 No critical security issues
- 📊 Documentation complete

---

This implementation plan provides a comprehensive roadmap for building a robust, efficient, and maintainable Hyundai Bluelink MQTT integration service. The phased approach ensures steady progress while maintaining code quality and testing rigor. Each phase builds upon the previous one, allowing for iterative development and continuous validation against requirements.
