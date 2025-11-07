"""Hyundai API client wrapper with refresh strategies."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, List, Optional

from hyundai_kia_connect_api import VehicleManager

from ..config.settings import HyundaiConfig
from ..utils.errors import HyundaiAPIError, RefreshError
from ..utils.logger import get_logger
from .data_mapper import VehicleData, map_vehicle_data

logger = get_logger(__name__)


class CircuitBreaker:
    """
    Prevents repeated API calls when service is down.
    States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing)
    """

    def __init__(self, failure_threshold: int = 5, timeout: int = 60) -> None:
        self.failure_threshold: int = failure_threshold
        self.timeout: int = timeout
        self.failure_count: int = 0
        self.state: str = "CLOSED"
        self.last_failure_time: Optional[datetime] = None

    def can_execute(self) -> bool:
        """Check if circuit allows execution."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Check if timeout has elapsed
            if (
                self.last_failure_time
                and datetime.utcnow() - self.last_failure_time
                > timedelta(seconds=self.timeout)
            ):
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker entering HALF_OPEN state")
                return True
            return False

        # HALF_OPEN state
        return True

    def record_success(self) -> None:
        """Record successful execution."""
        if self.state == "HALF_OPEN":
            logger.info("Circuit breaker closing after successful execution")
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self) -> None:
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


class HyundaiAPIClient:
    """
    Wrapper for hyundai_kia_connect_api VehicleManager.
    Implements refresh strategies and error handling.
    """

    def __init__(self, config: HyundaiConfig) -> None:
        self.config: HyundaiConfig = config
        self.vehicle_manager: Optional[VehicleManager] = None
        self.circuit_breaker: CircuitBreaker = CircuitBreaker()

    async def initialize(self) -> None:
        """
        Authenticate and discover vehicles.
        Called once on startup.
        """
        try:
            logger.info(
                "Initializing Hyundai API client",
                extra={
                    "region": self.config.region.name,
                    "brand": self.config.brand.name,
                },
            )

            self.vehicle_manager = VehicleManager(
                region=self.config.region,
                brand=self.config.brand,
                username=self.config.username,
                password=self.config.password,
                pin=self.config.pin,
            )

            # Authenticate using thread pool to avoid blocking event loop
            logger.debug("Authenticating with Hyundai API")
            await asyncio.to_thread(self.vehicle_manager.check_and_refresh_token)

            # Discover vehicles using thread pool to avoid blocking event loop
            logger.debug("Discovering vehicles")
            await asyncio.to_thread(self.vehicle_manager.update_all_vehicles_with_cached_state)

            vehicle_count = len(self.vehicle_manager.vehicles)
            logger.info(f"Hyundai API client initialized with {vehicle_count} vehicles")

        except Exception as e:
            logger.error(f"Failed to initialize Hyundai API client: {e}")
            raise HyundaiAPIError(f"Initialization failed: {e}")

    async def refresh_cached(self, vehicle_id: str) -> VehicleData:
        """
        Fast cached update using update_vehicle_with_cached_state().
        Returns local cached data without API call.
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")

        try:
            logger.info(f"Performing cached refresh for vehicle {vehicle_id}")

            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")

            # Wrap synchronous call in thread pool to avoid blocking event loop
            logger.debug(f"Updating vehicle {vehicle_id} with cached state")
            await asyncio.to_thread(self.vehicle_manager.update_vehicle_with_cached_state, vehicle_id)
            vehicle = self.vehicle_manager.get_vehicle(vehicle_id)

            if not vehicle:
                raise RefreshError(f"Vehicle {vehicle_id} not found")

            self.circuit_breaker.record_success()
            return map_vehicle_data(vehicle, "cached", "cached")

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Cached refresh failed for vehicle {vehicle_id}: {e}")
            raise RefreshError(f"Cached refresh failed: {e}")

    async def refresh_force(self, vehicle_id: str) -> VehicleData:
        """
        Force refresh from vehicle using force_refresh_vehicle_state().
        Makes real API call to vehicle for fresh data.
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")

        try:
            logger.info(f"Performing force refresh for vehicle {vehicle_id}")

            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")

            # Wrap synchronous call in thread pool to avoid blocking event loop
            logger.debug(f"Forcing refresh of vehicle {vehicle_id}")
            await asyncio.to_thread(self.vehicle_manager.force_refresh_vehicle_state, vehicle_id)
            vehicle = self.vehicle_manager.get_vehicle(vehicle_id)

            if not vehicle:
                raise RefreshError(f"Vehicle {vehicle_id} not found")

            self.circuit_breaker.record_success()
            return map_vehicle_data(vehicle, "fresh", "force")

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Force refresh failed for vehicle {vehicle_id}: {e}")
            raise RefreshError(f"Force refresh failed: {e}")

    async def refresh_smart(self, vehicle_id: str, max_age_seconds: int) -> VehicleData:
        """
        Smart refresh using check_and_force_update_vehicle(seconds).
        Only refreshes if data is older than max_age_seconds.
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")

        try:
            logger.info(
                f"Performing smart refresh for vehicle {vehicle_id}",
                extra={"max_age_seconds": max_age_seconds},
            )

            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")

            # Get vehicle and check timestamp before refresh
            vehicle = self.vehicle_manager.get_vehicle(vehicle_id)
            if not vehicle:
                raise RefreshError(f"Vehicle {vehicle_id} not found")

            timestamp_before = getattr(vehicle, "last_updated_at", None)

            # Perform smart refresh using thread pool to avoid blocking event loop
            logger.debug(f"Checking and forcing update for vehicle {vehicle_id}")
            await asyncio.to_thread(
                self.vehicle_manager.check_and_force_update_vehicle,
                max_age_seconds, vehicle_id
            )

            # Get vehicle again to check if data was actually refreshed
            vehicle = self.vehicle_manager.get_vehicle(vehicle_id)
            if not vehicle:
                raise RefreshError(f"Vehicle {vehicle_id} not found")

            # Determine if data is fresh or cached based on timestamp change
            timestamp_after = getattr(vehicle, "last_updated_at", None)

            # If timestamp changed, data is fresh; otherwise it's cached
            if (
                timestamp_before
                and timestamp_after
                and timestamp_after > timestamp_before
            ):
                data_source = "fresh"
                logger.info(
                    f"Smart refresh fetched fresh data for vehicle {vehicle_id}"
                )
            else:
                data_source = "cached"
                logger.info(f"Smart refresh used cached data for vehicle {vehicle_id}")

            self.circuit_breaker.record_success()
            return map_vehicle_data(vehicle, data_source, "smart")

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Smart refresh failed for vehicle {vehicle_id}: {e}")
            raise RefreshError(f"Smart refresh failed: {e}")

    def get_vehicle_ids(self) -> List[str]:
        """Return list of available vehicle IDs."""
        if not self.vehicle_manager:
            return []

        # Check if vehicles are strings (vehicle IDs) or objects
        vehicle_ids = []
        for vehicle in self.vehicle_manager.vehicles:
            if isinstance(vehicle, str):
                vehicle_ids.append(vehicle)
            elif hasattr(vehicle, 'id'):
                vehicle_ids.append(vehicle.id)
            elif hasattr(vehicle, 'vin'):
                vehicle_ids.append(vehicle.vin)
            else:
                # Fallback: use string representation
                vehicle_ids.append(str(vehicle))
        
        return vehicle_ids
