"""HomeAssistant WebSocket Event API Endpoints.

Provides REST and WebSocket API for HA event subscriptions:
- GET /api/v1/ha/events/subscribe — WebSocket endpoint for real-time events
- POST /api/v1/ha/events/subscribe — Subscribe to event types
- GET /api/v1/ha/events/history — Get recent event history
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, List

from flask import Blueprint, jsonify, request

try:
    from copilot_core.api.security import require_token
except ImportError:
    from ..api.security import require_token

from .websocket_client import HomeAssistantWebSocketClient, WebSocketConfig, ConnectionState
from .event_handler import EventHandler, HAEvent, create_standard_subscriptions

logger = logging.getLogger(__name__)

ha_events_bp = Blueprint("ha_events", __name__)

# Global state
_ws_client: Optional[HomeAssistantWebSocketClient] = None
_event_handler: Optional[EventHandler] = None
_listening_task: Optional[asyncio.Task] = None
_socketio = None


def init_ha_events_api(socketio=None) -> None:
    """Initialize HA events API state.
    
    Args:
        socketio: Optional Flask-SocketIO instance for broadcasting
    """
    global _event_handler, _socketio
    
    _event_handler = EventHandler(throttle_ms=100, history_size=100)
    _socketio = socketio
    
    if socketio:
        _event_handler.set_socketio_server(socketio)
    
    logger.info("HA Events API initialized")


def get_ws_client() -> Optional[HomeAssistantWebSocketClient]:
    """Get current WebSocket client instance."""
    return _ws_client


def get_event_handler() -> Optional[EventHandler]:
    """Get current event handler instance."""
    return _event_handler


async def _ensure_connection(access_token: str, base_url: str = "ws://homeassistant.local:8123") -> bool:
    """Ensure WebSocket connection is established.
    
    Args:
        access_token: HomeAssistant long-lived access token
        base_url: WebSocket base URL
    
    Returns:
        True if connected, False otherwise
    """
    global _ws_client, _listening_task
    
    # Create client if needed
    if _ws_client is None:
        config = WebSocketConfig(
            base_url=base_url,
            access_token=access_token
        )
        _ws_client = HomeAssistantWebSocketClient(config)
    
    # Connect if not already connected
    if not _ws_client.is_connected:
        connected = await _ws_client.connect()
        
        if not connected:
            logger.warning("Failed to connect to HA WebSocket")
            return False
        
        # Subscribe to standard events
        standard_events = [
            "state_changed",
            "call_service",
            "area_registry_updated"
        ]
        
        subscribed = await _ws_client.subscribe_events(standard_events)
        
        if not subscribed:
            logger.warning("Failed to subscribe to events")
            return False
        
        # Start listening task if not running
        if _listening_task is None or _listening_task.done():
            _listening_task = asyncio.create_task(_ws_client.start_listening())
            logger.info("Started WebSocket listening task")
        
        # Add event handler to process messages
        _ws_client.add_message_handler(_on_websocket_message)
    
    return True


def _on_websocket_message(message: dict[str, Any]) -> None:
    """Process WebSocket message from HA.

    Args:
        message: Raw WebSocket message dict
    """
    if not _event_handler:
        return

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_event_handler.handle_event(message))
    except RuntimeError:
        # No running event loop — run synchronously in a temporary loop
        asyncio.run(_event_handler.handle_event(message))


@ha_events_bp.route("/api/v1/ha/events/subscribe", methods=["GET"])
@require_token
async def subscribe_events_ws():
    """WebSocket endpoint for real-time event streaming.
    
    This endpoint upgrades to WebSocket and streams HA events
    in real-time to connected clients.
    
    Query params:
        token: Access token (alternative to header)
        events: Comma-separated list of event types to subscribe to
                (default: state_changed,call_service,area_registry_updated)
    
    WebSocket messages (client → server):
    {
        "action": "subscribe",
        "event_types": ["state_changed", "custom_event"]
    }
    {
        "action": "unsubscribe",
        "event_types": ["custom_event"]
    }
    
    WebSocket messages (server → client):
    {
        "type": "event",
        "event_type": "state_changed",
        "data": {...},
        "received_at": "2024-03-02T00:00:00"
    }
    """
    from flask_sock import Sock
    
    # Check if flask-sock is available
    try:
        from flask_sock import Sock
    except ImportError:
        logger.error("flask-sock not installed - WebSocket endpoint unavailable")
        return jsonify({
            "ok": False,
            "error": "WebSocket support not available. Install flask-sock."
        }), 503
    
    # This would be implemented with flask-sock
    # For now, return info about Socket.IO alternative
    return jsonify({
        "ok": True,
        "message": "Use Socket.IO for real-time events",
        "socketio_endpoint": "/socket.io/",
        "socketio_room": "ha_events",
        "note": "Connect via Socket.IO client to receive ha_event messages"
    })


@ha_events_bp.route("/api/v1/ha/events/subscribe", methods=["POST"])
@require_token
async def subscribe_events_post():
    """Subscribe to HomeAssistant event types.
    
    Request body:
    {
        "access_token": "your-long-lived-token",  // Required if not connected
        "base_url": "ws://homeassistant.local:8123",  // Optional
        "event_types": ["state_changed", "call_service"],  // Required
        "throttle_ms": 100  // Optional, default 100
    }
    
    Response:
    {
        "ok": true,
        "subscribed": ["state_changed", "call_service"],
        "throttle_ms": 100,
        "connected": true
    }
    """
    global _event_handler
    
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({
            "ok": False,
            "error": "Invalid JSON body"
        }), 400
    
    event_types = data.get("event_types", [])
    access_token = data.get("access_token", "")
    base_url = data.get("base_url", "ws://homeassistant.local:8123")
    throttle_ms = data.get("throttle_ms", 100)
    
    if not event_types:
        return jsonify({
            "ok": False,
            "error": "event_types is required"
        }), 400
    
    if not isinstance(event_types, list):
        return jsonify({
            "ok": False,
            "error": "event_types must be a list"
        }), 400
    
    # Ensure event handler exists
    if _event_handler is None:
        _event_handler = EventHandler(throttle_ms=throttle_ms)
        
        if _socketio:
            _event_handler.set_socketio_server(_socketio)
    else:
        # Update throttle if changed
        _event_handler.throttle_ms = throttle_ms
    
    # Ensure WebSocket connection
    if access_token:
        connected = await _ensure_connection(access_token, base_url)
        
        if not connected:
            return jsonify({
                "ok": False,
                "error": "Failed to connect to HomeAssistant WebSocket"
            }), 503
    else:
        # Check if already connected
        if _ws_client is None or not _ws_client.is_connected:
            return jsonify({
                "ok": False,
                "error": "Not connected. Provide access_token to establish connection."
            }), 400
    
    # Subscribe to events
    subscribed = []
    failed = []
    
    for event_type in event_types:
        try:
            await _event_handler.subscribe(event_type, throttle_ms=throttle_ms)
            subscribed.append(event_type)
        except Exception as e:
            logger.error(f"Failed to subscribe to {event_type}: {e}")
            failed.append(event_type)
    
    return jsonify({
        "ok": True,
        "subscribed": subscribed,
        "failed": failed,
        "throttle_ms": throttle_ms,
        "connected": _ws_client.is_connected if _ws_client else False,
        "active_subscriptions": _event_handler.active_subscriptions
    })


@ha_events_bp.route("/api/v1/ha/events/unsubscribe", methods=["POST"])
@require_token
async def unsubscribe_events():
    """Unsubscribe from HomeAssistant event types.
    
    Request body:
    {
        "event_types": ["state_changed", "call_service"],  // Optional, clears all if omitted
        "clear_all": true  // Optional, if true clears all subscriptions
    }
    
    Response:
    {
        "ok": true,
        "unsubscribed": ["state_changed"],
        "remaining_subscriptions": ["call_service"]
    }
    """
    global _event_handler
    
    if _event_handler is None:
        return jsonify({
            "ok": False,
            "error": "No active subscriptions"
        }), 400
    
    try:
        data = request.get_json() or {}
    except Exception:
        data = {}
    
    clear_all = data.get("clear_all", False)
    event_types = data.get("event_types", [])
    
    if clear_all:
        # Unsubscribe from all
        all_events = _event_handler.active_subscriptions
        
        for event_type in all_events:
            await _event_handler.unsubscribe(event_type)
        
        return jsonify({
            "ok": True,
            "unsubscribed": all_events,
            "remaining_subscriptions": []
        })
    
    # Unsubscribe from specific events
    unsubscribed = []
    
    for event_type in event_types:
        await _event_handler.unsubscribe(event_type)
        unsubscribed.append(event_type)
    
    return jsonify({
        "ok": True,
        "unsubscribed": unsubscribed,
        "remaining_subscriptions": _event_handler.active_subscriptions
    })


@ha_events_bp.route("/api/v1/ha/events/history", methods=["GET"])
@require_token
async def get_event_history():
    """Get recent event history.
    
    Query params:
        limit: Maximum number of events to return (default: 100, max: 500)
        event_type: Filter by specific event type
        include_data: Include event data (default: true)
    
    Response:
    {
        "ok": true,
        "count": 50,
        "events": [
            {
                "event_type": "state_changed",
                "data": {...},
                "origin": "LOCAL",
                "time_fired": "2024-03-02T00:00:00",
                "received_at": "2024-03-02T00:00:00"
            }
        ]
    }
    """
    global _event_handler
    
    if _event_handler is None:
        return jsonify({
            "ok": False,
            "error": "No event history available"
        }), 400
    
    try:
        limit = int(request.args.get("limit", "100"))
        limit = min(limit, 500)  # Cap at 500
    except ValueError:
        limit = 100
    
    event_type = request.args.get("event_type")
    include_data = request.args.get("include_data", "true").lower() == "true"
    
    try:
        events = await _event_handler.get_history(limit=limit, event_type=event_type)
        
        # Optionally remove data field to reduce response size
        if not include_data:
            for event in events:
                if "data" in event:
                    del event["data"]
        
        return jsonify({
            "ok": True,
            "count": len(events),
            "events": events
        })
    
    except Exception as e:
        logger.error(f"Failed to get event history: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@ha_events_bp.route("/api/v1/ha/events/clear", methods=["POST"])
@require_token
async def clear_event_history():
    """Clear event history.
    
    Response:
    {
        "ok": true,
        "message": "Event history cleared"
    }
    """
    global _event_handler
    
    if _event_handler is None:
        return jsonify({
            "ok": False,
            "error": "No event handler initialized"
        }), 400
    
    await _event_handler.clear_history()
    
    return jsonify({
        "ok": True,
        "message": "Event history cleared"
    })


@ha_events_bp.route("/api/v1/ha/events/status", methods=["GET"])
@require_token
async def get_events_status():
    """Get event system status.
    
    Response:
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
    """
    response = {
        "ok": True,
        "connected": False,
        "websocket_state": "disconnected",
        "active_subscriptions": [],
        "queue_size": 0,
        "history_size": 0,
        "throttle_ms": 100,
        "messages_received": 0
    }
    
    # WebSocket client status
    if _ws_client:
        ws_status = _ws_client.status
        response["connected"] = _ws_client.is_connected
        response["websocket_state"] = ws_status.state.value
        response["messages_received"] = ws_status.messages_received
        
        if ws_status.last_error:
            response["last_error"] = ws_status.last_error
    
    # Event handler status
    if _event_handler:
        response["active_subscriptions"] = _event_handler.active_subscriptions
        response["queue_size"] = _event_handler.queue_size
        response["history_size"] = _event_handler.history_size
        response["throttle_ms"] = _event_handler.throttle_ms
    
    return jsonify(response)


@ha_events_bp.route("/api/v1/ha/events/connect", methods=["POST"])
@require_token
async def connect_events():
    """Establish connection to HomeAssistant WebSocket.
    
    Request body:
    {
        "access_token": "your-long-lived-token",  // Required
        "base_url": "ws://homeassistant.local:8123",  // Optional
        "auto_subscribe": true  // Optional, default true - subscribe to standard events
    }
    
    Response:
    {
        "ok": true,
        "connected": true,
        "base_url": "ws://homeassistant.local:8123",
        "subscribed_events": ["state_changed", "call_service", "area_registry_updated"]
    }
    """
    global _ws_client, _event_handler
    
    try:
        data = request.get_json() or {}
    except Exception:
        data = {}
    
    access_token = data.get("access_token", "")
    base_url = data.get("base_url", "ws://homeassistant.local:8123")
    auto_subscribe = data.get("auto_subscribe", True)
    
    if not access_token:
        return jsonify({
            "ok": False,
            "error": "access_token is required"
        }), 400
    
    # Initialize event handler if needed
    if _event_handler is None:
        _event_handler = EventHandler(throttle_ms=100)
        
        if _socketio:
            _event_handler.set_socketio_server(_socketio)
    
    # Connect
    connected = await _ensure_connection(access_token, base_url)
    
    if not connected:
        return jsonify({
            "ok": False,
            "error": "Failed to connect to HomeAssistant WebSocket"
        }), 503
    
    # Auto-subscribe to standard events
    subscribed_events = []
    
    if auto_subscribe:
        standard_events = [
            "state_changed",
            "call_service",
            "area_registry_updated"
        ]
        
        for event_type in standard_events:
            await _event_handler.subscribe(event_type, throttle_ms=100)
            subscribed_events.append(event_type)
    
    return jsonify({
        "ok": True,
        "connected": True,
        "base_url": base_url,
        "subscribed_events": subscribed_events,
        "websocket_state": _ws_client.status.state.value if _ws_client else "unknown"
    })


@ha_events_bp.route("/api/v1/ha/events/disconnect", methods=["POST"])
@require_token
async def disconnect_events():
    """Disconnect from HomeAssistant WebSocket.
    
    Response:
    {
        "ok": true,
        "message": "Disconnected"
    }
    """
    global _ws_client, _listening_task
    
    if _ws_client:
        await _ws_client.disconnect()
        _ws_client = None
    
    if _listening_task:
        _listening_task.cancel()
        _listening_task = None
    
    logger.info("Disconnected from HA WebSocket")
    
    return jsonify({
        "ok": True,
        "message": "Disconnected"
    })


# Socket.IO event handlers (to be registered with Flask-SocketIO)
def register_socketio_handlers(socketio) -> None:
    """Register Socket.IO event handlers.
    
    Args:
        socketio: Flask-SocketIO instance
    """
    @socketio.on("connect", namespace="/ha")
    def handle_connect(auth):
        """Handle client connection."""
        from flask import request
        sid = request.sid
        logger.info(f"Client connected to HA events: {sid}")
        
        if _event_handler:
            asyncio.create_task(_event_handler.join_socketio_room(sid))
        
        return {"ok": True, "message": "Connected to HA events"}
    
    @socketio.on("disconnect", namespace="/ha")
    def handle_disconnect():
        """Handle client disconnection."""
        from flask import request
        sid = request.sid
        logger.info(f"Client disconnected from HA events: {sid}")
        
        if _event_handler:
            asyncio.create_task(_event_handler.leave_socketio_room(sid))
    
    @socketio.on("subscribe", namespace="/ha")
    def handle_subscribe(data):
        """Handle subscription request from client."""
        from flask import request
        sid = request.sid
        
        event_types = data.get("event_types", [])
        
        if not event_types:
            return {"ok": False, "error": "event_types required"}
        
        if _event_handler:
            for event_type in event_types:
                asyncio.create_task(_event_handler.subscribe(event_type))
            
            asyncio.create_task(_event_handler.join_socketio_room(sid))
            
            return {
                "ok": True,
                "subscribed": event_types,
                "room": "ha_events"
            }
        
        return {"ok": False, "error": "Event handler not initialized"}
    
    @socketio.on("unsubscribe", namespace="/ha")
    def handle_unsubscribe(data):
        """Handle unsubscription request from client."""
        event_types = data.get("event_types", [])
        
        if _event_handler:
            for event_type in event_types:
                asyncio.create_task(_event_handler.unsubscribe(event_type))
            
            return {"ok": True, "unsubscribed": event_types}
        
        return {"ok": False, "error": "Event handler not initialized"}
    
    logger.info("Socket.IO handlers registered for /ha namespace")
