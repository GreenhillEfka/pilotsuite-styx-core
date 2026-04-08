"""WebSocket Handler for Live Neuron Updates.

Broadcasts neuron state changes to connected clients in real-time.
"""
from __future__ import annotations

import logging
import json
import re
from typing import Any, Dict, Set, Optional
from datetime import datetime, timezone

try:
    from flask_socketio import SocketIO, emit, join_room, leave_room
    from flask import request
    SOCKETIO_AVAILABLE = True
except ImportError:
    SocketIO = None  # type: ignore
    emit = None  # type: ignore
    join_room = None  # type: ignore
    leave_room = None  # type: ignore
    request = None  # type: ignore
    SOCKETIO_AVAILABLE = False

_LOGGER = logging.getLogger(__name__)

# WebSocket event types
EVENT_NEURON_UPDATE = "neuron_update"
EVENT_NEURON_FIRE = "neuron_fire"
EVENT_GRAPH_UPDATE = "graph_update"
EVENT_MOOD_CHANGE = "mood_change"
EVENT_SUGGESTION = "suggestion"

# Room name validation: alphanumeric, underscore, hyphen only, max 50 chars
ROOM_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
ROOM_NAME_MAX_LENGTH = 50


def validate_room_name(room_name: str) -> bool:
    """Validate room name format.
    
    Args:
        room_name: Room name to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not room_name or len(room_name) > ROOM_NAME_MAX_LENGTH:
        return False
    return bool(ROOM_NAME_PATTERN.match(room_name))


class NeuronWebSocketHandler:
    """Handler for neuron WebSocket connections."""
    
    def __init__(self, socketio: Optional[SocketIO] = None):
        """Initialize the WebSocket handler.
        
        Args:
            socketio: Flask-SocketIO instance
        """
        self.socketio = socketio
        self.connected_clients: Set[str] = set()
        self.client_rooms: Dict[str, str] = {}
    
    def init_app(self, socketio: SocketIO):
        """Initialize with Flask-SocketIO instance.
        
        Args:
            socketio: Flask-SocketIO instance
        """
        self.socketio = socketio
        self._register_handlers()
    
    def _register_handlers(self):
        """Register WebSocket event handlers."""
        if not self.socketio or not SOCKETIO_AVAILABLE:
            return
        
        @self.socketio.on("connect")
        def handle_connect(auth=None):
            """Handle client connection with authentication.

            Token is resolved from (in order):
            1. SocketIO native ``auth`` dict (``{'token': '...'}``).
            2. Query parameter ``?token=xxx``.
            3. ``X-Auth-Token`` header.

            Connections without a valid token are **rejected**.
            """
            if request is None:
                return False

            from copilot_core.api.security import validate_websocket_token, get_auth_token
            import hmac as _hmac

            client_id = request.sid

            # --- authenticate ---------------------------------------------------
            authenticated = False
            configured_token = get_auth_token()

            if not configured_token:
                _LOGGER.warning(
                    "Neuron WS connection rejected (no token configured): %s",
                    client_id,
                )
                return False

            # 1. SocketIO auth dict
            if auth and isinstance(auth, dict) and "token" in auth:
                candidate = str(auth["token"]).strip()
                if candidate and _hmac.compare_digest(candidate, configured_token):
                    authenticated = True

            # 2+3. Query param / X-Auth-Token header
            if not authenticated:
                authenticated = validate_websocket_token(request)

            if not authenticated:
                _LOGGER.warning(
                    "Neuron WS authentication failed – connection rejected: %s",
                    client_id,
                )
                return False
            # -----------------------------------------------------------------

            self.connected_clients.add(client_id)
            _LOGGER.info("Client connected: %s", client_id)

            # Auto-join default room
            join_room("neurons")
            self.client_rooms[client_id] = "neurons"

            # Send welcome message
            emit("connected", {
                "client_id": client_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Connected to neuron live updates"
            })
        
        @self.socketio.on("disconnect")
        def handle_disconnect():
            """Handle client disconnection."""
            if request is None:
                return
            client_id = request.sid
            self.connected_clients.discard(client_id)
            if client_id in self.client_rooms:
                del self.client_rooms[client_id]
            _LOGGER.info("Client disconnected: %s", client_id)
        
        @self.socketio.on("subscribe")
        def handle_subscribe(data):
            """Handle subscription to specific neuron or room.
            
            Args:
                data: {"room": "neurons" or neuron_id}
            """
            if request is None:
                return
            client_id = request.sid
            room = data.get("room", "neurons")
            
            # Validate room name
            if not validate_room_name(room):
                _LOGGER.warning("Client %s attempted to join invalid room: %s", client_id, room)
                emit("error", {"message": "Invalid room name format"})
                return
            
            # Leave current room
            if client_id in self.client_rooms:
                leave_room(self.client_rooms[client_id])
            
            # Join new room
            join_room(room)
            self.client_rooms[client_id] = room
            
            _LOGGER.info("Client %s subscribed to %s", client_id, room)
            emit("subscribed", {"room": room})
        
        @self.socketio.on("unsubscribe")
        def handle_unsubscribe(data):
            """Handle unsubscription.

            Args:
                data: {"room": "neurons" or neuron_id}
            """
            if request is None:
                return
            client_id = request.sid
            room = data.get("room", "neurons")

            # Validate room name
            if not validate_room_name(room):
                _LOGGER.warning("Client %s attempted to leave invalid room: %s", client_id, room)
                emit("error", {"message": "Invalid room name format"})
                return

            leave_room(room)
            _LOGGER.info("Client %s unsubscribed from %s", client_id, room)
    
    def broadcast_neuron_update(self, neuron_id: str, data: Dict[str, Any]):
        """Broadcast a neuron state update.
        
        Args:
            neuron_id: ID of the updated neuron
            data: Update data including state, value, confidence, etc.
        """
        if not self.socketio:
            return
        
        payload = {
            "event": EVENT_NEURON_UPDATE,
            "neuron_id": neuron_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }
        
        self.socketio.emit(EVENT_NEURON_UPDATE, payload, room="neurons")
        _LOGGER.debug("Broadcast neuron update: %s", neuron_id)
    
    def broadcast_neuron_fire(self, neuron_id: str, value: float, confidence: float):
        """Broadcast a neuron fire event.
        
        Args:
            neuron_id: ID of the firing neuron
            value: Activation value
            confidence: Confidence score
        """
        if not self.socketio:
            return
        
        payload = {
            "event": EVENT_NEURON_FIRE,
            "neuron_id": neuron_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "value": value,
                "confidence": confidence,
                "firing": True
            }
        }
        
        self.socketio.emit(EVENT_NEURON_FIRE, payload, room="neurons")
        _LOGGER.debug("Broadcast neuron fire: %s (value=%s)", neuron_id, value)
    
    def broadcast_graph_update(self, graph_data: Dict[str, Any]):
        """Broadcast a complete graph update.
        
        Args:
            graph_data: Full graph data (nodes + edges)
        """
        if not self.socketio:
            return
        
        payload = {
            "event": EVENT_GRAPH_UPDATE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": graph_data
        }
        
        self.socketio.emit(EVENT_GRAPH_UPDATE, payload, room="neurons")
        _LOGGER.debug("Broadcast graph update")
    
    def broadcast_mood_change(self, mood: str, confidence: float, mood_values: Dict[str, float]):
        """Broadcast a mood change event.
        
        Args:
            mood: New dominant mood
            confidence: Confidence score
            mood_values: All mood values
        """
        if not self.socketio:
            return
        
        payload = {
            "event": EVENT_MOOD_CHANGE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "mood": mood,
                "confidence": confidence,
                "mood_values": mood_values
            }
        }
        
        self.socketio.emit(EVENT_MOOD_CHANGE, payload, room="neurons")
        _LOGGER.info("Broadcast mood change: %s (confidence=%s)", mood, confidence)
    
    def broadcast_suggestion(self, suggestion: Dict[str, Any]):
        """Broadcast a new suggestion.
        
        Args:
            suggestion: Suggestion data
        """
        if not self.socketio:
            return
        
        payload = {
            "event": EVENT_SUGGESTION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": suggestion
        }
        
        self.socketio.emit(EVENT_SUGGESTION, payload, room="neurons")
        _LOGGER.debug("Broadcast suggestion: %s", suggestion.get("action", "unknown"))
    
    def get_connected_count(self) -> int:
        """Get number of connected clients."""
        return len(self.connected_clients)
    
    def get_client_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get info about a specific client.
        
        Args:
            client_id: Client session ID
        
        Returns:
            Client info dict or None
        """
        if client_id not in self.connected_clients:
            return None
        
        return {
            "client_id": client_id,
            "room": self.client_rooms.get(client_id, "neurons"),
            "connected": True
        }


# Singleton instance
_ws_handler: Optional[NeuronWebSocketHandler] = None


def get_neuron_ws_handler() -> NeuronWebSocketHandler:
    """Get the singleton WebSocket handler instance."""
    global _ws_handler
    if _ws_handler is None:
        _ws_handler = NeuronWebSocketHandler()
    return _ws_handler


def init_neuron_websocket(socketio: SocketIO):
    """Initialize the neuron WebSocket handler.
    
    Args:
        socketio: Flask-SocketIO instance
    """
    handler = get_neuron_ws_handler()
    handler.init_app(socketio)
    _LOGGER.info("Neuron WebSocket handler initialized")


__all__ = [
    "NeuronWebSocketHandler",
    "get_neuron_ws_handler",
    "init_neuron_websocket",
    "EVENT_NEURON_UPDATE",
    "EVENT_NEURON_FIRE",
    "EVENT_GRAPH_UPDATE",
    "EVENT_MOOD_CHANGE",
    "EVENT_SUGGESTION"
]
