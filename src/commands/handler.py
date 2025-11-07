"""Command parsing and execution for MQTT commands."""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from ..utils.errors import CommandError
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from ..hyundai.api_client import HyundaiAPIClient
    from ..mqtt.client import MQTTClient

logger = get_logger(__name__)


# ===== Control Command Dataclasses =====

@dataclass
class ControlCommand:
    """Base class for control commands."""
    command_type: str  # "lock", "unlock", "climate", etc.
    vehicle_id: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @staticmethod
    def parse(topic: str, payload: str, topic_manager: Any) -> 'ControlCommand':
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
        valid_types = ["lock", "climate", "windows", "charge_port", "charging_current"]
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


# ===== Refresh Command Dataclass =====

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
        # Validate inputs
        if not topic or not isinstance(topic, str):
            raise CommandError("Invalid topic: must be a non-empty string")
        
        if not payload or not isinstance(payload, str):
            raise CommandError("Invalid payload: must be a non-empty string")
        
        # Extract vehicle_id from topic
        parts = topic.split("/")
        vehicle_id = parts[1] if len(parts) > 1 else None
        
        if not vehicle_id:
            raise CommandError(f"Could not extract vehicle_id from topic: {topic}")
        
        # Validate vehicle_id format (alphanumeric, underscore, hyphen)
        if not vehicle_id.replace("_", "").replace("-", "").isalnum():
            raise CommandError(f"Invalid vehicle_id format: {vehicle_id}")
        
        # Parse command type and parameters
        payload = payload.strip()
        if ":" in payload:
            cmd_type, param = payload.split(":", 1)
            cmd_type = cmd_type.strip()
            
            if cmd_type == "smart":
                try:
                    max_age = int(param.strip())
                    # Validate max_age is reasonable (between 1 second and 7 days)
                    if max_age < 1 or max_age > 604800:
                        raise CommandError(
                            f"Invalid max_age value: {max_age}. Must be between 1 and 604800 seconds."
                        )
                except ValueError:
                    raise CommandError(f"Invalid max_age parameter for smart command: {param}")
            else:
                max_age = None
        else:
            cmd_type = payload
            max_age = None
        
        # Validate command type
        if cmd_type not in ["cached", "force", "smart"]:
            raise CommandError(f"Invalid command type: {cmd_type}. Must be 'cached', 'force', or 'smart'")
        
        # Validate smart command has max_age
        if cmd_type == "smart" and max_age is None:
            raise CommandError("Smart command requires max_age parameter (e.g., 'smart:300')")
        
        return RefreshCommand(
            command_type=cmd_type,
            vehicle_id=vehicle_id,
            max_age_seconds=max_age
        )


class CommandHandler:
    """
    Processes MQTT commands and coordinates refresh operations.
    """

    def __init__(self, api_client: 'HyundaiAPIClient', mqtt_client: 'MQTTClient') -> None:
        self.api_client: 'HyundaiAPIClient' = api_client
        self.mqtt_client: 'MQTTClient' = mqtt_client
        self._command_queue: asyncio.Queue[RefreshCommand] = asyncio.Queue()
        self._control_command_queue: asyncio.Queue[ControlCommand] = asyncio.Queue()  # Separate queue for control commands
        self._last_command_time: dict[str, datetime] = {}
        self._min_command_interval: int = 5  # Minimum seconds between commands for same vehicle
        self._active_actions: Dict[str, ActionTracker] = {}  # Track active actions by action_id

    async def handle_command(self, command: RefreshCommand) -> None:
        """Execute refresh command and publish results."""
        vehicle_id = command.vehicle_id
        try:
            # Check for command throttling
            current_time = datetime.utcnow()
            
            if vehicle_id in self._last_command_time:
                elapsed = (current_time - self._last_command_time[vehicle_id]).total_seconds()
                if elapsed < self._min_command_interval:
                    logger.warning(
                        f"Command throttled for vehicle {vehicle_id} "
                        f"(elapsed: {elapsed:.1f}s < {self._min_command_interval}s)"
                    )
                    return
            
            self._last_command_time[vehicle_id] = current_time
            
            logger.info(
                f"Executing {command.command_type} command for vehicle {vehicle_id}"
            )
            
            # Execute appropriate refresh strategy
            if command.command_type == "cached":
                data = await self.api_client.refresh_cached(command.vehicle_id)
            elif command.command_type == "force":
                data = await self.api_client.refresh_force(command.vehicle_id)
            elif command.command_type == "smart":
                # max_age_seconds is guaranteed to be set for smart commands by validation in parse()
                assert command.max_age_seconds is not None, "Smart command must have max_age_seconds"
                data = await self.api_client.refresh_smart(
                    command.vehicle_id,
                    command.max_age_seconds
                )
            else:
                raise CommandError(f"Unknown command type: {command.command_type}")
            
            # Publish updated data to MQTT
            await self.mqtt_client.publish_vehicle_data(data)
            
            # Publish success status
            await self.mqtt_client.publish_error_status(vehicle_id, None)
            
            logger.info(f"Command executed successfully for vehicle {vehicle_id}")
            
        except Exception as e:
            logger.error(f"Command execution failed for vehicle {vehicle_id}: {e}")
            # Publish error status to MQTT for monitoring
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

    async def enqueue_command(self, topic: str, payload: str) -> None:
        """Add command to processing queue."""
        try:
            logger.info(f"enqueue_command called with topic={topic}, payload={payload}")
            command = RefreshCommand.parse(topic, payload)
            logger.debug(f"Command parsed successfully: {command}")
            await self._command_queue.put(command)
            logger.info(f"Command enqueued: {command.command_type} for vehicle {command.vehicle_id}")
            logger.debug(f"Queue size after enqueue: {self._command_queue.qsize()}")
        except CommandError as e:
            logger.error(f"Failed to parse command: {e}")
        except Exception as e:
            logger.error(f"Failed to enqueue command: {e}", exc_info=True)

    async def process_commands(self) -> None:
        """Process commands from queue (main command loop)."""
        logger.info("Starting command processing loop")
        
        while True:
            try:
                logger.debug("Waiting for command from queue...")
                command = await self._command_queue.get()
                logger.info(f"Retrieved command from queue: {command.command_type} for vehicle {command.vehicle_id}")
                await self.handle_command(command)
                logger.debug("Command handling completed")
            except asyncio.CancelledError:
                logger.info("Command processing loop cancelled")
                raise
            except Exception as e:
                logger.error(f"Error processing command: {e}", exc_info=True)

    # ===== Control Command Methods =====

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
                # Create climate options from command
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
        Wait for action completion using upstream API's built-in polling.
        
        The upstream API handles all polling internally when synchronous=True.
        We just wait for the final result and refresh vehicle data if successful.
        """
        from ..hyundai.api_client import EU_COMMAND_TIMEOUTS
        
        timeout = EU_COMMAND_TIMEOUTS.get(tracker.command_type, 60)
        
        try:
            # Let the upstream API handle all the polling
            final_status = await self.api_client.check_action_status(
                tracker.vehicle_id,
                tracker.action_id,
                synchronous=True,  # API polls internally until terminal state
                timeout_seconds=timeout
            )
            
            # Update tracker with final status
            tracker.update_status(final_status)
            
            # Publish final status to MQTT
            await self._publish_action_status(tracker, final_status)
            
            # If successful, refresh vehicle data to get updated state
            if final_status == "SUCCESS":
                try:
                    data = await self.api_client.refresh_force(tracker.vehicle_id)
                    await self.mqtt_client.publish_vehicle_data(data)
                except Exception as refresh_error:
                    logger.warning(f"Failed to refresh after successful command: {refresh_error}")
            
            logger.info(f"Action {tracker.action_id} completed with status: {final_status}")
            
        except Exception as e:
            logger.error(f"Action status check failed for {tracker.action_id}: {e}")
            tracker.update_status("FAILED", str(e))
            await self._publish_action_status(tracker, "FAILED", str(e))
        
        finally:
            # Cleanup tracker
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
        """Create climate options dictionary from ClimateCommand."""
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
        """Create windows options dictionary from WindowsCommand."""
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
