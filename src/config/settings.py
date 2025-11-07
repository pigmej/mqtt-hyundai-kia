"""Configuration settings loaded from environment variables."""

import os
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

from dotenv import load_dotenv


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
    """Hyundai API configuration."""
    username: str
    password: str
    pin: str
    region: Region
    brand: Brand
    vehicle_id: Optional[str] = None

    @staticmethod
    def from_env() -> 'HyundaiConfig':
        """Load from environment variables with validation."""
        from ..utils.errors import ConfigurationError
        
        username = os.getenv("HYUNDAI_USERNAME")
        password = os.getenv("HYUNDAI_PASSWORD")
        pin = os.getenv("HYUNDAI_PIN")
        
        # Validate required fields
        if not all([username, password, pin]):
            raise ConfigurationError("Missing required Hyundai credentials (HYUNDAI_USERNAME, HYUNDAI_PASSWORD, HYUNDAI_PIN)")
        
        try:
            region = Region(int(os.getenv("HYUNDAI_REGION", "1")))
            brand = Brand(int(os.getenv("HYUNDAI_BRAND", "1")))
        except (ValueError, KeyError) as e:
            raise ConfigurationError(f"Invalid region or brand configuration: {e}")
        
        return HyundaiConfig(
            username=username,  # type: ignore
            password=password,  # type: ignore
            pin=pin,  # type: ignore
            region=region,
            brand=brand,
            vehicle_id=os.getenv("HYUNDAI_VEHICLE_ID")
        )


@dataclass
class MQTTConfig:
    """MQTT broker configuration."""
    broker_host: str
    broker_port: int
    username: Optional[str]
    password: Optional[str]
    use_tls: bool
    client_id: str
    qos_level: int
    base_topic: str

    @staticmethod
    def from_env() -> 'MQTTConfig':
        """Load from environment variables with validation."""
        from ..utils.errors import ConfigurationError
        
        broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        
        try:
            broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
            qos_level = int(os.getenv("MQTT_QOS", "1"))
        except ValueError as e:
            raise ConfigurationError(f"Invalid MQTT port or QoS configuration: {e}")
        
        use_tls_str = os.getenv("MQTT_USE_TLS", "false").lower()
        use_tls = use_tls_str in ("true", "1", "yes")
        
        return MQTTConfig(
            broker_host=broker_host,
            broker_port=broker_port,
            username=os.getenv("MQTT_USERNAME"),
            password=os.getenv("MQTT_PASSWORD"),
            use_tls=use_tls,
            client_id=os.getenv("MQTT_CLIENT_ID", "hyundai_mqtt"),
            qos_level=qos_level,
            base_topic=os.getenv("MQTT_BASE_TOPIC", "hyundai")
        )


@dataclass
class AppConfig:
    """Complete application configuration."""
    hyundai: HyundaiConfig
    mqtt: MQTTConfig
    log_level: str
    initial_refresh: bool

    @staticmethod
    def from_env() -> 'AppConfig':
        """Load complete configuration from environment."""
        initial_refresh_str = os.getenv("INITIAL_REFRESH", "true").lower()
        initial_refresh = initial_refresh_str in ("true", "1", "yes")
        
        return AppConfig(
            hyundai=HyundaiConfig.from_env(),
            mqtt=MQTTConfig.from_env(),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            initial_refresh=initial_refresh
        )


def load_config() -> AppConfig:
    """Load configuration from .env file and environment variables."""
    # Load .env file if it exists
    load_dotenv()
    
    # Load and return configuration
    return AppConfig.from_env()
