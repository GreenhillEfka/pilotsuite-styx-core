"""WebSocket Handler for PilotSuite real-time updates.

Provides WebSocket support for:
- Live mood updates
- Neuron state changes
- Brain pipeline events
- Real-time dashboard updates
"""
from __future__ import annotations

import json
import logging
import queue
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum

try:
    from flask_socketio import SocketIO, emit, join_room, leave_room
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    _LOGGER = logging.getLogger(__name__)
    _LOGGER.warning("flask-socketio not available - WebSocket support disabled")

from copilot_core.mood.live_engine import LiveMoodState, MoodScore3D, get_live_mood_engine
from copilot_core.neurons.manager import get_neuron_manager

_LOGGER = logging.getLogger(__name__)

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


class EventType(str, Enum):
    """WebSocket event types."""
    MOOD_UPDATE = "mood_update"
    NEURON_FIRE = "neuron_fire"
    NEURON_STATE_CHANGE = "neuron_state_change"
    GRAPH_UPDATE = "graph_update"
    PIPELINE_UPDATE = "pipeline_update"
    SUGGESTION = "suggestion"
    SYSTEM_STATUS = "system_status"
    ERROR = "error"


@dataclass
class WebSocketEvent:
    """WebSocket event structure.
    
    Attributes:
        event_type: Type of event
        data: Event payload
        timestamp: When event occurred
        room: Target room/channel
    """
    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    room: str = "general"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "room": self.room
        }


def build_graph_update_payload(graph_stats: Dict[str, Any], event: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Project brain-graph stats into the bounded live dashboard payload.
    
    Enriches event_data with canvas-actionable delta fields:
    - node_id / edge_id / pruned_stats: exact change targets
    - change_type: "node_added" | "node_updated" | "edge_added" | "edge_updated" | "pruned"
    This lets canvas consumers highlight exact graph element deltas, not only summary counts.
    """
    graph_stats = graph_stats or {}
    event = event or {}
    event_type = event.get("event") or None
    raw_data = event.get("data") if isinstance(event.get("data"), dict) else {}
    event_timestamp_ms = event.get("timestamp_ms") if event else None

    # Derive canvas-actionable delta fields from event type
    node_id = None
    edge_id = None
    pruned_stats = None
    change_type = None

    if event_type == "node_updated":
        node_id = raw_data.get("id")
        change_type = "node_updated"
    elif event_type == "edge_updated":
        edge_id = raw_data.get("id")
        change_type = "edge_updated"
    elif event_type == "graph_pruned":
        pruned_stats = {
            "nodes_removed": raw_data.get("nodes_removed", 0),
            "edges_removed": raw_data.get("edges_removed", 0),
        }
        change_type = "pruned"

    return {
        "nodes": int(graph_stats.get("nodes") or graph_stats.get("node_count") or 0),
        "edges": int(graph_stats.get("edges") or graph_stats.get("edge_count") or 0),
        "max_nodes": int(graph_stats.get("max_nodes") or 0),
        "max_edges": int(graph_stats.get("max_edges") or 0),
        "source_event": event_type,
        "event_timestamp_ms": event_timestamp_ms,
        "event_data": raw_data,
        # Canvas-actionable delta fields
        "delta": {
            "change_type": change_type,
            "node_id": node_id,
            "edge_id": edge_id,
            "pruned_stats": pruned_stats,
        },
    }


class WebSocketHandler:
    """Handler for WebSocket connections and events.
    
    Manages:
    - Client connections
    - Event broadcasting
    - Room management
    - Event filtering
    """
    
    def __init__(self, socketio: Optional[SocketIO] = None):
        """Initialize WebSocket handler.
        
        Args:
            socketio: Flask-SocketIO instance
        """
        self.socketio = socketio
        self._connections: Set[str] = set()
        self._rooms: Dict[str, Set[str]] = {}
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        self._graph_bridge_stop = threading.Event()
        self._graph_bridge_thread: Optional[threading.Thread] = None
        
        if socketio:
            self._register_handlers()
        
        _LOGGER.info("WebSocketHandler initialized (connections=%d)", len(self._connections))
    
    def _register_handlers(self) -> None:
        """Register SocketIO event handlers."""
        if not self.socketio:
            return
        
        @self.socketio.on('connect')
        def handle_connect(auth=None):
            """Handle client connection with authentication.

            Token is resolved from (in order):
            1. SocketIO native ``auth`` dict (``{'token': '...'}``).
            2. Query parameter ``?token=xxx``.
            3. ``X-Auth-Token`` header.

            Connections without a valid token are **rejected**.
            """
            from copilot_core.api.security import validate_websocket_token, get_auth_token
            import hmac as _hmac

            sid = request.sid if hasattr(request, 'sid') else 'unknown'

            # --- authenticate ---------------------------------------------------
            authenticated = False
            configured_token = get_auth_token()

            if not configured_token:
                # No token configured – reject (secure default)
                _LOGGER.warning(
                    "WebSocket connection rejected (no token configured): %s", sid
                )
                return False

            # 1. SocketIO auth dict
            if auth and isinstance(auth, dict) and 'token' in auth:
                candidate = str(auth['token']).strip()
                if candidate and _hmac.compare_digest(candidate, configured_token):
                    authenticated = True

            # 2+3. Query param / X-Auth-Token header (via helper)
            if not authenticated:
                authenticated = validate_websocket_token(request)

            if not authenticated:
                _LOGGER.warning(
                    "WebSocket authentication failed – connection rejected: %s", sid
                )
                return False
            # -----------------------------------------------------------------

            self._connections.add(sid)
            _LOGGER.info("WebSocket client connected: %s (total=%d)", sid, len(self._connections))

            # Send welcome message
            emit('system_status', {
                'status': 'connected',
                'message': 'Welcome to PilotSuite WebSocket',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            sid = request.sid if hasattr(request, 'sid') else 'unknown'
            self._connections.discard(sid)
            _LOGGER.info("WebSocket client disconnected: %s (total=%d)", sid, len(self._connections))
        
        @self.socketio.on('join_room')
        def handle_join(data):
            """Handle room join request."""
            room = data.get('room', 'general')
            
            # Validate room name
            if not validate_room_name(room):
                _LOGGER.warning("Invalid room name rejected: %s", room)
                emit('error', {'message': f'Invalid room name: {room}'})
                return
            
            join_room(room)
            
            if room not in self._rooms:
                self._rooms[room] = set()
            
            sid = request.sid if hasattr(request, 'sid') else 'unknown'
            self._rooms[room].add(sid)
            
            _LOGGER.info("Client %s joined room %s", sid, room)
        
        @self.socketio.on('leave_room')
        def handle_leave(data):
            """Handle room leave request."""
            room = data.get('room', 'general')
            leave_room(room)
            
            if room in self._rooms:
                sid = request.sid if hasattr(request, 'sid') else 'unknown'
                self._rooms[room].discard(sid)
            
            _LOGGER.info("Client left room %s", room)
        
        @self.socketio.on('subscribe')
        def handle_subscribe(data):
            """Handle subscription request."""
            event_type = data.get('event_type')
            if event_type:
                try:
                    et = EventType(event_type)
                    if et not in self._event_handlers:
                        self._event_handlers[et] = []
                    _LOGGER.info("Client subscribed to %s", et.value)
                except ValueError:
                    emit('error', {'message': f'Invalid event type: {event_type}'})
    
    def emit_event(self, event: WebSocketEvent) -> None:
        """Emit an event to clients.
        
        Args:
            event: Event to emit
        """
        if not self.socketio:
            _LOGGER.debug("No socketio instance - skipping event emit")
            return
        
        try:
            event_dict = event.to_dict()
            
            if event.room == "general":
                # Broadcast to all
                self.socketio.emit(event.event_type.value, event_dict)
            else:
                # Send to specific room
                self.socketio.emit(event.event_type.value, event_dict, room=event.room)
            
            _LOGGER.debug(
                "Emitted event %s to room %s (data_size=%d)",
                event.event_type.value, event.room, len(json.dumps(event_dict))
            )
        except Exception as e:
            _LOGGER.error("Error emitting event: %s", e)
    
    def broadcast_mood_update(self, mood_state: LiveMoodState) -> None:
        """Broadcast mood update to all clients.
        
        Args:
            mood_state: New mood state
        """
        event = WebSocketEvent(
            event_type=EventType.MOOD_UPDATE,
            data=mood_state.to_dict(),
            room="mood"
        )
        self.emit_event(event)
        
        # Also send to general room
        event.room = "general"
        self.emit_event(event)
    
    def broadcast_neuron_fire(self, neuron_name: str, neuron_data: Dict[str, Any]) -> None:
        """Broadcast neuron fire event.
        
        Args:
            neuron_name: Name of firing neuron
            neuron_data: Neuron state data
        """
        event = WebSocketEvent(
            event_type=EventType.NEURON_FIRE,
            data={
                "neuron_name": neuron_name,
                "firing": True,
                "state": neuron_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            room="neurons"
        )
        self.emit_event(event)
    
    def broadcast_neuron_state_change(self, neuron_name: str, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> None:
        """Broadcast neuron state change.
        
        Args:
            neuron_name: Name of neuron
            old_state: Previous state
            new_state: New state
        """
        event = WebSocketEvent(
            event_type=EventType.NEURON_STATE_CHANGE,
            data={
                "neuron_name": neuron_name,
                "old_state": old_state,
                "new_state": new_state,
                "changed_fields": self._get_changed_fields(old_state, new_state),
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            room="neurons"
        )
        self.emit_event(event)
    
    def broadcast_graph_update(self, graph_data: Dict[str, Any]) -> None:
        """Broadcast a bounded brain-graph summary update to live dashboard clients."""
        event = WebSocketEvent(
            event_type=EventType.GRAPH_UPDATE,
            data=graph_data,
            room="neurons"
        )
        self.emit_event(event)

    def broadcast_pipeline_update(self, pipeline_data: Dict[str, Any]) -> None:
        """Broadcast pipeline update.
        
        Args:
            pipeline_data: Pipeline status data
        """
        event = WebSocketEvent(
            event_type=EventType.PIPELINE_UPDATE,
            data=pipeline_data,
            room="pipeline"
        )
        self.emit_event(event)
    
    def broadcast_suggestion(self, suggestion: Dict[str, Any]) -> None:
        """Broadcast suggestion.
        
        Args:
            suggestion: Suggestion data
        """
        event = WebSocketEvent(
            event_type=EventType.SUGGESTION,
            data=suggestion,
            room="suggestions"
        )
        self.emit_event(event)
    
    def _get_changed_fields(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        """Get list of changed fields between two dicts.
        
        Args:
            old: Old dictionary
            new: New dictionary
        
        Returns:
            List of changed field names
        """
        changed = []
        all_keys = set(old.keys()) | set(new.keys())
        
        for key in all_keys:
            if old.get(key) != new.get(key):
                changed.append(key)
        
        return changed
    
    def get_connection_count(self) -> int:
        """Get number of active connections.
        
        Returns:
            Number of connections
        """
        return len(self._connections)
    
    def get_room_members(self, room: str) -> int:
        """Get number of members in a room.
        
        Args:
            room: Room name
        
        Returns:
            Number of members
        """
        return len(self._rooms.get(room, set()))
    
    def attach_brain_graph_service(self, brain_graph_service: Any) -> None:
        """Bridge BrainGraph SSE events onto the existing live Socket.IO channel."""
        if not self.socketio or brain_graph_service is None:
            return
        if self._graph_bridge_thread is not None and self._graph_bridge_thread.is_alive():
            return

        subscriber = brain_graph_service.subscribe_sse()
        self._graph_bridge_stop.clear()

        def _bridge_loop() -> None:
            try:
                while not self._graph_bridge_stop.is_set():
                    try:
                        event = subscriber.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    latest_event = event
                    while True:
                        try:
                            latest_event = subscriber.get_nowait()
                        except queue.Empty:
                            break

                    try:
                        payload = build_graph_update_payload(
                            brain_graph_service.get_stats(),
                            latest_event,
                        )
                        self.broadcast_graph_update(payload)
                    except Exception:
                        _LOGGER.exception("Brain graph live bridge emit failed")
            finally:
                brain_graph_service.unsubscribe_sse(subscriber)

        self._graph_bridge_thread = threading.Thread(
            target=_bridge_loop,
            name="brain-graph-ws-bridge",
            daemon=True,
        )
        self._graph_bridge_thread.start()
        _LOGGER.info("Brain graph live bridge enabled")

    def cleanup(self) -> None:
        """Cleanup resources."""
        self._graph_bridge_stop.set()
        self._connections.clear()
        self._rooms.clear()
        self._event_handlers.clear()
        _LOGGER.info("WebSocketHandler cleaned up")


# Singleton instance
_websocket_handler: Optional[WebSocketHandler] = None
_socketio_instance: Optional[SocketIO] = None


def init_websocket(app) -> WebSocketHandler:
    """Initialize WebSocket support for a Flask app.
    
    Args:
        app: Flask application
    
    Returns:
        WebSocketHandler instance
    """
    global _websocket_handler, _socketio_instance
    
    if not SOCKETIO_AVAILABLE:
        _LOGGER.warning("WebSocket support not available (flask-socketio not installed)")
        return None
    
    try:
        # Initialize SocketIO
        _socketio_instance = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode="threading",
            logger=False,
            engineio_logger=False
        )
        
        # Create handler
        _websocket_handler = WebSocketHandler(_socketio_instance)
        
        # Setup real-time callbacks
        _setup_realtime_callbacks(app)
        
        _LOGGER.info("WebSocket initialized successfully")
        return _websocket_handler
    
    except Exception as e:
        _LOGGER.error("Failed to initialize WebSocket: %s", e)
        return None


def _setup_realtime_callbacks(app=None) -> None:
    """Setup callbacks for real-time updates."""
    if not _websocket_handler:
        return
    
    # Subscribe to mood updates
    mood_engine = get_live_mood_engine()
    mood_engine.on_update(_websocket_handler.broadcast_mood_update)

    if app is not None:
        try:
            services = app.config.get("COPILOT_SERVICES", {}) or {}
            brain_graph_service = services.get("brain_graph_service")
            if brain_graph_service is not None:
                _websocket_handler.attach_brain_graph_service(brain_graph_service)
        except Exception as e:
            _LOGGER.warning("Could not setup brain graph live bridge: %s", e)
    
    # Subscribe to neuron updates (would need callback support in NeuronManager)
    try:
        manager = get_neuron_manager()
        # Register callback for neuron state changes
        # This would require adding callback support to NeuronManager
    except Exception as e:
        _LOGGER.warning("Could not setup neuron callbacks: %s", e)


def get_websocket_handler() -> Optional[WebSocketHandler]:
    """Get the WebSocket handler instance.
    
    Returns:
        WebSocketHandler instance or None
    """
    return _websocket_handler


def get_socketio() -> Optional[SocketIO]:
    """Get the SocketIO instance.
    
    Returns:
        SocketIO instance or None
    """
    return _socketio_instance


# Fallback request object for standalone usage
class _MockRequest:
    sid = 'standalone'


try:
    from flask import request
except ImportError:
    request = _MockRequest()


__all__ = [
    "EventType",
    "WebSocketEvent",
    "WebSocketHandler",
    "build_graph_update_payload",
    "init_websocket",
    "get_websocket_handler",
    "get_socketio"
]
