# Redis Configuration Guide

## Overview

This document describes the Redis configuration for the Insurance Recommendation Agent system. Redis is used as the hot data layer for storing recent conversation messages, session state, and caching.

## Architecture

### Three-Layer Memory System

Redis serves as the **Hot Data Layer** in our three-layer memory architecture:

1. **Hot Data Layer (Redis)** - Recent 5 turns of conversation
2. **Warm Data Layer (PostgreSQL)** - Historical conversation beyond 5 turns
3. **Cold Data Layer (FAISS + PostgreSQL)** - Archived sessions and vector search

## Key Naming Conventions

All Redis keys follow a structured naming convention for easy management and debugging:

### Hot Data Keys

Format: `hot:{session_id}:{data_type}`

- `hot:{session_id}:messages` - Recent conversation messages (list)
- `hot:{session_id}:slots` - Extracted slot values (string/JSON)
- `hot:{session_id}:context` - Current conversation context (string/JSON)
- `hot:{session_id}:metadata` - Session metadata (string/JSON)

**Example:**
```
hot:session-abc123:messages
hot:session-abc123:slots
```

### Cache Keys

Format: `cache:{resource_type}:{identifier}`

- `cache:recommendation:{profile_hash}` - Cached recommendation results
- `cache:product:{product_id}:vector` - Cached product feature vectors
- `cache:user:{user_id}:profile` - Cached user profiles

**Example:**
```
cache:recommendation:hash_xyz789
cache:product:prod-001:vector
```

### Session Management Keys

- `lock:session:{session_id}` - Session lock for concurrency control
- `state:session:{session_id}` - Session state information
- `active:sessions` - Set of all active session IDs

### Metrics Keys

- `metrics:agent:{agent_name}` - Agent performance metrics
- `metrics:session:{session_id}` - Session-level metrics

## Configuration

### Environment Variables

Configure Redis connection in `.env` file:

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=          # Optional, leave empty if no password
```

### Connection Pool Settings

The Redis client uses a connection pool with the following settings:

- **Max Connections**: 50
- **Socket Timeout**: 5 seconds
- **Connection Timeout**: 5 seconds
- **Health Check Interval**: 30 seconds
- **Decode Responses**: True (automatic string decoding)
- **Retry on Timeout**: True

These settings are configured in `utils/redis_client.py`.

## Usage

### Basic Usage

```python
from utils.redis_client import get_redis_client, RedisKeyNamespace

# Get Redis client (singleton)
redis_client = get_redis_client()

# Check health
if redis_client.is_healthy():
    print("Redis is healthy")

# Add hot message
session_id = "session-123"
message = '{"role": "user", "content": "Hello"}'
redis_client.add_hot_message(session_id, message)

# Get hot messages
messages = redis_client.get_hot_messages(session_id)

# Set cache
cache_key = RedisKeyNamespace.cache_recommendation("profile_hash")
redis_client.set_cache(cache_key, '{"products": [...]}', ttl_seconds=3600)

# Get cache
cached_data = redis_client.get_cache(cache_key)
```

### Hot Data Operations

```python
# Add message (automatically keeps only last 5)
redis_client.add_hot_message(session_id, message_json)

# Get all hot messages
messages = redis_client.get_hot_messages(session_id)

# Set/Get slots
redis_client.set_hot_slots(session_id, slots_json)
slots = redis_client.get_hot_slots(session_id)

# Set/Get context
redis_client.set_hot_context(session_id, context_json)
context = redis_client.get_hot_context(session_id)

# Clear all hot data for a session
redis_client.clear_hot_data(session_id)
```

### Session Lock (Concurrency Control)

```python
# Acquire lock
if redis_client.acquire_session_lock(session_id, timeout_seconds=10):
    try:
        # Critical section - process session
        pass
    finally:
        # Always release lock
        redis_client.release_session_lock(session_id)
else:
    print("Session is locked by another process")
```

### Active Session Management

```python
# Add session to active set
redis_client.add_active_session(session_id)

# Get all active sessions
active_sessions = redis_client.get_active_sessions()

# Remove session from active set
redis_client.remove_active_session(session_id)
```

## Health Checks

### Comprehensive Health Check

```python
health = redis_client.health_check()

if health['healthy']:
    print(f"Redis Version: {health['info']['redis_version']}")
    print(f"Connected Clients: {health['info']['connected_clients']}")
    print(f"Memory Used: {health['info']['used_memory_human']}")
else:
    print(f"Health check failed: {health['error']}")
```

### Quick Health Check

```python
if redis_client.is_healthy():
    print("Redis is operational")
```

## Data Expiration

### Automatic Expiration

- **Hot Data**: 30 minutes TTL (automatically set)
- **Cache Data**: Configurable TTL (default: 1 hour)
- **Session Locks**: Configurable timeout (default: 10 seconds)

### Manual Cleanup

```python
# Clear hot data when session ends
redis_client.clear_hot_data(session_id)

# Delete specific cache
redis_client.delete_cache(cache_key)
```

## Testing

### Run Unit Tests

```bash
# Run all Redis client tests
uv run pytest tests/unit/test_redis_client.py -v

# Run specific test
uv run pytest tests/unit/test_redis_client.py::TestRedisClient::test_health_check_success -v
```

### Test Redis Connection

```bash
# Run integration test script
uv run python scripts/test_redis_connection.py
```

This script will:
1. Initialize Redis client
2. Perform health check
3. Test hot data operations
4. Test cache operations
5. Test session locks
6. Test active session management
7. Test metrics operations
8. Clean up test data

## Monitoring

### Key Metrics to Monitor

1. **Connection Pool**
   - Active connections
   - Connection errors
   - Connection timeouts

2. **Performance**
   - Command latency (P50, P95, P99)
   - Commands per second
   - Memory usage

3. **Health**
   - Ping response time
   - Failed health checks
   - Connection failures

### Logging

Redis operations are logged with the following levels:

- **INFO**: Initialization, successful operations
- **WARNING**: Health check failures, retry attempts
- **ERROR**: Connection errors, operation failures
- **DEBUG**: Detailed operation logs (when DEBUG=true)

## Troubleshooting

### Connection Refused

**Problem**: `ConnectionError: Connection refused`

**Solutions**:
1. Verify Redis is running: `redis-cli ping`
2. Check Redis host/port in `.env`
3. Check firewall settings
4. Verify Redis is listening on correct interface

### Timeout Errors

**Problem**: `TimeoutError: Timeout reading from socket`

**Solutions**:
1. Increase socket timeout in connection pool
2. Check network latency
3. Verify Redis server performance
4. Check for slow commands: `redis-cli slowlog get 10`

### Memory Issues

**Problem**: Redis running out of memory

**Solutions**:
1. Check memory usage: `redis-cli info memory`
2. Verify TTL is set on keys
3. Implement eviction policy in Redis config
4. Increase Redis max memory limit

### Authentication Failed

**Problem**: `AuthenticationError: Authentication required`

**Solutions**:
1. Set `REDIS_PASSWORD` in `.env`
2. Verify password is correct
3. Check Redis `requirepass` configuration

## Best Practices

1. **Always use key namespaces** - Use `RedisKeyNamespace` class for consistent naming
2. **Set TTL on all keys** - Prevent memory leaks from abandoned keys
3. **Use connection pool** - Don't create new connections for each operation
4. **Handle errors gracefully** - Redis failures shouldn't crash the application
5. **Monitor health** - Regular health checks to detect issues early
6. **Clean up on session end** - Call `clear_hot_data()` when session closes
7. **Use locks for critical sections** - Prevent race conditions in concurrent access
8. **Log operations** - Enable logging for debugging and monitoring

## Production Considerations

### High Availability

For production, consider:

1. **Redis Sentinel** - Automatic failover
2. **Redis Cluster** - Horizontal scaling
3. **Replication** - Master-slave setup for read scaling
4. **Backup** - Regular RDB/AOF backups

### Security

1. **Enable authentication** - Set strong password
2. **Use TLS** - Encrypt connections in production
3. **Network isolation** - Redis should not be publicly accessible
4. **Disable dangerous commands** - Rename or disable FLUSHALL, FLUSHDB, etc.

### Performance Tuning

1. **Connection pooling** - Adjust max_connections based on load
2. **Pipeline commands** - Batch multiple commands for efficiency
3. **Use appropriate data structures** - Lists for messages, Sets for sessions
4. **Monitor slow commands** - Identify and optimize slow operations

## References

- [Redis Documentation](https://redis.io/documentation)
- [redis-py Documentation](https://redis-py.readthedocs.io/)
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)
