# Cache Module Documentation

Redis-based caching layer for PilotSuite Styx Core with automatic in-memory fallback.

## Overview

This module provides:
- **Async Redis client** with automatic fallback to in-memory storage
- **API response caching** with configurable TTL
- **Cache invalidation** on WebSocket events
- **Hit/miss metrics** for monitoring
- **REST API endpoints** for cache management

## Architecture

```
copilot_core/cache/
├── __init__.py          # Module exports
├── redis_client.py      # Async Redis client with fallback
├── api_cache.py         # API response caching layer
└── tests/
    └── test_cache.py    # Unit tests

copilot_core/api/v1/
└── cache_control.py     # REST API endpoints
```

## Features

### Redis Client (`redis_client.py`)

- **Connection**: localhost:6379 (configurable)
- **Fallback**: Automatic in-memory storage when Redis unavailable
- **TTL Support**: Configurable expiration per key
- **Pattern Deletion**: Wildcard-based key invalidation
- **Health Checks**: Ping-based connection monitoring

### API Cache (`api_cache.py`)

- **TTL Defaults**:
  - Entity data: 5 minutes (300s)
  - State data: 1 minute (60s)
  - Default: 2 minutes (120s)
- **Metrics**: Hit/miss ratio tracking
- **Invalidation**: Key, pattern, or full flush
- **Decorator**: `@cached()` for easy function caching
- **WebSocket Integration**: Auto-invalidate on state changes

### Cache Control API (`cache_control.py`)

Three REST endpoints (all require auth token):

#### GET `/api/v1/cache/status`
```json
{
  "success": true,
  "data": {
    "connected": true,
    "host": "localhost",
    "port": 6379,
    "using_fallback": false,
    "redis_available": true
  }
}
```

#### POST `/api/v1/cache/invalidate`
```json
// Invalidate all
{"all": true}

// Invalidate specific key
{"key": "entity:light.living_room"}

// Invalidate by pattern
{"pattern": "state:*"}

// Default: invalidate entities and states
{}
```

Response:
```json
{
  "success": true,
  "data": {
    "invalidated_entities": 15,
    "invalidated_states": 23,
    "total": 38
  }
}
```

#### GET `/api/v1/cache/stats`
```json
{
  "success": true,
  "data": {
    "hits": 150,
    "misses": 23,
    "total": 173,
    "hit_ratio": 0.867,
    "connection": {
      "connected": true,
      "host": "localhost",
      "port": 6379,
      "using_fallback": false
    }
  }
}
```

## Usage

### Basic Caching

```python
from copilot_core.cache import get_api_cache

cache = get_api_cache()

# Cache with default TTL
await cache.set("my:key", {"data": "value"})

# Cache with custom TTL (seconds)
await cache.set("my:key", {"data": "value"}, ttl=600)

# Get from cache
value = await cache.get("my:key")

# Invalidate
await cache.invalidate("my:key")
await cache.invalidate_pattern("my:*")
```

### Entity/State Caching

```python
# Cache entity data (5 min TTL)
await cache.cache_entity_data("light.living_room", entity_data)

# Cache state (1 min TTL)
await cache.cache_state("light.living_room", state_data)

# Get cached data
entity = await cache.get_entity_data("light.living_room")
state = await cache.get_state("light.living_room")

# Invalidate
await cache.invalidate_entity("light.living_room")
await cache.invalidate_entities()  # All entities
```

### Using the Decorator

```python
from copilot_core.cache import cached

@cached(ttl=300, key_prefix="entities")
async def get_entities():
    # Expensive operation
    return await fetch_all_entities()

# First call: executes function and caches result
# Subsequent calls: returns cached result (5 min TTL)
```

### WebSocket Integration

```python
from copilot_core.cache.api_cache import setup_cache_invalidation

# Auto-invalidate cache on state changes
await setup_cache_invalidation(websocket_handler)
```

## Installation

### Redis (Optional but Recommended)

```bash
# Install Redis
apt-get install redis-server

# Start Redis
systemctl start redis

# Verify
redis-cli ping  # Should return: PONG
```

### Python Dependencies

```bash
# Install redis async client
pip install redis
```

If `redis` package is not installed, the module automatically falls back to in-memory storage.

## Configuration

### Environment Variables

```bash
# Redis connection
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # Optional

# Auth token for API endpoints
COPILOT_AUTH_TOKEN=your_secret_token
```

### Initialize in App

```python
from copilot_core.api.v1.cache_control import init_cache_control_api

# In your Flask app setup
init_cache_control_api(app)
```

## Monitoring

### Cache Hit Ratio

Monitor via `/api/v1/cache/stats`:
- **hit_ratio > 0.8**: Excellent cache utilization
- **hit_ratio 0.5-0.8**: Good, room for improvement
- **hit_ratio < 0.5**: Consider adjusting TTL or caching strategy

### Connection Status

Check `/api/v1/cache/status`:
- `connected: true` → Redis available
- `using_fallback: true` → Using in-memory (Redis unavailable)

## Performance Notes

- **Redis**: Sub-millisecond latency, persistent across restarts
- **In-Memory**: Nanosecond latency, lost on restart
- **TTL Selection**:
  - States: Short TTL (1 min) due to frequent changes
  - Entities: Medium TTL (5 min) for stable data
  - Config/Settings: Long TTL (10+ min) for rare changes

## Security

- All API endpoints require authentication via `require_token` decorator
- Token from `COPILOT_AUTH_TOKEN` env var or options.json
- No sensitive data should be cached without encryption

## Troubleshooting

### Redis Connection Failed
```
redis.asyncio not available, using in-memory fallback
```
- Install redis package: `pip install redis`
- Or start Redis server: `systemctl start redis`

### Cache Not Invalidating
- Check WebSocket event listeners are registered
- Verify event handler is broadcasting state_changed events

### High Miss Ratio
- Increase TTL for stable data
- Cache at higher level (aggregate responses vs individual calls)
- Pre-warm cache on startup for frequently accessed data
