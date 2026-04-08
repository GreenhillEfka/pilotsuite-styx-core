# Connection Pooling Guide

## Overview

PilotSuite Core includes a production-ready connection pooling system for efficient HTTP client session management. This reduces connection overhead and improves performance for repeated API calls to:

- Home Assistant Supervisor API
- Ollama API

## Features

- **Configurable pool size**: Default 10 connections per target (via `POOL_MAX_CONNECTIONS`)
- **Connection reuse**: Sessions are reused across requests
- **Timeout handling**: Configurable timeouts (via `POOL_TIMEOUT`)
- **Health checks**: Automatic health monitoring (via `POOL_HEALTH_CHECK_INTERVAL`)
- **Metrics**: Built-in metrics for connection reuse rates
- **Graceful shutdown**: Proper cleanup on application exit

## Configuration

Set environment variables to configure the connection pool:

```bash
# Pool size (default: 10)
export POOL_MAX_CONNECTIONS=20

# Connection timeout in seconds (default: 30)
export POOL_TIMEOUT=60

# Health check interval in seconds (default: 60)
export POOL_HEALTH_CHECK_INTERVAL=120
```

## Usage

### Basic Usage

```python
from copilot_core.connection_pool import get_ha_session, get_ollama_session

# Use HA session
async with get_ha_session() as session:
    async with session.get('http://homeassistant:8123/api/states') as resp:
        data = await resp.json()

# Use Ollama session
async with get_ollama_session() as session:
    async with session.post('http://ollama:11434/api/generate', json=prompt) as resp:
        response = await resp.json()
```

### Advanced Usage with Pool Manager

```python
from copilot_core.connection_pool import get_pool_manager, close_pool

# Get pool manager
pool = await get_pool_manager()

# Get sessions
ha_session = await pool.get_ha_session()
ollama_session = await pool.get_ollama_session()

# Use sessions...

# Health checks
ha_healthy = await pool.check_ha_health('http://homeassistant:8123')
ollama_healthy = await pool.check_ollama_health('http://ollama:11434')

# Get metrics
metrics = pool.get_metrics()
print(f"HA reuse rate: {metrics['ha_pool']['reuse_rate_pct']}%")

# Cleanup (on shutdown)
await close_pool()
```

## Migration Guide

### Before (without pooling)

```python
import aiohttp

async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()
```

### After (with pooling)

```python
from copilot_core.connection_pool import get_ha_session

async def fetch_data():
    async with get_ha_session() as session:
        async with session.get(url) as resp:
            return await resp.json()
```

## Metrics

The connection pool provides detailed metrics:

```python
from copilot_core.connection_pool import get_pool_metrics

metrics = get_pool_metrics()
# {
#   "ha_pool": {
#     "requests_total": 100,
#     "connections_reused": 85,
#     "reuse_rate_pct": 85.0,
#     "healthy": True,
#     "session_active": True
#   },
#   "ollama_pool": {...},
#   "config": {...}
# }
```

## Best Practices

1. **Use context managers**: Always use `async with get_ha_session()` to ensure proper cleanup
2. **Don't create sessions manually**: Use the pool manager for all HTTP clients
3. **Monitor metrics**: Check reuse rates to ensure pooling is effective
4. **Configure pool size**: Adjust `POOL_MAX_CONNECTIONS` based on your workload
5. **Handle shutdown**: Call `await close_pool()` on application exit

## Testing

Run the connection pool tests:

```bash
cd copilot_core/rootfs/usr/src/app
pytest tests/test_connection_pool.py -v
```

All 23 tests should pass.

## Implementation Details

- **Singleton pattern**: Global pool manager ensures single instance
- **Thread-safe**: Uses asyncio locks for concurrent access
- **Lazy initialization**: Pool is created on first use
- **Automatic reconnection**: Sessions are recreated if closed
- **Health check caching**: Health status cached to avoid excessive checks

## Files

- `copilot_core/connection_pool.py`: Main implementation
- `tests/test_connection_pool.py`: Comprehensive test suite
- `docs/CONNECTION_POOLING.md`: This documentation

## Author

Clawdya  
Version: 1.0.0  
Date: 2026-03-02
