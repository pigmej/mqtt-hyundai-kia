"""Main application entry point for Hyundai MQTT service."""

import asyncio
import signal
from pathlib import Path
from typing import Any, Optional

from .commands import CommandHandler
from .config import AppConfig, load_config
from .hyundai import HyundaiAPIClient
from .mqtt import MQTTClient
from .utils import get_logger

logger = get_logger(__name__)


class HyundaiMQTTService:
    """
    Main service orchestrator for Hyundai MQTT integration.
    """

    def __init__(self) -> None:
        self.config: Optional[AppConfig] = None
        self.api_client: Optional[HyundaiAPIClient] = None
        self.mqtt_client: Optional[MQTTClient] = None
        self.command_handler: Optional[CommandHandler] = None
        self._shutdown_event: asyncio.Event = asyncio.Event()

    async def _route_mqtt_command(self, topic: str, payload: str) -> None:
        """Route MQTT commands to appropriate handler."""
        if not self.command_handler:
            logger.error("Command handler not initialized")
            return

        # Check if it's a control command or refresh command
        if "/commands/refresh" in topic:
            # Refresh command
            await self.command_handler.enqueue_command(topic, payload)
        elif "/commands/" in topic:
            # Control command (lock, climate, windows, etc.)
            await self.command_handler.enqueue_control_command(topic, payload)
        else:
            logger.warning(f"Unknown command topic: {topic}")

    async def initialize(self) -> None:
        """Initialize all components."""
        try:
            # Load and validate configuration
            logger.info("Loading configuration")
            self.config = load_config()

            # Configure logging level
            import logging

            logging.getLogger().setLevel(self.config.log_level)

            # Initialize Hyundai API client
            logger.info("Initializing Hyundai API client")
            self.api_client = HyundaiAPIClient(self.config.hyundai)
            await self.api_client.initialize()

            # Initialize MQTT client with command callback
            logger.info("Initializing MQTT client")
            self.mqtt_client = MQTTClient(
                self.config.mqtt, on_command_callback=self._route_mqtt_command
            )

            # Initialize command handler with both clients
            self.command_handler = CommandHandler(self.api_client, self.mqtt_client)

            # Connect to MQTT broker
            await self.mqtt_client.connect()

            # Create service readiness file for health check
            try:
                Path("/tmp/service-ready").touch()
                logger.info("Service readiness file created")
            except Exception as e:
                logger.warning(f"Failed to create service readiness file: {e}")

            logger.info("Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize service: {e}", exc_info=True)
            raise

    async def load_initial_data(self) -> None:
        """Load cached data on startup if configured."""
        if not self.config or not self.config.initial_refresh:
            logger.info("Skipping initial data load (INITIAL_REFRESH=false)")
            return

        logger.info("Loading initial cached data")

        if not self.api_client or not self.mqtt_client:
            logger.error("Cannot load initial data: components not initialized")
            return

        vehicle_ids = self.api_client.get_vehicle_ids()
        logger.info(f"Found {len(vehicle_ids)} vehicles")

        for vehicle_id in vehicle_ids:
            try:
                logger.info(f"Loading initial data for vehicle {vehicle_id}")
                data = await self.api_client.refresh_cached(vehicle_id)
                await self.mqtt_client.publish_vehicle_data(data)
                logger.info(f"Initial data loaded for vehicle {vehicle_id}")
            except Exception as e:
                logger.error(
                    f"Failed to load initial data for vehicle {vehicle_id}: {e}"
                )

    async def run(self) -> None:
        """Main service loop."""
        try:
            # Initialize components
            await self.initialize()

            # Load initial data
            await self.load_initial_data()

            if not self.command_handler:
                raise RuntimeError("Command handler not initialized")

            # Start command processing loops
            logger.info("Starting command processing")
            command_task = asyncio.create_task(self.command_handler.process_commands())
            control_command_task = asyncio.create_task(
                self.command_handler.process_control_commands()
            )

            logger.info("Service is running. Waiting for MQTT commands...")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

            logger.info("Shutdown signal received")

            # Cancel tasks
            command_task.cancel()
            control_command_task.cancel()
            try:
                await command_task
            except asyncio.CancelledError:
                pass
            try:
                await control_command_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            logger.critical(f"Service failed: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Graceful shutdown of all components."""
        logger.info("Shutting down service")

        # Remove service readiness file
        try:
            readiness_file = Path("/tmp/service-ready")
            if readiness_file.exists():
                readiness_file.unlink()
                logger.info("Service readiness file removed")
        except Exception as e:
            logger.warning(f"Failed to remove service readiness file: {e}")

        if self.mqtt_client:
            self.mqtt_client.disconnect()

        logger.info("Service shutdown complete")

    def signal_handler(self, sig: int, frame: Any) -> None:
        """Handle shutdown signals (SIGINT, SIGTERM)."""
        logger.info(f"Received signal {sig}, initiating shutdown")
        # Schedule the shutdown event in the event loop
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(self._shutdown_event.set)
        except RuntimeError:
            # Fallback if called outside event loop context
            self._shutdown_event.set()


async def main() -> None:
    """Application entry point."""
    service = HyundaiMQTTService()

    # Register signal handlers
    signal.signal(signal.SIGINT, service.signal_handler)
    signal.signal(signal.SIGTERM, service.signal_handler)

    # Run service
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
