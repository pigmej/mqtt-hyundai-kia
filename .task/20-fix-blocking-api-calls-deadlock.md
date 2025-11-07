# Task: 20 - Fix Blocking API Calls Deadlock

## Problem Statement
The Hyundai MQTT integration service experiences a deadlock after the initial data refresh. MQTT refresh commands work once (during startup) but then the service becomes unresponsive. Investigation revealed that the `hyundai_kia_connect_api` library methods (`force_refresh_vehicle_state()`, `update_vehicle_with_cached_state()`, `check_and_force_update_vehicle()`) are **synchronous blocking calls** being executed directly in async methods, which blocks the entire event loop and prevents processing of subsequent MQTT messages.

### Root Cause
The async refresh methods in `src/hyundai/api_client.py` call synchronous blocking I/O operations without wrapping them in `asyncio.to_thread()` or `loop.run_in_executor()`. This causes:
1. Initial refresh works (runs before command loop starts)
2. First MQTT command blocks the event loop
3. Service appears frozen/unresponsive
4. No further MQTT messages can be processed

### User Feedback
User reported: "I think something is completely broken with MQTT logic, it's clearly visible that it works only once and then we're in a deadloop. The initial refresh is the only thing that works. It's clearly stuck on the refresh loop for some reason."

## Requirements
1. **Wrap all synchronous Hyundai API calls** in `asyncio.to_thread()` to run them in a thread pool
2. **Fix three refresh methods** in `src/hyundai/api_client.py`:
   - `refresh_cached()` (line 129: `update_vehicle_with_cached_state()`)
   - `refresh_force()` (line 157: `force_refresh_vehicle_state()`)
   - `refresh_smart()` (line 196: `check_and_force_update_vehicle()`)
3. **Fix initialization method** (line 103-106: `check_and_refresh_token()` and `update_all_vehicles_with_cached_state()`)
4. **Maintain error handling** - ensure circuit breaker and error catching still work correctly
5. **Add logging** to track when operations are offloaded to threads
6. **Test thoroughly** to ensure no other blocking calls exist

## Expected Outcome
After the fix:
1. ✅ Initial data refresh works
2. ✅ MQTT commands trigger successful refreshes
3. ✅ Service remains responsive to multiple MQTT commands
4. ✅ Event loop is never blocked by synchronous I/O
5. ✅ All existing functionality (circuit breaker, error handling, logging) continues to work
6. ✅ Multiple concurrent commands can be processed without deadlock

## Technical Implementation Plan

### Pattern to Apply
```python
# BEFORE (BLOCKING):
self.vehicle_manager.force_refresh_vehicle_state(vehicle_id)

# AFTER (NON-BLOCKING):
await asyncio.to_thread(
    self.vehicle_manager.force_refresh_vehicle_state,
    vehicle_id
)
```

### Files to Modify
1. **`src/hyundai/api_client.py`** - All methods calling VehicleManager:
   - `initialize()` - lines 103, 106
   - `refresh_cached()` - line 129
   - `refresh_force()` - line 157
   - `refresh_smart()` - line 196
   - `get_vehicle_ids()` - if it calls any VehicleManager methods

### Testing Steps
1. Start the service with enhanced logging
2. Verify initial data refresh works
3. Send first MQTT refresh command - should work
4. Send second MQTT refresh command - should work (this currently fails)
5. Send multiple rapid commands - all should be queued and processed
6. Monitor logs for any blocking behavior
7. Verify data is correctly published after each refresh

## Other Important Agreements
- **Event loop must never be blocked**: All I/O operations must be either async-native or wrapped in thread pool executors
- **Preserve existing architecture**: Don't restructure the command handler, MQTT client, or other components
- **Maintain backwards compatibility**: All existing features and error handling must continue working
- **Thread safety**: Ensure VehicleManager methods are thread-safe when called from thread pool (they should be, but verify)
- **Enhanced logging remains**: Keep all the diagnostic logging added in previous debugging sessions

## Verification Criteria
- [ ] Service starts successfully
- [ ] Initial data refresh publishes to MQTT
- [ ] First MQTT command triggers refresh and publishes data
- [ ] Second MQTT command triggers refresh and publishes data
- [ ] Ten consecutive MQTT commands all succeed
- [ ] Service logs show "Command executed successfully" for each command
- [ ] No "blocking" or "timeout" warnings in logs
- [ ] Circuit breaker continues to function correctly
- [ ] Error handling still catches and reports API failures

## Additional Context
This issue was discovered after extensive debugging that included:
1. Enhanced logging throughout MQTT and command handling code
2. Comprehensive test suite showing isolated components work correctly
3. Discovery that `future.result(timeout=0.1)` was causing silent failures
4. Final realization that the core issue is synchronous blocking I/O in async context

The synchronous nature of `hyundai_kia_connect_api` methods was confirmed via:
```python
inspect.iscoroutinefunction(VehicleManager.force_refresh_vehicle_state)  # Returns False
```