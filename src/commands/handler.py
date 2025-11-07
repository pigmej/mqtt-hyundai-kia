"""Command parsing and execution for MQTT commands."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from ..utils.errors import CommandError
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from ..hyundai.api_client import HyundaiAPIClient
    from ..mqtt.client import MQTTClient

logger = get_logger(__name__)


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
        self._last_command_time: dict[str, datetime] = {}
        self._min_command_interval: int = 5  # Minimum seconds between commands for same vehicle

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
