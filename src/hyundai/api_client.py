"""Hyundai API client wrapper with refresh strategies."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, List, Optional

from hyundai_kia_connect_api import VehicleManager, ClimateRequestOptions, WindowRequestOptions
from hyundai_kia_connect_api.ApiImpl import ORDER_STATUS

from ..config.settings import HyundaiConfig
from ..utils.errors import HyundaiAPIError, RefreshError
from ..utils.logger import get_logger
from .data_mapper import VehicleData, map_vehicle_data

logger = get_logger(__name__)


# EU-specific timeout configurations per command type (seconds)
EU_COMMAND_TIMEOUTS = {
    "lock": 60,
    "unlock": 60,
    "climate_start": 120,
    "climate_stop": 120,
    "climate": 120,  # Generic climate command
    "windows": 90,
    "charge_port": 60,
    "charging_current": 120,  # EU-only feature
}


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
        self._token_refresh_lock: asyncio.Lock = asyncio.Lock()
        self._last_refresh_time: Optional[datetime] = None

    async def _is_token_expired_error(self, error: Exception) -> bool:
        """Check if error indicates token expiration."""
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in [
            "token is expired",
            "key not authorized: token is expired",
            "authentication failed",
            "unauthorized"
        ])

    async def _refresh_token_safely(self) -> None:
        """Safely refresh token with concurrency protection."""
        async with self._token_refresh_lock:
            # Double-check pattern to avoid redundant refreshes
            if self._last_refresh_time and \
               (datetime.utcnow() - self._last_refresh_time).seconds < 30:
                return
            
            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")
            
            logger.info("Refreshing expired token")
            await asyncio.to_thread(self.vehicle_manager.check_and_refresh_token)
            self._last_refresh_time = datetime.utcnow()
            logger.info("Token refresh completed successfully")

    async def _execute_with_retry(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation with token refresh and retry logic."""
        try:
            return await operation(*args, **kwargs)
        except Exception as e:
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await operation(*args, **kwargs)
            else:
                # Re-raise non-token errors
                raise

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
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.refresh_cached(vehicle_id)
            else:
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
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.refresh_force(vehicle_id)
            else:
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
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.refresh_smart(vehicle_id, max_age_seconds)
            else:
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

    # ===== Control Command Methods =====

    async def lock_vehicle(self, vehicle_id: str) -> str:
        """
        Lock vehicle doors.
        
        Returns:
            action_id: Unique identifier for tracking command execution
        
        Raises:
            HyundaiAPIError: If circuit breaker is open or execution fails
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")
        
        try:
            logger.info(f"Executing lock command for vehicle {vehicle_id}")
            
            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")
            
            # Execute via thread pool - DO NOT assume success
            action_id = await asyncio.to_thread(
                self.vehicle_manager.lock,
                vehicle_id
            )
            
            self.circuit_breaker.record_success()
            logger.info(f"Lock command initiated with action_id: {action_id}")
            return action_id
            
        except Exception as e:
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.lock_vehicle(vehicle_id)
            else:
                self.circuit_breaker.record_failure()
                logger.error(f"Lock command failed for vehicle {vehicle_id}: {e}")
                raise HyundaiAPIError(f"Lock command failed: {e}")

    async def unlock_vehicle(self, vehicle_id: str) -> str:
        """
        Unlock vehicle doors.
        
        Returns:
            action_id: Unique identifier for tracking command execution
        
        Raises:
            HyundaiAPIError: If circuit breaker is open or execution fails
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")
        
        try:
            logger.info(f"Executing unlock command for vehicle {vehicle_id}")
            
            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")
            
            # Execute via thread pool - DO NOT assume success
            action_id = await asyncio.to_thread(
                self.vehicle_manager.unlock,
                vehicle_id
            )
            
            self.circuit_breaker.record_success()
            logger.info(f"Unlock command initiated with action_id: {action_id}")
            return action_id
            
        except Exception as e:
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.unlock_vehicle(vehicle_id)
            else:
                self.circuit_breaker.record_failure()
                logger.error(f"Unlock command failed for vehicle {vehicle_id}: {e}")
                raise HyundaiAPIError(f"Unlock command failed: {e}")

    async def start_climate(self, vehicle_id: str, options: Any) -> str:
        """
        Start climate control with options.
        
        Args:
            vehicle_id: Vehicle identifier
            options: Climate control options dictionary (will be converted to ClimateRequestOptions)
        
        Returns:
            action_id: Unique identifier for tracking command execution
        
        Raises:
            HyundaiAPIError: If circuit breaker is open or execution fails
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")
        
        try:
            logger.info(f"Executing start climate command for vehicle {vehicle_id} with options: {options}")
            
            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")
            
            # Convert dictionary to ClimateRequestOptions object
            climate_options = ClimateRequestOptions(
                set_temp=options.get("set_temp"),
                duration=options.get("duration"),
                defrost=options.get("defrost"),
                climate=options.get("climate"),
                steering_wheel=options.get("steering_wheel"),
                front_left_seat=options.get("front_left_seat"),
                front_right_seat=options.get("front_right_seat"),
                rear_left_seat=options.get("rear_left_seat"),
                rear_right_seat=options.get("rear_right_seat")
            )
            
            # Execute via thread pool - DO NOT assume success
            action_id = await asyncio.to_thread(
                self.vehicle_manager.start_climate,
                vehicle_id,
                climate_options
            )
            
            self.circuit_breaker.record_success()
            logger.info(f"Start climate command initiated with action_id: {action_id}")
            return action_id
            
        except Exception as e:
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.start_climate(vehicle_id, options)
            else:
                self.circuit_breaker.record_failure()
                logger.error(f"Start climate command failed for vehicle {vehicle_id}: {e}")
                raise HyundaiAPIError(f"Start climate command failed: {e}")

    async def stop_climate(self, vehicle_id: str) -> str:
        """
        Stop climate control.
        
        Returns:
            action_id: Unique identifier for tracking command execution
        
        Raises:
            HyundaiAPIError: If circuit breaker is open or execution fails
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")
        
        try:
            logger.info(f"Executing stop climate command for vehicle {vehicle_id}")
            
            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")
            
            # Check if climate is currently on before stopping
            vehicle = self.vehicle_manager.get_vehicle(vehicle_id)
            if vehicle:
                climate_is_on = getattr(vehicle, 'air_ctrl_is_on', None)
                logger.info(f"Vehicle climate status before command: air_ctrl_is_on={climate_is_on}")
            
            # Execute via thread pool - DO NOT assume success
            action_id = await asyncio.to_thread(
                self.vehicle_manager.stop_climate,
                vehicle_id
            )
            
            logger.info(f"stop_climate returned action_id: {action_id} (type: {type(action_id)})")
            
            self.circuit_breaker.record_success()
            logger.info(f"Stop climate command initiated with action_id: {action_id}")
            return action_id
            
        except Exception as e:
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.stop_climate(vehicle_id)
            else:
                self.circuit_breaker.record_failure()
                logger.error(f"Stop climate command failed for vehicle {vehicle_id}: {e}")
                raise HyundaiAPIError(f"Stop climate command failed: {e}")

    async def set_windows_state(self, vehicle_id: str, options: Any) -> str:
        """
        Set window states.
        
        Args:
            vehicle_id: Vehicle identifier
            options: Window state options dictionary (will be converted to WindowRequestOptions)
        
        Returns:
            action_id: Unique identifier for tracking command execution
        
        Raises:
            HyundaiAPIError: If circuit breaker is open or execution fails
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")
        
        try:
            logger.info(f"Executing set windows command for vehicle {vehicle_id} with options: {options}")
            
            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")
            
            # Convert dictionary to WindowRequestOptions object
            window_options = WindowRequestOptions(
                front_left=options.get("front_left"),
                front_right=options.get("front_right"),
                back_left=options.get("back_left"),
                back_right=options.get("back_right")
            )
            
            # Execute via thread pool - DO NOT assume success
            action_id = await asyncio.to_thread(
                self.vehicle_manager.set_windows_state,
                vehicle_id,
                window_options
            )
            
            self.circuit_breaker.record_success()
            logger.info(f"Set windows command initiated with action_id: {action_id}")
            return action_id
            
        except Exception as e:
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.set_windows_state(vehicle_id, options)
            else:
                self.circuit_breaker.record_failure()
                logger.error(f"Set windows command failed for vehicle {vehicle_id}: {e}")
                raise HyundaiAPIError(f"Set windows command failed: {e}")

    async def open_charge_port(self, vehicle_id: str) -> str:
        """
        Open charge port.
        
        Returns:
            action_id: Unique identifier for tracking command execution
        
        Raises:
            HyundaiAPIError: If circuit breaker is open or execution fails
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")
        
        try:
            logger.info(f"Executing open charge port command for vehicle {vehicle_id}")
            
            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")
            
            # Execute via thread pool - DO NOT assume success
            action_id = await asyncio.to_thread(
                self.vehicle_manager.open_charge_port,
                vehicle_id
            )
            
            self.circuit_breaker.record_success()
            logger.info(f"Open charge port command initiated with action_id: {action_id}")
            return action_id
            
        except Exception as e:
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.open_charge_port(vehicle_id)
            else:
                self.circuit_breaker.record_failure()
                logger.error(f"Open charge port command failed for vehicle {vehicle_id}: {e}")
                raise HyundaiAPIError(f"Open charge port command failed: {e}")

    async def close_charge_port(self, vehicle_id: str) -> str:
        """
        Close charge port.
        
        Returns:
            action_id: Unique identifier for tracking command execution
        
        Raises:
            HyundaiAPIError: If circuit breaker is open or execution fails
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")
        
        try:
            logger.info(f"Executing close charge port command for vehicle {vehicle_id}")
            
            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")
            
            # Execute via thread pool - DO NOT assume success
            action_id = await asyncio.to_thread(
                self.vehicle_manager.close_charge_port,
                vehicle_id
            )
            
            self.circuit_breaker.record_success()
            logger.info(f"Close charge port command initiated with action_id: {action_id}")
            return action_id
            
        except Exception as e:
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.close_charge_port(vehicle_id)
            else:
                self.circuit_breaker.record_failure()
                logger.error(f"Close charge port command failed for vehicle {vehicle_id}: {e}")
                raise HyundaiAPIError(f"Close charge port command failed: {e}")

    async def set_charging_current(self, vehicle_id: str, level: int) -> str:
        """
        Set AC charging current limit (EU-only feature).
        
        Args:
            vehicle_id: Vehicle identifier
            level: Charging current level (1=100%, 2=90%, 3=60%)
        
        Returns:
            action_id: Unique identifier for tracking command execution
        
        Raises:
            HyundaiAPIError: If circuit breaker is open or execution fails
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")
        
        try:
            logger.info(f"Executing set charging current command for vehicle {vehicle_id} with level: {level}")
            
            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")
            
            # Execute via thread pool - DO NOT assume success
            action_id = await asyncio.to_thread(
                self.vehicle_manager.set_charging_current,
                vehicle_id,
                level
            )
            
            self.circuit_breaker.record_success()
            logger.info(f"Set charging current command initiated with action_id: {action_id}")
            return action_id
            
        except Exception as e:
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.set_charging_current(vehicle_id, level)
            else:
                self.circuit_breaker.record_failure()
                logger.error(f"Set charging current command failed for vehicle {vehicle_id}: {e}")
                raise HyundaiAPIError(f"Set charging current command failed: {e}")

    async def check_action_status(
        self,
        vehicle_id: str,
        action_id: str,
        synchronous: bool = True,
        timeout_seconds: int = 60
    ) -> str:
        """
        Check status of vehicle action.
        
        Args:
            vehicle_id: Vehicle identifier
            action_id: Action identifier from control command
            synchronous: If True, poll until completion; if False, return immediately
            timeout_seconds: Maximum time to wait for completion (EU-specific)
        
        Returns:
            Final status: "SUCCESS", "FAILED", "TIMEOUT", or "UNKNOWN"
        
        Implementation:
            - Polls every 5 seconds if synchronous=True
            - Returns immediately with current status if synchronous=False
            - Uses EU-specific timeout configurations per command type
        """
        if not self.circuit_breaker.can_execute():
            raise HyundaiAPIError("Circuit breaker is open")
        
        try:
            if not self.vehicle_manager:
                raise HyundaiAPIError("VehicleManager not initialized")
            
            if synchronous:
                # Use API's built-in synchronous polling
                status_response = await asyncio.to_thread(
                    self.vehicle_manager.check_action_status,
                    vehicle_id,
                    action_id,
                    synchronous=True,  # Let API handle polling internally
                    timeout=timeout_seconds
                )
                
                # Parse final status from response
                status = self._parse_action_status(status_response)
                logger.info(f"Action {action_id} reached terminal state: {status}")
                return status
            else:
                # Single status check
                status_response = await asyncio.to_thread(
                    self.vehicle_manager.check_action_status,
                    vehicle_id,
                    action_id
                )
                return self._parse_action_status(status_response)
                
        except Exception as e:
            if await self._is_token_expired_error(e):
                logger.warning(f"Token expired detected, attempting refresh: {e}")
                await self._refresh_token_safely()
                logger.info("Retrying operation after token refresh")
                return await self.check_action_status(vehicle_id, action_id, synchronous, timeout_seconds)
            else:
                self.circuit_breaker.record_failure()
                logger.error(f"Action status check failed: {e}")
                raise HyundaiAPIError(f"Action status check failed: {e}")

    def _parse_action_status(self, status_response: Any) -> str:
        """
        Parse action status response from API.
        
        Args:
            status_response: Response from check_action_status API call
                           Can be ORDER_STATUS enum, string, or dict
        
        Returns:
            Status string: "SUCCESS", "FAILED", "PENDING", "TIMEOUT", or "UNKNOWN"
        """
        # Handle ORDER_STATUS enum objects (from hyundai_kia_connect_api.ApiImpl)
        # VehicleManager.check_action_status() returns ORDER_STATUS enum members
        if hasattr(status_response, 'name'):
            # It's an enum - use the name directly
            return status_response.name
        
        # Handle string responses
        elif isinstance(status_response, str):
            status_upper = status_response.upper()
            if "SUCCESS" in status_upper or "COMPLETE" in status_upper:
                return "SUCCESS"
            elif "FAIL" in status_upper or "ERROR" in status_upper:
                return "FAILED"
            elif "PENDING" in status_upper or "PROCESSING" in status_upper:
                return "PENDING"
            elif "TIMEOUT" in status_upper:
                return "TIMEOUT"
            else:
                return "UNKNOWN"
        
        # Handle dictionary responses
        elif isinstance(status_response, dict):
            # Try to extract status from dict
            status = status_response.get("status", "").upper()
            if "SUCCESS" in status or "COMPLETE" in status:
                return "SUCCESS"
            elif "FAIL" in status or "ERROR" in status:
                return "FAILED"
            elif "PENDING" in status or "PROCESSING" in status:
                return "PENDING"
            elif "TIMEOUT" in status:
                return "TIMEOUT"
            else:
                return "UNKNOWN"
        else:
            # Unknown response format
            logger.warning(f"Unknown action status response format: {type(status_response)}")
            return "UNKNOWN"
