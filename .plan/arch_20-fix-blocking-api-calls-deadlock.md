# Architecture Plan: Fix Blocking API Calls Deadlock

## Context Analysis

The Hyundai MQTT integration service is experiencing a critical deadlock issue where the service becomes unresponsive after the initial data refresh. The root cause has been identified as **synchronous blocking I/O operations** being called directly within async methods, which blocks the entire event loop and prevents processing of subsequent MQTT messages.

### Problem Details

- **Initial refresh works**: Occurs before the MQTT command loop starts
- **First MQTT command blocks**: Synchronous API call blocks the event loop
- **Service appears frozen**: No further MQTT messages can be processed
- **Affected methods**: Three refresh methods and initialization in `src/hyundai/api_client.py`

### Technical Root Cause

The `hyundai_kia_connect_api` library methods are synchronous:
- `force_refresh_vehicle_state()`
- `update_vehicle_with_cached_state()`
- `check_and_force_update_vehicle()`
- `check_and_refresh_token()`
- `update_all_vehicles_with_cached_state()`

These are called directly from async methods without proper thread pool offloading.

## Technology Recommendations

### **IMPORTANT**: Asyncio Thread Pool Integration

**Primary Solution**: Use `asyncio.to_thread()` for all blocking operations

```python
# Pattern to apply:
await asyncio.to_thread(
    self.vehicle_manager.force_refresh_vehicle_state,
    vehicle_id
)
```

**Why `asyncio.to_thread()` over `loop.run_in_executor()`**:
- **Simpler API**: No need to get the current loop manually
- **Context preservation**: Automatically propagates context variables
- **Modern approach**: Recommended since Python 3.9
- **Error handling**: Cleaner exception propagation
- **Resource management**: Better thread pool lifecycle management

### Alternative: `loop.run_in_executor()`

Consider only if:
- Need custom executor configuration
- Running on Python < 3.9
- Require specific thread pool tuning

```python
# Alternative pattern:
loop = asyncio.get_running_loop()
await loop.run_in_executor(
    None,  # Use default executor
    self.vehicle_manager.force_refresh_vehicle_state,
    vehicle_id
)
```

### Thread Safety Considerations

**VehicleManager Thread Safety**:
- Most `hyundai_kia_connect_api` operations are read-heavy and should be thread-safe
- Monitor for any shared state modifications
- Consider adding locks if race conditions emerge

**Circuit Breaker Thread Safety**:
- Current `CircuitBreaker` implementation appears thread-safe
- Verify atomic operations for failure counting and state transitions

## System Architecture

### Current Architecture (Problematic)

```
MQTT Message → Command Handler → API Client (SYNC) → Event Loop BLOCKED
```

### Target Architecture (Fixed)

```
MQTT Message → Command Handler → API Client (ASYNC) → Thread Pool → Hyundai API
                                                    ↑
                                              Event Loop FREE
```

### Component Integration

**HyundaiAPIClient Modifications**:
1. **Initialization method** (`initialize()`):
   - Wrap `check_and_refresh_token()` in `asyncio.to_thread()`
   - Wrap `update_all_vehicles_with_cached_state()` in `asyncio.to_thread()`

2. **Refresh methods**:
   - `refresh_cached()`: Wrap `update_vehicle_with_cached_state()`
   - `refresh_force()`: Wrap `force_refresh_vehicle_state()`
   - `refresh_smart()`: Wrap `check_and_force_update_vehicle()`

3. **Error handling preservation**:
   - Maintain existing try/catch blocks
   - Ensure circuit breaker functionality intact
   - Preserve logging and diagnostics

## Integration Patterns

### **IMPORTANT**: Non-Blocking Pattern Implementation

```python
async def refresh_force(self, vehicle_id: str) -> VehicleData:
    """Force refresh from vehicle using thread pool."""
    if not self.circuit_breaker.can_execute():
        raise HyundaiAPIError("Circuit breaker is open")

    try:
        logger.info(f"Performing force refresh for vehicle {vehicle_id}")
        logger.debug(f"Offloading force_refresh_vehicle_state to thread pool")

        if not self.vehicle_manager:
            raise HyundaiAPIError("VehicleManager not initialized")

        # CRITICAL: Offload blocking call to thread pool
        await asyncio.to_thread(
            self.vehicle_manager.force_refresh_vehicle_state,
            vehicle_id
        )
        
        vehicle = self.vehicle_manager.get_vehicle(vehicle_id)
        if not vehicle:
            raise RefreshError(f"Vehicle {vehicle_id} not found")

        self.circuit_breaker.record_success()
        return map_vehicle_data(vehicle, "fresh", "force")

    except Exception as e:
        self.circuit_breaker.record_failure()
        logger.error(f"Force refresh failed for vehicle {vehicle_id}: {e}")
        raise RefreshError(f"Force refresh failed: {e}")
```

### Enhanced Logging Pattern

```python
logger.debug(f"Offloading {method_name} to thread pool for vehicle {vehicle_id}")
logger.info(f"Thread pool operation completed for vehicle {vehicle_id}")
```

### Circuit Breaker Integration

The existing circuit breaker pattern remains unchanged:
- **Success/Failure tracking**: Still works correctly
- **State management**: Thread-safe for our use case
- **Threshold enforcement**: Maintained across thread boundaries

## Implementation Guidance

### **IMPORTANT**: Step-by-Step Implementation

1. **Backup current implementation**
2. **Modify `initialize()` method** (lines 103-106):
   ```python
   # Before:
   self.vehicle_manager.check_and_refresh_token()
   self.vehicle_manager.update_all_vehicles_with_cached_state()
   
   # After:
   await asyncio.to_thread(self.vehicle_manager.check_and_refresh_token)
   await asyncio.to_thread(self.vehicle_manager.update_all_vehicles_with_cached_state)
   ```

3. **Modify `refresh_cached()` method** (line 129):
   ```python
   # Before:
   self.vehicle_manager.update_vehicle_with_cached_state(vehicle_id)
   
   # After:
   await asyncio.to_thread(
       self.vehicle_manager.update_vehicle_with_cached_state,
       vehicle_id
   )
   ```

4. **Modify `refresh_force()` method** (line 157):
   ```python
   # Before:
   self.vehicle_manager.force_refresh_vehicle_state(vehicle_id)
   
   # After:
   await asyncio.to_thread(
       self.vehicle_manager.force_refresh_vehicle_state,
       vehicle_id
   )
   ```

5. **Modify `refresh_smart()` method** (line 196):
   ```python
   # Before:
   self.vehicle_manager.check_and_force_update_vehicle(max_age_seconds, vehicle_id)
   
   # After:
   await asyncio.to_thread(
       self.vehicle_manager.check_and_force_update_vehicle,
       max_age_seconds, vehicle_id
   )
   ```

### Testing Strategy

1. **Unit Testing**:
   - Verify each method returns expected data
   - Test error handling and circuit breaker functionality
   - Confirm logging shows thread pool usage

2. **Integration Testing**:
   - Start service and verify initial refresh works
   - Send first MQTT command - should work
   - Send second MQTT command - should work (key test)
   - Send multiple rapid commands - all should process
   - Monitor logs for blocking behavior

3. **Load Testing**:
   - Send 10+ consecutive commands
   - Verify no deadlocks or timeouts
   - Confirm responsive behavior under load

### Performance Considerations

**Thread Pool Sizing**:
- Default `ThreadPoolExecutor` typically uses `min(32, os.cpu_count() + 4)`
- Monitor for thread pool exhaustion under heavy load
- Consider custom executor if needed

**Memory Usage**:
- Thread pool adds minimal overhead
- Monitor for memory leaks in long-running operations

**Response Time**:
- Slight increase due to thread switching overhead
- Trade-off: Non-responsive vs. slightly slower but responsive

### Monitoring and Observability

**Enhanced Logging**:
```python
logger.debug(f"Thread pool operation started: {method_name}")
logger.info(f"Thread pool operation completed: {method_name} in {duration:.2f}s")
```

**Metrics to Track**:
- Thread pool queue depth
- Operation completion times
- Circuit breaker state changes
- Event loop responsiveness

### Rollback Strategy

If issues arise:
1. **Immediate rollback**: Remove `asyncio.to_thread()` wrappers
2. **Alternative approach**: Use `loop.run_in_executor()` with custom executor
3. **Fallback**: Implement request queuing with semaphore limiting

## Critical Success Factors

### **IMPORTANT**: Must-Have Requirements

1. **Event Loop Never Blocks**: All I/O operations must be offloaded
2. **Backwards Compatibility**: All existing functionality preserved
3. **Error Handling**: Circuit breaker and exception handling intact
4. **Thread Safety**: VehicleManager operations safe in thread pool
5. **Performance**: Service remains responsive under load
6. **Observability**: Enhanced logging for debugging

### Risk Mitigation

**High-Risk Areas**:
- VehicleManager thread safety (monitor closely)
- Circuit breaker state consistency
- Exception propagation across thread boundaries

**Mitigation Strategies**:
- Comprehensive testing before production deployment
- Enhanced monitoring and alerting
- Quick rollback capability
- Gradual rollout with feature flags

### Success Metrics

**Functional Success**:
- ✅ Initial data refresh works
- ✅ MQTT commands trigger successful refreshes
- ✅ Service remains responsive to multiple commands
- ✅ Event loop never blocked by synchronous I/O
- ✅ All existing functionality continues working

**Performance Success**:
- ✅ Multiple concurrent commands processed without deadlock
- ✅ Response times remain acceptable
- ✅ No memory leaks or resource exhaustion
- ✅ Thread pool utilization within expected bounds

This architectural plan provides a comprehensive approach to resolving the blocking API calls deadlock while maintaining system reliability and performance. The use of `asyncio.to_thread()` represents the modern, recommended approach for integrating synchronous operations into async applications.