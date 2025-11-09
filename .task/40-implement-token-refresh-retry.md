# Task: 40 - Implement Token Refresh and Retry Mechanism

## Problem Statement
The current Hyundai MQTT integration has a critical authentication issue: when the API token expires during normal operation, all subsequent commands fail with "Token is expired" error and there is no automatic token refresh mechanism. The token is only refreshed once during service initialization, leading to permanent command failures until service restart.

### User Feedback
User reported the specific error:
```json
{"timestamp": "2025-11-08T10:51:35.891478Z", "level": "ERROR", "message": "Force refresh failed for vehicle fb9ccccc-11111111-1111-1111-1111-111111111111: Key not authorized: Token is expired", "module": "api_client", "function": "refresh_force"}
{"timestamp": "2025-11-08T10:51:35.891536Z", "level": "ERROR", "message": "Command execution failed for vehicle fb9ccccc-11111111-1111-1111-1111-111111111111: Force refresh failed: Key not authorized: Token is expired", "module": "handler", "function": "handle_command"}
```

User specifically requested: *"I think we should refresh auth when we have this error and retry the request after refresh, isn't it?"*

## Requirements

### 1. Token Expiration Detection
- Detect "Token is expired" errors in all API client methods
- Handle variations of token expiration messages from the API
- Distinguish token expiration from other authentication errors

### 2. Automatic Token Refresh
- Implement automatic token refresh when expiration is detected
- Use `vehicle_manager.check_and_refresh_token()` for refresh
- Add concurrency protection to prevent multiple simultaneous refresh attempts
- Handle refresh failures gracefully

### 3. Request Retry Mechanism
- Automatically retry the original request after successful token refresh
- Implement single retry (no infinite retry loops)
- Maintain all existing error handling for non-token failures
- Preserve original request context and logging

### 4. Concurrency Protection
- Use `asyncio.Lock` to prevent multiple simultaneous refresh attempts
- Track refresh state to avoid redundant operations
- Handle race conditions when multiple threads detect token expiration simultaneously

### 5. Comprehensive Coverage
- Apply token refresh logic to all API client methods:
  - `refresh_cached()`, `refresh_force()`, `refresh_smart()`
  - All control commands: `lock_vehicle()`, `unlock_vehicle()`, `start_climate()`, `stop_climate()`
  - `set_windows_state()`, `open_charge_port()`, `close_charge_port()`, `set_charging_current()`
  - `check_action_status()`

## Expected Outcome

### Deliverables
1. **Enhanced `HyundaiAPIClient`** with token refresh and retry:
   - `_is_token_expired_error()` method to detect token expiration
   - `_refresh_token_safely()` method with concurrency protection
   - `_execute_with_retry()` wrapper method for all API calls
   - Updated all existing methods to use retry mechanism

2. **Robust Error Handling**:
   - Token expiration detection and automatic recovery
   - Proper error propagation for non-token failures
   - Detailed logging for token refresh operations
   - Circuit breaker integration with token refresh

3. **Thread Safety**:
   - Asyncio lock for token refresh coordination
   - State tracking for refresh operations
   - Race condition prevention

### Success Criteria
- ✅ Token expiration errors are automatically detected
- ✅ Token is refreshed automatically when expired
- ✅ Original requests are retried after successful refresh
- ✅ No multiple simultaneous refresh attempts
- ✅ All existing functionality preserved for non-token errors
- ✅ Proper logging and error handling throughout
- ✅ Circuit breaker continues to work with token refresh
- ✅ No performance degradation for normal operations

## Implementation Components

### 1. Token Refresh Detection (`src/hyundai/api_client.py`)
```python
def _is_token_expired_error(self, error: Exception) -> bool:
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
        
        logger.info("Refreshing expired token")
        await asyncio.to_thread(self.vehicle_manager.check_and_refresh_token)
        self._last_refresh_time = datetime.utcnow()
        logger.info("Token refresh completed successfully")
```

### 2. Retry Wrapper Method
```python
async def _execute_with_retry(self, operation: Callable, *args, **kwargs) -> Any:
    """Execute operation with token refresh and retry logic."""
    try:
        return await operation(*args, **kwargs)
    except Exception as e:
        if self._is_token_expired_error(e):
            logger.warning(f"Token expired detected, attempting refresh: {e}")
            await self._refresh_token_safely()
            logger.info("Retrying operation after token refresh")
            return await operation(*args, **kwargs)
        else:
            # Re-raise non-token errors
            raise
```

### 3. Updated Method Examples
```python
async def refresh_force(self, vehicle_id: str) -> VehicleData:
    """Force refresh with token retry."""
    if not self.circuit_breaker.can_execute():
        raise HyundaiAPIError("Circuit breaker is open")
    
    try:
        async def _operation():
            logger.debug(f"Forcing refresh of vehicle {vehicle_id}")
            await asyncio.to_thread(self.vehicle_manager.force_refresh_vehicle_state, vehicle_id)
            vehicle = self.vehicle_manager.get_vehicle(vehicle_id)
            if not vehicle:
                raise RefreshError(f"Vehicle {vehicle_id} not found")
            return map_vehicle_data(vehicle, "fresh", "force")
        
        result = await self._execute_with_retry(_operation)
        self.circuit_breaker.record_success()
        return result
        
    except Exception as e:
        self.circuit_breaker.record_failure()
        logger.error(f"Force refresh failed for vehicle {vehicle_id}: {e}")
        raise RefreshError(f"Force refresh failed: {e}")
```

### 4. Constructor Updates
```python
def __init__(self, config: HyundaiConfig) -> None:
    self.config: HyundaiConfig = config
    self.vehicle_manager: Optional[VehicleManager] = None
    self.circuit_breaker: CircuitBreaker = CircuitBreaker()
    self._token_refresh_lock: asyncio.Lock = asyncio.Lock()
    self._last_refresh_time: Optional[datetime] = None
```

## Other Important Agreements

### Architectural Decisions
- **Single Retry Pattern**: Only retry once after token refresh to avoid infinite loops
- **Non-Intrusive Design**: Token refresh logic should not change existing method signatures
- **Preserve Existing Error Handling**: All non-token errors should behave exactly as before
- **Circuit Breaker Integration**: Token refresh should work seamlessly with existing circuit breaker
- **Async Safety**: Use asyncio.Lock for thread safety in async context

### Error Handling Strategy
- **Token Expiration**: Automatic refresh + retry + success
- **Refresh Failure**: Propagate as authentication error
- **Other Errors**: Existing error handling unchanged
- **Concurrent Detection**: Lock prevents multiple refresh attempts

### Logging Requirements
- Log token expiration detection at WARNING level
- Log token refresh operations at INFO level
- Log retry attempts at INFO level
- Maintain existing error logging for all other cases

### Performance Considerations
- Minimal overhead for normal operations (no token expiration)
- Lock contention only during token refresh (rare event)
- No additional API calls for token expiration detection
- Preserve existing circuit breaker behavior

## Dependencies to Add
- No new dependencies required
- Uses existing `asyncio` and `datetime` modules
- Leverages existing `vehicle_manager.check_and_refresh_token()` method

## Files to Modify
1. **Modify**: `src/hyundai/api_client.py` - Add token refresh and retry mechanism to all methods

## Additional Context
This implementation addresses a critical production issue where the service becomes unusable after token expiration. The solution builds upon the existing foundation:

- Task 10: Initial MQTT integration ✅
- Task 20: Fixed async blocking issues ✅  
- Task 30: Added vehicle control with confirmations ✅
- Task 40: Now adding robust token refresh and retry mechanism

The approach is conservative and focused: detect token expiration, refresh safely, retry once, and preserve all existing behavior for other error cases. This ensures the service remains operational without requiring manual restarts when tokens expire during normal usage.