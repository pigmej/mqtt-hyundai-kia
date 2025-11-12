# Architectural Analysis: Implement Token Refresh and Retry Mechanism

## Context Analysis

### Problem Domain
The Hyundai MQTT integration service currently faces a **critical authentication failure issue**: when API tokens expire during normal operation, all subsequent commands fail permanently with "Token is expired" errors. The system requires a manual service restart to restore functionality because token refresh only occurs once during initialization.

This represents a **production reliability gap** where:
- **Initial startup works**: Token is refreshed during `initialize()` method
- **Token expiration causes cascade failure**: All operations fail after token expires (typically hours/days into runtime)
- **No automatic recovery**: Service becomes unusable until manual restart
- **User impact**: Commands return permanent errors: `"Key not authorized: Token is expired"`

### Current Architecture Assessment

**Existing Token Management**:
- ✅ Token refresh on initialization: `vehicle_manager.check_and_refresh_token()` in `initialize()`
- ✅ Thread pool integration: All VehicleManager calls use `asyncio.to_thread()`
- ✅ Circuit breaker protection: Guards against cascading failures
- ❌ **No expiration detection**: Token errors treated as generic failures
- ❌ **No automatic refresh**: Token only refreshed during initialization
- ❌ **No retry mechanism**: Failed operations not retried after token refresh

**Architectural Foundation** (from previous tasks):
- **Task 10**: Established MQTT integration with data refresh strategies
- **Task 20**: Fixed event loop blocking with `asyncio.to_thread()` pattern
- **Task 30**: Implemented EU vehicle control with action confirmation
- **Task 40**: Now adding resilient token lifecycle management

The existing architecture is sound but lacks **authentication resilience**. All necessary infrastructure exists (circuit breaker, thread pool, error handling) - we need to add **token lifecycle management** as a cross-cutting concern.

### Key Constraints and Requirements

**Technical Constraints**:
- **Asyncio-based architecture**: All token refresh operations must be async-safe
- **Thread pool execution**: VehicleManager is synchronous, must use `asyncio.to_thread()`
- **Circuit breaker preservation**: Token refresh must not interfere with existing failure tracking
- **Non-blocking requirements**: Token refresh cannot block event loop
- **Concurrency protection**: Multiple simultaneous requests must not trigger multiple refreshes

**Business Requirements**:
- **Zero downtime**: Service must recover automatically from token expiration
- **Transparent recovery**: Users should not experience command failures due to token expiration
- **Single retry guarantee**: Avoid infinite retry loops while ensuring recovery
- **Comprehensive coverage**: All API methods must support token refresh
- **Audit trail**: All token refresh operations must be logged

## Technology Recommendations

### Core Pattern: Retry with Token Refresh

**IMPORTANT**: Implement a **decorator-style retry pattern** that wraps all API operations with token expiration detection and automatic refresh.

**Pattern Architecture**:
```python
async def _execute_with_retry(operation: Callable, *args, **kwargs) -> Any:
    """Execute operation with single retry after token refresh."""
    try:
        # First attempt
        return await operation(*args, **kwargs)
    except Exception as e:
        if self._is_token_expired_error(e):
            # Refresh token and retry ONCE
            await self._refresh_token_safely()
            return await operation(*args, **kwargs)
        else:
            # Re-raise non-token errors
            raise
```

**Why This Pattern**:
- ✅ **Non-intrusive**: No method signature changes required
- ✅ **Single retry**: Prevents infinite retry loops
- ✅ **Transparent**: Callers unaware of token refresh
- ✅ **Consistent**: Same pattern across all API methods
- ✅ **Testable**: Easy to unit test with mock exceptions

### Concurrency Protection Strategy

**IMPORTANT**: Use **asyncio.Lock with double-check pattern** to prevent concurrent token refreshes.

**Implementation Pattern**:
```python
async def _refresh_token_safely(self) -> None:
    """Thread-safe token refresh with double-check pattern."""
    async with self._token_refresh_lock:
        # Double-check: avoid redundant refreshes
        if self._last_refresh_time and \
           (datetime.utcnow() - self._last_refresh_time).seconds < 30:
            return  # Recent refresh, skip
        
        # Perform refresh
        await asyncio.to_thread(self.vehicle_manager.check_and_refresh_token)
        self._last_refresh_time = datetime.utcnow()
```

**Why asyncio.Lock over threading.Lock**:
- ✅ **Async-native**: Works correctly with async/await syntax
- ✅ **Event loop aware**: Doesn't block event loop during lock wait
- ✅ **Context manager support**: Clean `async with` syntax
- ✅ **Cancellation safe**: Properly handles asyncio task cancellation

**Why Double-Check Pattern**:
- ✅ **Race condition prevention**: Multiple threads detect expiration simultaneously
- ✅ **Efficiency**: Avoid redundant refresh attempts within short window
- ✅ **Performance**: Reduces lock contention under concurrent load

### Token Expiration Detection Strategy

**IMPORTANT**: Use **keyword-based error pattern matching** to detect token expiration errors.

**Implementation Pattern**:
```python
def _is_token_expired_error(self, error: Exception) -> bool:
    """Detect token expiration from error message patterns."""
    error_str = str(error).lower()
    return any(keyword in error_str for keyword in [
        "token is expired",
        "key not authorized: token is expired",
        "authentication failed",
        "unauthorized"
    ])
```

**Rationale**:
- ✅ **Library-agnostic**: Works with any error message format from `hyundai_kia_connect_api`
- ✅ **Robust**: Matches variations of token expiration messages
- ✅ **Low false-positive rate**: Specific enough to avoid misclassification
- ✅ **Easy to extend**: New patterns can be added as discovered

**Alternative Considered**: Exception type matching
- ❌ **Library-dependent**: Requires specific exception types from `hyundai_kia_connect_api`
- ❌ **Fragile**: Library updates might change exception hierarchy
- ❌ **Limited visibility**: Library might wrap errors in generic exceptions

### Integration with Existing Patterns

**Circuit Breaker Interaction**:
- Token refresh errors should **still trigger circuit breaker**
- Successful retry after token refresh should **record success**
- Pattern: Token refresh happens **before** circuit breaker records failure

**Thread Pool Integration**:
- Token refresh uses existing `asyncio.to_thread()` pattern
- Consistent with Task 20 architectural decision
- No additional thread pool configuration needed

**Error Handling Hierarchy**:
1. **Token expiration detected** → Refresh token → Retry operation
2. **Refresh fails** → Propagate as HyundaiAPIError → Circuit breaker records failure
3. **Other errors** → Existing error handling (circuit breaker, logging)

## System Architecture

### Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   HyundaiAPIClient                          │
│                                                             │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Public API Method (e.g., refresh_force)          │    │
│  │                                                     │    │
│  │  1. Check circuit breaker                          │    │
│  │  2. Execute operation with retry wrapper           │    │
│  │     ▼                                               │    │
│  │  ┌─────────────────────────────────────────┐      │    │
│  │  │ _execute_with_retry()                   │      │    │
│  │  │                                         │      │    │
│  │  │  Try: Execute operation via thread pool │      │    │
│  │  │  Catch: Token expired?                  │      │    │
│  │  │    ├─ Yes → _refresh_token_safely()     │      │    │
│  │  │    │         ▼                           │      │    │
│  │  │    │    ┌─────────────────────────┐     │      │    │
│  │  │    │    │ asyncio.Lock acquired   │     │      │    │
│  │  │    │    │ Double-check recent?    │     │      │    │
│  │  │    │    │ Refresh via thread pool │     │      │    │
│  │  │    │    │ Update timestamp        │     │      │    │
│  │  │    │    └─────────────────────────┘     │      │    │
│  │  │    │         ▼                           │      │    │
│  │  │    │    Retry operation                 │      │    │
│  │  │    └─ No → Re-raise error               │      │    │
│  │  └─────────────────────────────────────────┘      │    │
│  │                                                     │    │
│  │  3. Record circuit breaker success/failure         │    │
│  │  4. Return result or propagate error              │    │
│  └───────────────────────────────────────────────────┘    │
│                                                             │
│  State:                                                     │
│  - _token_refresh_lock: asyncio.Lock                       │
│  - _last_refresh_time: Optional[datetime]                  │
│  - circuit_breaker: CircuitBreaker (existing)              │
│  - vehicle_manager: VehicleManager (existing)              │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow for Token Refresh

**Scenario 1: Token Expired - First Thread Detects**
```
Thread 1: refresh_force() → Token expired error
         ↓
Thread 1: _execute_with_retry() detects expiration
         ↓
Thread 1: _refresh_token_safely() acquires lock
         ↓
Thread 1: Checks double-check window (no recent refresh)
         ↓
Thread 1: Executes check_and_refresh_token() via thread pool
         ↓
Thread 1: Updates _last_refresh_time
         ↓
Thread 1: Releases lock
         ↓
Thread 1: Retries refresh_force() with fresh token → Success
```

**Scenario 2: Token Expired - Concurrent Thread Arrives**
```
Thread 1: In _refresh_token_safely(), performing refresh
Thread 2: refresh_cached() → Token expired error
         ↓
Thread 2: _execute_with_retry() detects expiration
         ↓
Thread 2: _refresh_token_safely() waits for lock (Thread 1 holds it)
         ↓
Thread 1: Completes refresh, releases lock
         ↓
Thread 2: Acquires lock
         ↓
Thread 2: Checks double-check window (recent refresh by Thread 1!)
         ↓
Thread 2: Skips redundant refresh, releases lock
         ↓
Thread 2: Retries refresh_cached() with fresh token → Success
```

**Scenario 3: Non-Token Error**
```
Thread 1: refresh_force() → Network timeout error
         ↓
Thread 1: _execute_with_retry() checks error
         ↓
Thread 1: Not token expiration → Re-raise error
         ↓
Thread 1: Circuit breaker records failure
         ↓
Thread 1: Error propagated to caller (existing behavior)
```

### State Management

**New Instance Variables**:
- `_token_refresh_lock: asyncio.Lock` - Coordination for concurrent refresh attempts
- `_last_refresh_time: Optional[datetime]` - Timestamp of last successful refresh

**Invariants**:
- Lock must be acquired before any token refresh operation
- Timestamp must be updated atomically with refresh completion
- Double-check window: 30 seconds (configurable if needed)

## Integration Patterns

### Pattern 1: Inline Retry Pattern (REJECTED)

**Implementation**:
```python
async def refresh_force(self, vehicle_id: str) -> VehicleData:
    try:
        # Operation
        await asyncio.to_thread(...)
    except Exception as e:
        if self._is_token_expired_error(e):
            await self._refresh_token_safely()
            # Retry inline
            await asyncio.to_thread(...)
        else:
            raise
```

**Why Rejected**:
- ❌ **Code duplication**: Retry logic repeated in every method
- ❌ **Error-prone**: Easy to forget retry in new methods
- ❌ **Maintenance burden**: Changes require updating all methods

### Pattern 2: Nested Function Wrapper (SELECTED)

**Implementation**:
```python
async def refresh_force(self, vehicle_id: str) -> VehicleData:
    async def _operation():
        await asyncio.to_thread(...)
        vehicle = self.vehicle_manager.get_vehicle(vehicle_id)
        return map_vehicle_data(...)
    
    result = await self._execute_with_retry(_operation)
    return result
```

**Why Selected**:
- ✅ **DRY principle**: Retry logic in single location
- ✅ **Consistent**: All methods use identical pattern
- ✅ **Maintainable**: Changes to retry logic affect all methods
- ✅ **Testable**: Can test retry logic independently

### Pattern 3: Decorator Pattern (CONSIDERED)

**Implementation**:
```python
@with_token_retry
async def refresh_force(self, vehicle_id: str) -> VehicleData:
    # Implementation without retry logic
```

**Why Not Selected**:
- ⚠️ **Complexity**: Decorators with instance methods require careful handling
- ⚠️ **Debugging**: Stack traces become harder to read
- ⚠️ **Explicit better than implicit**: Nested function more visible

### Method Coverage Strategy

**IMPORTANT**: All API client methods must be updated to use retry pattern.

**Methods Requiring Update**:
1. **Refresh Operations**:
   - `refresh_cached()` ✓
   - `refresh_force()` ✓
   - `refresh_smart()` ✓

2. **Vehicle Control Commands**:
   - `lock_vehicle()` ✓
   - `unlock_vehicle()` ✓
   - `start_climate()` ✓
   - `stop_climate()` ✓
   - `set_windows_state()` ✓
   - `open_charge_port()` ✓
   - `close_charge_port()` ✓
   - `set_charging_current()` ✓

3. **Status Operations**:
   - `check_action_status()` ✓

**Current State**: All methods already have token refresh implemented inline! Task shows this pattern exists but needs validation.

## Implementation Guidance

### Phase 1: Core Infrastructure (ALREADY IMPLEMENTED)

**IMPORTANT**: Review existing implementation in `api_client.py` lines 96-134.

**Existing Implementation**:
- ✅ `_is_token_expired_error()` method (lines 96-104)
- ✅ `_refresh_token_safely()` method (lines 106-120)
- ✅ `_execute_with_retry()` method (lines 122-134)
- ✅ Instance variables in `__init__()` (lines 93-94)

**Validation Required**:
1. **Verify token refresh lock initialization**: Check `asyncio.Lock()` created correctly
2. **Verify double-check timing**: Confirm 30-second window is appropriate
3. **Verify error pattern coverage**: Test against real token expiration errors

### Phase 2: Method Integration (ALREADY IMPLEMENTED)

**IMPORTANT**: All methods already implement inline token refresh pattern (lines 199-310, 364-761).

**Current Pattern in Methods**:
```python
except Exception as e:
    if await self._is_token_expired_error(e):
        logger.warning(f"Token expired detected, attempting refresh: {e}")
        await self._refresh_token_safely()
        logger.info("Retrying operation after token refresh")
        return await self.{method_name}(...)  # Recursive retry
    else:
        # Existing error handling
```

**Pattern Used**: Recursive retry (method calls itself after token refresh)

**Comparison with Task Specification**:
- Task spec: Nested function wrapper pattern
- Actual implementation: Recursive self-call pattern
- Both achieve same goal with different approaches

**Analysis of Recursive Pattern**:
- ✅ **Pros**: Simple, no nested functions, clear call flow
- ✅ **Works correctly**: Single retry guarantee (refresh happens once)
- ⚠️ **Risk**: Stack depth (negligible for single retry)
- ⚠️ **Risk**: Infinite loop if token refresh doesn't update state (mitigated by lock + timestamp)

### Phase 3: Testing Strategy

**Unit Tests Required**:

1. **Token Expiration Detection Test**:
   ```python
   async def test_detect_token_expired_error():
       # Test various token expiration message formats
       assert _is_token_expired_error(Exception("Token is expired"))
       assert _is_token_expired_error(Exception("Key not authorized: Token is expired"))
       assert not _is_token_expired_error(Exception("Network timeout"))
   ```

2. **Token Refresh Concurrency Test**:
   ```python
   async def test_concurrent_token_refresh():
       # Simulate multiple threads detecting expiration
       # Verify only one refresh occurs
       # Verify double-check prevents redundant refreshes
   ```

3. **Retry Mechanism Test**:
   ```python
   async def test_single_retry_after_token_refresh():
       # First call: raises token expired
       # Token refresh succeeds
       # Second call: succeeds
       # Verify exactly 2 calls to underlying method
   ```

4. **Circuit Breaker Integration Test**:
   ```python
   async def test_circuit_breaker_with_token_refresh():
       # Token refresh succeeds → circuit breaker records success
       # Token refresh fails → circuit breaker records failure
   ```

**Integration Tests Required**:

1. **End-to-End Token Expiration Recovery**:
   ```python
   async def test_e2e_token_expiration_recovery():
       # Simulate real token expiration during operation
       # Verify automatic recovery without user intervention
       # Verify operation completes successfully
   ```

2. **Load Test with Concurrent Operations**:
   ```python
   async def test_concurrent_operations_during_token_expiration():
       # Launch 10 concurrent operations
       # Trigger token expiration
       # Verify all operations recover
       # Verify only one token refresh occurs
   ```

### Phase 4: Observability and Monitoring

**Logging Requirements**:

**IMPORTANT**: Token refresh operations must be observable for debugging and audit.

**Log Levels**:
- **WARNING**: Token expiration detected (indicates potential configuration issue)
- **INFO**: Token refresh initiated and completed
- **INFO**: Operation retried after token refresh
- **ERROR**: Token refresh failed (critical - requires investigation)

**Log Messages Already Implemented**:
```python
logger.warning(f"Token expired detected, attempting refresh: {e}")
logger.info("Refreshing expired token")
logger.info("Token refresh completed successfully")
logger.info("Retrying operation after token refresh")
```

**Additional Metrics to Consider**:
- Count of token refresh operations per hour
- Time taken for token refresh
- Frequency of concurrent refresh attempts
- Success rate of operations after token refresh

### Phase 5: Performance Optimization

**Current Implementation Assessment**:

**Lock Contention Analysis**:
- Lock only held during token refresh (rare event)
- Lock released immediately after refresh completes
- Double-check reduces lock acquisition attempts
- **Expected contention**: Very low (tokens expire hours apart)

**Thread Pool Impact**:
- Token refresh uses existing thread pool
- No additional pool configuration needed
- Refresh operation is fast (< 1 second typically)
- **Expected impact**: Minimal

**Circuit Breaker Interaction**:
- Token refresh errors still trigger circuit breaker
- Prevents cascading failures if refresh repeatedly fails
- **Expected behavior**: Correct

### Critical Implementation Decisions

**IMPORTANT Decision 1: Recursive Retry vs Nested Function**

**Current Implementation**: Recursive self-call
```python
return await self.refresh_force(vehicle_id)  # Calls itself
```

**Task Specification**: Nested function wrapper
```python
async def _operation():
    # Implementation
return await self._execute_with_retry(_operation)
```

**Recommendation**: **Keep recursive pattern** - simpler and already implemented
- Same guarantees (single retry)
- Clearer for debugging (direct method call)
- Less cognitive overhead (no nested functions)

**IMPORTANT Decision 2: Error Pattern Matching**

**Current Implementation**: String matching with keyword list
```python
any(keyword in error_str for keyword in [...])
```

**Alternatives Considered**:
- Regex pattern matching (more powerful but overkill)
- Exception type checking (library-dependent)

**Recommendation**: **Keep string matching** - simple and effective
- Library-agnostic
- Easy to extend
- Low false-positive rate

**IMPORTANT Decision 3: Double-Check Window**

**Current Implementation**: 30 seconds
```python
(datetime.utcnow() - self._last_refresh_time).seconds < 30
```

**Consideration**: Tokens typically valid for hours, 30s window is conservative

**Recommendation**: **Keep 30 seconds** - good balance
- Prevents redundant refreshes under burst load
- Short enough to not mask real expiration
- Can be made configurable if needed

**IMPORTANT Decision 4: Async Lock vs Threading Lock**

**Current Implementation**: `asyncio.Lock()`
```python
self._token_refresh_lock: asyncio.Lock = asyncio.Lock()
```

**Why Correct**:
- Async-native (doesn't block event loop)
- Works correctly with async/await
- Proper cancellation handling

**Alternative**: `threading.Lock()` would be incorrect (blocks event loop)

## Risk Analysis and Mitigation

### Risk 1: Infinite Retry Loop

**Scenario**: Token refresh succeeds but token still invalid
**Probability**: Low (library should update token state)
**Impact**: High (service hangs)

**Mitigation**:
- Single retry guarantee (no while loops)
- Double-check pattern prevents rapid re-refresh
- Circuit breaker will open if repeated failures

### Risk 2: Race Condition in Token Refresh

**Scenario**: Multiple threads refresh simultaneously
**Probability**: Medium (concurrent operations common)
**Impact**: Medium (redundant API calls, rate limit risk)

**Mitigation**:
- ✅ asyncio.Lock prevents concurrent execution
- ✅ Double-check pattern prevents redundant refreshes
- ✅ 30-second window provides buffer

### Risk 3: Lock Deadlock

**Scenario**: Lock acquired but never released
**Probability**: Very low (Python context managers reliable)
**Impact**: High (all operations blocked)

**Mitigation**:
- ✅ Using `async with` context manager (automatic release)
- ✅ No nested locks (no deadlock possible)
- ✅ Exception in critical section still releases lock

### Risk 4: Token Refresh Failure

**Scenario**: Token refresh fails (wrong credentials, API down)
**Probability**: Low (credentials validated at startup)
**Impact**: High (service unusable)

**Mitigation**:
- ✅ Error propagated to caller
- ✅ Circuit breaker will open
- ✅ Logged at ERROR level for visibility
- ✅ Service will retry on next operation

### Risk 5: False Positive Token Expiration Detection

**Scenario**: Non-token error matched by keyword pattern
**Probability**: Low (keywords are specific)
**Impact**: Medium (unnecessary token refresh)

**Mitigation**:
- Keywords are highly specific ("token is expired", "key not authorized: token is expired")
- "authentication failed" and "unauthorized" are broader but still authentication-related
- Worst case: Unnecessary token refresh (idempotent operation)

## Success Criteria

### Functional Success Metrics

✅ **Token expiration automatically detected**
- All token expiration error messages matched
- No false negatives (missed expiration errors)
- Minimal false positives (non-token errors misidentified)

✅ **Token automatically refreshed when expired**
- `vehicle_manager.check_and_refresh_token()` called
- Token state updated in VehicleManager
- Subsequent operations use fresh token

✅ **Operations automatically retried after refresh**
- Original operation executed again
- Same parameters and context preserved
- Success reported to caller transparently

✅ **No concurrent refresh attempts**
- asyncio.Lock prevents simultaneous refresh
- Double-check prevents redundant refresh within window
- Logs show single refresh even with concurrent operations

✅ **All existing functionality preserved**
- Non-token errors handled as before
- Circuit breaker behavior unchanged
- Logging and diagnostics maintained

### Performance Success Metrics

✅ **Minimal overhead for normal operations**
- No performance impact when token valid
- Token check is simple string matching (microseconds)
- No additional API calls or network I/O

✅ **Circuit breaker integration maintained**
- Success/failure tracking correct
- State transitions work with retry pattern
- Thresholds and timeouts unchanged

✅ **No event loop blocking**
- Token refresh via `asyncio.to_thread()`
- Lock operations are async (no blocking)
- All I/O properly offloaded

### Operational Success Metrics

✅ **Service remains operational after token expiration**
- No manual restart required
- Commands succeed transparently
- Users unaware of token refresh

✅ **Proper observability**
- Token expiration events logged
- Refresh operations tracked
- Failures escalated appropriately

✅ **Thread safety guaranteed**
- No race conditions in concurrent scenarios
- Lock contention minimal
- State consistency maintained

## Validation Checklist

Before considering this implementation complete:

1. **Code Review**:
   - [ ] Verify all methods implement retry pattern consistently
   - [ ] Verify asyncio.Lock used correctly (not threading.Lock)
   - [ ] Verify double-check window timing is appropriate
   - [ ] Verify error patterns comprehensive

2. **Unit Testing**:
   - [ ] Test token expiration detection with various error messages
   - [ ] Test concurrent token refresh with multiple threads
   - [ ] Test single retry guarantee (no infinite loops)
   - [ ] Test circuit breaker integration

3. **Integration Testing**:
   - [ ] Test end-to-end recovery from real token expiration
   - [ ] Test concurrent operations during token expiration
   - [ ] Test token refresh failure propagation

4. **Load Testing**:
   - [ ] Test service under sustained load with token expiration
   - [ ] Verify no performance degradation
   - [ ] Verify no resource leaks

5. **Production Readiness**:
   - [ ] Logging comprehensive and actionable
   - [ ] Metrics available for monitoring
   - [ ] Documentation updated
   - [ ] Runbook includes token refresh troubleshooting

## Conclusion

This architectural analysis reveals that **the token refresh and retry mechanism is already implemented** in the current codebase (`api_client.py`). The implementation uses a **recursive retry pattern** instead of the nested function wrapper pattern specified in the task, but achieves the same goals with equivalent guarantees.

**Key Architectural Strengths**:
- ✅ Comprehensive coverage of all API methods
- ✅ Proper asyncio.Lock for concurrency protection
- ✅ Double-check pattern prevents redundant refreshes
- ✅ Integration with existing circuit breaker
- ✅ Consistent error handling and logging
- ✅ Non-blocking execution via thread pool

**Recommended Validation Actions**:
1. **Test existing implementation** against the success criteria
2. **Verify error patterns** match actual token expiration errors from API
3. **Load test** concurrent operations during token expiration
4. **Confirm** recursive retry pattern provides single retry guarantee

**No Implementation Required**: The task specification appears to describe the existing implementation. Focus should be on **validation, testing, and potential refinement** rather than new implementation.

**If New Implementation Is Required** (contradiction with existing code):
- Follow the nested function wrapper pattern from task specification
- Replace recursive calls with `_execute_with_retry()` wrapper
- Maintain all existing error handling and logging
- Ensure circuit breaker integration preserved
