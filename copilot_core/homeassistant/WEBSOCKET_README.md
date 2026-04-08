# HomeAssistant WebSocket Client

Real-time event streaming from HomeAssistant via WebSocket connection.

## Overview

This module provides:

- **Async WebSocket Client** (`websocket_client.py`) - Persistent WebSocket connection with auto-reconnect
- **Event Handler** (`event_handler.py`) - Event subscription, routing, throttling, and history
- **REST API** (`api/v1/ha_events.py`) - Endpoints for managing event subscriptions

## Features

- ✅ WebSocket connection to HA (`ws://homeassistant.local:8123/api/websocket`)
- ✅ Authentication with Long-Lived Access Token
- ✅ Event subscription: `state_changed`, `call_service`, `area_registry_updated`, etc.
- ✅ Auto-reconnect with exponential backoff (1s → 60s max delay)
- ✅ Event queue with throttling (100ms default)
- ✅ Event history tracking (last 100 events)
- ✅ Socket.IO broadcast to dashboard clients
- ✅ REST API for subscription management

## Quick Start

### 1. Initialize the API

```python
from flask import Flask
from flask_socketio import SocketIO
from copilot_core.homeassistant import init_ha_events_api, register_socketio_handlers

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize HA events API with Socket.IO
init_ha_events_api(socketio)
register_socketio_handlers(socketio)

# Register blueprint
from copilot_core.api.v1.ha_events import ha_events_bp
app.register_blueprint(ha_events_bp, url_prefix="/api/v1")
```

### 2. Connect to HomeAssistant

```bash
curl -X POST http://localhost:5000/api/v1/ha/events/connect \
  -H "X-Auth-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "your-long-lived-access-token",
    "base_url": "ws://homeassistant.local:8123",
    "auto_subscribe": true
  }'
```

Response:
```json
{
  "ok": true,
  "connected": true,
  "base_url": "ws://homeassistant.local:8123",
  "subscribed_events": [
    "state_changed",
    "call_service",
    "area_registry_updated"
  ]
}
```

### 3. Subscribe to Additional Events

```bash
curl -X POST http://localhost:5000/api/v1/ha/events/subscribe \
  -H "X-Auth-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "event_types": ["device_registry_updated", "entity_registry_updated"],
    "throttle_ms": 50
  }'
```

### 4. Get Event History

```bash
curl -X GET "http://localhost:5000/api/v1/ha/events/history?limit=50&event_type=state_changed" \
  -H "X-Auth-Token: your-token"
```

### 5. Receive Real-Time Events via Socket.IO

**Client-side (JavaScript):**

```javascript
const socket = io('http://localhost:5000/ha');

socket.on('connect', () => {
  console.log('Connected to HA events');
  
  // Subscribe to events
  socket.emit('subscribe', {
    event_types: ['state_changed', 'call_service']
  });
});

socket.on('ha_event', (event) => {
  console.log('Received event:', event);
  // {
  //   event_type: 'state_changed',
  //   data: { entity_id: 'light.living_room', ... },
  //   origin: 'LOCAL',
  //   time_fired: '2024-03-02T00:00:00',
  //   received_at: '2024-03-02T00:00:00'
  // }
});

socket.on('disconnect', () => {
  console.log('Disconnected from HA events');
});
```

## API Reference

### REST Endpoints

#### `POST /api/v1/ha/events/connect`

Establish WebSocket connection to HomeAssistant.

**Request:**
```json
{
  "access_token": "your-token",
  "base_url": "ws://homeassistant.local:8123",
  "auto_subscribe": true
}
```

**Response:**
```json
{
  "ok": true,
  "connected": true,
  "subscribed_events": ["state_changed", "call_service", "area_registry_updated"]
}
```

---

#### `POST /api/v1/ha/events/subscribe`

Subscribe to specific event types.

**Request:**
```json
{
  "event_types": ["state_changed", "custom_event"],
  "throttle_ms": 100
}
```

**Response:**
```json
{
  "ok": true,
  "subscribed": ["state_changed", "custom_event"],
  "throttle_ms": 100,
  "active_subscriptions": ["state_changed", "call_service", "custom_event"]
}
```

---

#### `POST /api/v1/ha/events/unsubscribe`

Unsubscribe from event types.

**Request:**
```json
{
  "event_types": ["custom_event"],
  "clear_all": false
}
```

**Response:**
```json
{
  "ok": true,
  "unsubscribed": ["custom_event"],
  "remaining_subscriptions": ["state_changed", "call_service"]
}
```

---

#### `GET /api/v1/ha/events/history`

Get recent event history.

**Query Params:**
- `limit` (default: 100, max: 500) - Number of events to return
- `event_type` (optional) - Filter by event type
- `include_data` (default: true) - Include event data

**Response:**
```json
{
  "ok": true,
  "count": 50,
  "events": [
    {
      "event_type": "state_changed",
      "data": { "entity_id": "light.living_room", ... },
      "origin": "LOCAL",
      "time_fired": "2024-03-02T00:00:00",
      "received_at": "2024-03-02T00:00:00"
    }
  ]
}
```

---

#### `GET /api/v1/ha/events/status`

Get event system status.

**Response:**
```json
{
  "ok": true,
  "connected": true,
  "websocket_state": "connected",
  "active_subscriptions": ["state_changed", "call_service"],
  "queue_size": 0,
  "history_size": 42,
  "throttle_ms": 100,
  "messages_received": 1234
}
```

---

#### `POST /api/v1/ha/events/clear`

Clear event history.

**Response:**
```json
{
  "ok": true,
  "message": "Event history cleared"
}
```

---

#### `POST /api/v1/ha/events/disconnect`

Disconnect from HomeAssistant WebSocket.

**Response:**
```json
{
  "ok": true,
  "message": "Disconnected"
}
```

### Socket.IO Events

**Namespace:** `/ha`

#### Client → Server

**`subscribe`** - Subscribe to events
```javascript
socket.emit('subscribe', {
  event_types: ['state_changed', 'call_service']
});
```

**`unsubscribe`** - Unsubscribe from events
```javascript
socket.emit('unsubscribe', {
  event_types: ['call_service']
});
```

#### Server → Client

**`ha_event`** - Real-time event notification
```javascript
socket.on('ha_event', (event) => {
  console.log(event);
});
```

## Programmatic Usage

### Direct WebSocket Client

```python
import asyncio
from copilot_core.homeassistant import HomeAssistantWebSocketClient, WebSocketConfig

async def main():
    config = WebSocketConfig(
        base_url="ws://homeassistant.local:8123",
        access_token="your-token"
    )
    
    client = HomeAssistantWebSocketClient(config)
    
    # Connect
    connected = await client.connect()
    
    if connected:
        # Subscribe to events
        await client.subscribe_events([
            "state_changed",
            "call_service"
        ])
        
        # Add message handler
        def on_message(msg):
            print(f"Received: {msg}")
        
        client.add_message_handler(on_message)
        
        # Start listening (runs indefinitely)
        await client.start_listening()

asyncio.run(main())
```

### Event Handler with Custom Logic

```python
from copilot_core.homeassistant import EventHandler, HAEvent

async def on_state_change(event: HAEvent):
    """Handle state change events."""
    entity_id = event.data.get("entity_id")
    new_state = event.data.get("new_state", {}).get("state")
    
    print(f"Entity {entity_id} changed to {new_state}")

async def main():
    handler = EventHandler(throttle_ms=50)
    
    # Subscribe to events
    await handler.subscribe("state_changed", handler=on_state_change, throttle_ms=50)
    await handler.subscribe("call_service", throttle_ms=100)
    
    # Start processing
    await handler.start_processing()

asyncio.run(main())
```

## Configuration

### WebSocketConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | str | `"ws://homeassistant.local:8123"` | WebSocket base URL |
| `access_token` | str | `""` | Long-lived access token |
| `timeout_seconds` | float | `5.0` | Connection timeout |
| `verify_ssl` | bool | `True` | Verify SSL certificates |
| `max_reconnect_attempts` | int | `10` | Max reconnection attempts |
| `initial_reconnect_delay` | float | `1.0` | Initial reconnect delay (seconds) |
| `max_reconnect_delay` | float | `60.0` | Max reconnect delay (seconds) |
| `ping_interval` | float | `30.0` | WebSocket ping interval (seconds) |

### EventHandler

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `throttle_ms` | int | `100` | Event throttling interval |
| `history_size` | int | `100` | Max events in history |

## Error Handling

The WebSocket client automatically handles:

- **Connection failures** - Retries with exponential backoff
- **Authentication errors** - Reports error, does not retry
- **Timeout errors** - Triggers reconnection
- **Message parsing errors** - Logs warning, continues processing

Max reconnection attempts: 10 (configurable)
Backoff strategy: 1s → 2s → 4s → 8s → 16s → 32s → 60s (max)

## Throttling

Event throttling prevents overwhelming clients with high-frequency updates:

- Default throttle: 100ms per event type + identifier
- Identifier examples:
  - `state_changed`: entity_id
  - `call_service`: domain.service
  - Others: event_type

Throttled events are dropped (not queued).

## Security

- All endpoints require authentication via `X-Auth-Token` header or `token` query param
- Access tokens should be long-lived tokens from HomeAssistant user profile
- SSL verification enabled by default (disable for self-signed certs with `verify_ssl=False`)

## Troubleshooting

### Connection fails

1. Check HomeAssistant is running and accessible
2. Verify WebSocket URL is correct (`ws://` not `http://`)
3. Check access token is valid (create new one in HA user profile)
4. Check firewall allows WebSocket connections (port 8123)

### Events not received

1. Check connection status: `GET /api/v1/ha/events/status`
2. Verify subscriptions: check `active_subscriptions` in status response
3. Check throttling - events may be dropped if too frequent
4. Check Socket.IO room membership for dashboard clients

### High memory usage

1. Reduce `history_size` in EventHandler
2. Increase `throttle_ms` to drop more events
3. Clear history periodically: `POST /api/v1/ha/events/clear`

## Testing

```bash
# Check connection
curl -X GET http://localhost:5000/api/v1/ha/events/status \
  -H "X-Auth-Token: your-token"

# Get history
curl -X GET "http://localhost:5000/api/v1/ha/events/history?limit=10" \
  -H "X-Auth-Token: your-token"

# Test with WebSocket client (requires wscat)
wscat -c "ws://localhost:5000/api/v1/ha/events/subscribe?token=your-token"
```

## See Also

- HomeAssistant REST API: `copilot_core/homeassistant/client.py`
- HomeAssistant Discovery API: `copilot_core/homeassistant/api.py`
- Socket.IO documentation: https://socket.io/docs/
