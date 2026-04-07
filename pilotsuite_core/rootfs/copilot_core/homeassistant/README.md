# HomeAssistant Integration

Async client and auto-discovery for HomeAssistant REST API.

## Features

- **Async HTTP Client**: Full async support with `aiohttp`
- **Auto-Discovery**: Automatic discovery via mDNS/DNS-SD and hostname resolution
- **Entity Mapping**: Automatic mapping of HA entities to dashboard widgets
- **SSL Support**: Configurable SSL verification (supports self-signed certificates)
- **Retry Logic**: Exponential backoff retry on failures
- **Connection Timeout**: Configurable timeout (default 5s)

## Installation

Add to `requirements.txt`:

```txt
aiohttp>=3.9.0
```

## Quick Start

### Basic Usage

```python
from copilot_core.homeassistant import HomeAssistantClient, HAConnectionConfig

# Create client
config = HAConnectionConfig(
    base_url="http://homeassistant.local:8123",
    access_token="your-long-lived-token",
    timeout_seconds=5.0
)

client = HomeAssistantClient(config)

# Test connection
status = await client.test_connection()
if status.connected:
    print(f"Connected in {status.response_time_ms}ms")

# Get areas
areas = await client.get_areas()

# Get all entities
states = await client.get_states()

# Get single entity
entity = await client.get_entity("light.living_room")

# Close client
await client.close()
```

### Auto-Discovery

```python
from copilot_core.homeassistant import AutoDiscovery

discovery = AutoDiscovery()

# Discover instances
instances = await discovery.discover()
for inst in instances:
    print(f"Found: {inst.base_url} ({inst.friendly_name})")

# Connect to first discovered instance
if instances:
    client = await discovery.connect(
        base_url=instances[0].base_url,
        access_token="your-token"
    )
```

### Entity Mapping

```python
from copilot_core.homeassistant import EntityMapper

mapper = EntityMapper()

# Update area registry
areas = await client.get_areas()
mapper.update_area_registry(areas)

# Map all entities
states = await client.get_states()
mappings = mapper.map_entities(states)

for mapping in mappings:
    print(f"{mapping.name}: {mapping.widget_type} (priority: {mapping.priority})")

# Filter by area
living_room_entities = mapper.get_by_area("living_room")

# Filter by type
lights = mapper.get_by_widget_type(WidgetType.LIGHT)
```

## API Endpoints

The module provides Flask API endpoints under `/api/v1/ha/`:

### POST `/api/v1/ha/connect`

Establish connection to HomeAssistant.

**Request:**
```json
{
    "base_url": "http://homeassistant.local:8123",
    "access_token": "your-token",
    "verify_ssl": true,
    "timeout_seconds": 5.0
}
```

**Response:**
```json
{
    "ok": true,
    "connected": true,
    "base_url": "...",
    "response_time_ms": 42.5,
    "version": "2024.1.0",
    "friendly_name": "Home Assistant"
}
```

### GET `/api/v1/ha/status`

Get current connection status.

### GET `/api/v1/ha/areas`

Get all areas/zones.

### GET `/api/v1/ha/entities`

Get all entities with optional filters.

**Query Params:**
- `domain`: Filter by domain (e.g., "light", "sensor")
- `area_id`: Filter by area
- `device_class`: Filter by device class

### GET `/api/v1/ha/entity/<entity_id>`

Get single entity.

### POST `/api/v1/ha/discover`

Discover HomeAssistant instances.

### POST `/api/v1/ha/disconnect`

Disconnect from HomeAssistant.

## Authentication

Use HomeAssistant **Long-Lived Access Token**:

1. Go to HA Profile → Long-Lived Access Tokens
2. Create new token
3. Use token in `X-Auth-Token` header or `access_token` field

## SSL/TLS

For self-signed certificates:

```python
config = HAConnectionConfig(
    base_url="https://homeassistant.local:8123",
    access_token="your-token",
    verify_ssl=False  # Accept self-signed
)
```

## Error Handling

```python
from aiohttp import ClientError

try:
    areas = await client.get_areas()
except PermissionError:
    print("Authentication failed")
except FileNotFoundError:
    print("Endpoint not found")
except ClientError as e:
    print(f"Connection error: {e}")
```

## Testing

```bash
cd /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app
pytest -q tests/homeassistant/
```

## Files

- `client.py` — Async HTTP client
- `auto_discovery.py` — Auto-discovery logic
- `entity_mapper.py` — Entity → Widget mapping
- `api.py` — Flask API endpoints
- `__init__.py` — Package exports

## Integration

The blueprint is automatically registered in `api/v1/blueprint.py`:

```python
from copilot_core.homeassistant.api import ha_discovery_bp
api_v1.register_blueprint(ha_discovery_bp)
```

## Context

Part of PilotSuite Styx Core v12.8.0 — HomeAssistant Auto-Discovery & Client.
