"""MQTT client wrapper with connection management and publishing."""

import asyncio
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import paho.mqtt.client as mqtt

from ..config.settings import MQTTConfig
from ..hyundai.data_mapper import VehicleData
from ..utils.errors import MQTTConnectionError
from ..utils.logger import get_logger
from .topics import TOPIC_CONFIG, TopicManager

logger = get_logger(__name__)


class MQTTClient:
    """
    Wrapper for paho.mqtt.client with reconnection logic.
    """

    def __init__(self, config: MQTTConfig, on_command_callback: Optional[Callable] = None) -> None:
        self.config: MQTTConfig = config
        self.on_command_callback: Optional[Callable] = on_command_callback
        self.topic_manager: TopicManager = TopicManager(config.base_topic)
        self.client: mqtt.Client = mqtt.Client(client_id=config.client_id)
        self.connected: bool = False
        self.vehicle_ids: List[str] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._setup_callbacks()
        self._setup_authentication()
        if config.use_tls:
            self._setup_tls()

    def _setup_callbacks(self) -> None:
        """Configure MQTT callbacks for connection events."""
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _setup_authentication(self) -> None:
        """Configure MQTT authentication if credentials provided."""
        if self.config.username and self.config.password:
            self.client.username_pw_set(
                self.config.username,
                self.config.password
            )

    def _setup_tls(self) -> None:
        """Configure TLS/SSL for secure connection."""
        self.client.tls_set()

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        """Handle successful connection - subscribe to command topics."""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self.connected = True
            
            # Subscribe to refresh command topics for all vehicles
            command_topic = self.topic_manager.all_commands_topic()
            client.subscribe(command_topic, qos=1)
            logger.info(f"Subscribed to refresh command topic: {command_topic}")
            
            # Subscribe to control command topics for all vehicles
            control_command_topic = self.topic_manager.all_control_commands_topic()
            client.subscribe(control_command_topic, qos=1)
            logger.info(f"Subscribed to control command topics: {control_command_topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")
            self.connected = False

    def _on_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        """Handle disconnection - trigger reconnection logic."""
        logger.warning(f"Disconnected from MQTT broker (rc={rc})")
        self.connected = False
        
        if rc != 0:
            # Unexpected disconnection - paho will auto-reconnect
            logger.info("Attempting automatic reconnection...")

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        """Route incoming messages to command handler."""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            logger.info(f"Received message on topic {topic}: {payload}")
            
            # Extract vehicle ID from topic
            vehicle_id = self.topic_manager.extract_vehicle_id_from_topic(topic)
            logger.debug(f"Extracted vehicle_id: {vehicle_id}")
            
            # Debug condition checks
            logger.debug(f"Condition checks - vehicle_id: {vehicle_id is not None}, "
                        f"on_command_callback: {self.on_command_callback is not None}, "
                        f"loop: {self.loop is not None}")
            
            if vehicle_id and self.on_command_callback and self.loop:
                # Schedule the callback in the main event loop
                # (we're in paho-mqtt's thread, not the asyncio event loop)
                logger.info(f"Scheduling command callback for vehicle {vehicle_id}")
                future = asyncio.run_coroutine_threadsafe(
                    self.on_command_callback(topic, payload),
                    self.loop
                )
                logger.info(f"Command callback scheduled successfully for vehicle {vehicle_id}")
                
                # Add callback to handle any exceptions that occur during execution
                def log_callback_result(future):
                    try:
                        future.result()  # This will raise if the callback failed
                        logger.debug(f"Command callback completed successfully for vehicle {vehicle_id}")
                    except Exception as e:
                        logger.error(f"Command callback failed for vehicle {vehicle_id}: {e}", exc_info=True)
                
                future.add_done_callback(log_callback_result)
            else:
                # Log why command was not scheduled
                reasons = []
                if not vehicle_id:
                    reasons.append("vehicle_id is None or empty")
                if not self.on_command_callback:
                    reasons.append("on_command_callback is not set")
                if not self.loop:
                    reasons.append("event loop is not set")
                logger.warning(f"Cannot schedule command callback. Reasons: {', '.join(reasons)}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}", exc_info=True)

    async def connect(self) -> None:
        """Establish MQTT connection with retry logic."""
        try:
            # Store the current event loop FIRST, before any connection attempts
            # This ensures it's available if messages arrive immediately after connection
            self.loop = asyncio.get_event_loop()
            logger.debug(f"Event loop stored: {self.loop}")
            
            logger.info(
                f"Connecting to MQTT broker {self.config.broker_host}:{self.config.broker_port}"
            )
            
            self.client.connect(
                self.config.broker_host,
                self.config.broker_port,
                keepalive=60
            )
            
            # Start the MQTT client loop in a separate thread
            self.client.loop_start()
            
            # Wait for connection
            max_wait = 10
            waited = 0
            while not self.connected and waited < max_wait:
                await asyncio.sleep(0.5)
                waited += 0.5
            
            if not self.connected:
                raise MQTTConnectionError("Failed to connect to MQTT broker within timeout")
            
            logger.info("MQTT client connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise MQTTConnectionError(f"Connection failed: {e}")

    async def publish_vehicle_data(self, vehicle_data: VehicleData) -> None:
        """Publish all vehicle data to respective topics."""
        if not self.connected:
            logger.warning("Not connected to MQTT broker, skipping publish")
            return
        
        try:
            logger.info(f"Publishing vehicle data for {vehicle_data.vehicle_id}")
            
            # Get all messages to publish
            messages = vehicle_data.to_mqtt_messages()
            
            for metric_path, value in messages:
                # Build full topic
                parts = metric_path.split("/")
                if len(parts) == 2:
                    category, metric = parts
                    if category == "battery":
                        topic = self.topic_manager.battery_topic(vehicle_data.vehicle_id, metric)
                    elif category == "ev":
                        topic = self.topic_manager.ev_topic(vehicle_data.vehicle_id, metric)
                    elif category == "status":
                        topic = self.topic_manager.status_topic(vehicle_data.vehicle_id, metric)
                    elif category == "doors":
                        topic = self.topic_manager.door_topic(vehicle_data.vehicle_id, metric)
                    elif category == "windows":
                        topic = self.topic_manager.window_topic(vehicle_data.vehicle_id, metric)
                    elif category == "climate":
                        topic = self.topic_manager.climate_topic(vehicle_data.vehicle_id, metric)
                    elif category == "location":
                        topic = self.topic_manager.location_topic(vehicle_data.vehicle_id, metric)
                    elif category == "tires":
                        topic = self.topic_manager.tire_topic(vehicle_data.vehicle_id, metric)
                    elif category == "service":
                        topic = self.topic_manager.service_topic(vehicle_data.vehicle_id, metric)
                    elif category == "engine":
                        topic = self.topic_manager.engine_topic(vehicle_data.vehicle_id, metric)
                    else:
                        continue
                    
                    # Get topic configuration
                    config = TOPIC_CONFIG.get(metric_path, {"qos": 0, "retain": False})
                    
                    # Format message
                    if metric_path.startswith("status/"):
                        # Status messages are already in string format
                        payload = json.dumps({"value": value, "timestamp": vehicle_data.status.last_updated.isoformat() + "Z"})
                    else:
                        unit = config.get("unit")
                        payload = self.topic_manager.format_message(
                            value,
                            unit=unit,
                            timestamp=vehicle_data.status.last_updated
                        )
                    
                    # Publish
                    result = self.client.publish(
                        topic,
                        payload,
                        qos=config.get("qos", 0),
                        retain=config.get("retain", False)
                    )
                    
                    if result.rc != mqtt.MQTT_ERR_SUCCESS:
                        logger.warning(f"Failed to publish to {topic}: {result.rc}")
            
            logger.info(f"Successfully published data for vehicle {vehicle_data.vehicle_id}")
            
        except Exception as e:
            logger.error(f"Error publishing vehicle data: {e}")

    async def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> None:
        """
        Publish a message to a specific topic.
        
        Args:
            topic: MQTT topic
            payload: Message payload (will be converted to string)
            qos: Quality of Service level (0, 1, or 2)
            retain: Whether to retain the message
        """
        if not self.connected:
            logger.warning("Not connected to MQTT broker, skipping publish")
            return
        
        try:
            # Convert payload to string if needed
            if not isinstance(payload, str):
                payload = json.dumps(payload)
            
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.warning(f"Failed to publish to {topic}: {result.rc}")
            else:
                logger.debug(f"Published to {topic}: {payload[:100]}")  # Log first 100 chars
                
        except Exception as e:
            logger.error(f"Error publishing to {topic}: {e}")

    async def publish_error_status(self, vehicle_id: str, error_data: Optional[Dict[str, Any]]) -> None:
        """
        Publish error status to MQTT for monitoring.
        
        Args:
            vehicle_id: Vehicle identifier
            error_data: Error details dict, or None to clear error status
        """
        if not self.connected:
            logger.warning("Not connected to MQTT broker, skipping error status publish")
            return
        
        try:
            topic = self.topic_manager.status_topic(vehicle_id, "error")
            
            if error_data is None:
                # Clear error status
                payload = json.dumps({
                    "value": None,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
            else:
                # Publish error details
                payload = json.dumps({
                    "value": error_data,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
            
            result = self.client.publish(topic, payload, qos=0, retain=True)
            
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.warning(f"Failed to publish error status to {topic}: {result.rc}")
            else:
                logger.debug(f"Published error status for vehicle {vehicle_id}")
                
        except Exception as e:
            logger.error(f"Error publishing error status: {e}")

    def disconnect(self) -> None:
        """Gracefully disconnect from MQTT broker."""
        try:
            logger.info("Disconnecting from MQTT broker")
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logger.info("Disconnected from MQTT broker")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
