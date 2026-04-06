# Home Assistant Bridge v2 - Slice 311

## Overview

This module implements the adapter for integrating Home Assistant with the Core Permission Management API as part of Slice 311 of the hexagonal architecture refactor.

## Components

### Interface (`interface.py`)
Defines the abstract contract for Home Assistant integration:
- `sync_permissions_to_ha()` - Synchronize permissions from Core to HA
- `handle_ha_permission_request()` - Handle permission creation requests from HA
- `handle_ha_permission_delete()` - Handle permission deletion requests from HA
- `get_ha_permission_info()` - Retrieve combined permission information

### Adapter (`adapter.py`)
Concrete implementation of the interface that:
- Communicates with Home Assistant via its API
- Integrates with the Core Permission Management API
- Handles bidirectional synchronization of permission data

### Configuration (`config.py`)
Manages configuration for the adapter:
- Home Assistant URL and authentication token
- Synchronization intervals
- Debug logging settings

### Factory (`factory.py`)
Provides factory methods for creating adapter instances:
- From configuration dictionaries
- From environment variables

## Integration Points

The adapter integrates with:
1. Core Permission Management API (`copilot_core.api.v1.permission_management`)
2. Home Assistant via `homeassistant_api` client library

## Environment Variables

- `HA_URL` - Home Assistant URL (default: http://localhost:8123)
- `HA_TOKEN` - Home Assistant Long-Lived Access Token
- `HA_SYNC_INTERVAL` - Sync interval in seconds (default: 300)
- `HA_DEBUG_LOGGING` - Enable debug logging (default: false)

## Usage

```python
from homeassistant.slices.311.factory import HABridgeV2AdapterFactory

# Create adapter from environment variables
adapter = HABridgeV2AdapterFactory.create_from_env()

# Sync permissions
success = adapter.sync_permissions_to_ha()

# Handle permission request from HA
result = adapter.handle_ha_permission_request({
    "name": "new_permission",
    "description": "Example permission"
})
```