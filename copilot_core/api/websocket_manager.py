"""WebSocket Manager — Connection pooling, rooms, broadcasting."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Optional, Callable
import time

logger = logging.getLogger(__name__)


@dataclass
class WSConnection:
    id: str
    user_id: str
    rooms: Set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=lambda: time.time())
    last_activity: float = field(default_factory=lambda: time.time())
    metadata: Dict[str, Any] = field(default_factory=dict)


class WebSocketManager:
    """Manages WebSocket connections, rooms, and message broadcasting."""

    def __init__(self, max_connections: int = 10000):
        self._max_connections = max_connections
        self._connections: Dict[str, WSConnection] = {}
        self._rooms: Dict[str, Set[str]] = {}
        self._message_handlers: Dict[str, Callable] = {}

    def connect(self, connection_id: str, user_id: str, metadata: Optional[Dict] = None) -> bool:
        """Accept a new WebSocket connection."""
        if len(self._connections) >= self._max_connections:
            return False

        conn = WSConnection(
            id=connection_id,
            user_id=user_id,
            metadata=metadata or {}
        )
        self._connections[connection_id] = conn
        logger.info(f"WS connected: {connection_id} (user: {user_id})")
        return True

    def disconnect(self, connection_id: str):
        """Handle connection disconnect."""
        if connection_id in self._connections:
            conn = self._connections[connection_id]
            # Remove from all rooms
            for room in conn.rooms:
                if room in self._rooms:
                    self._rooms[room].discard(connection_id)
            del self._connections[connection_id]
            logger.info(f"WS disconnected: {connection_id}")

    def join_room(self, connection_id: str, room: str):
        """Add connection to a room."""
        if connection_id not in self._connections:
            return

        conn = self._connections[connection_id]
        conn.rooms.add(room)

        if room not in self._rooms:
            self._rooms[room] = set()
        self._rooms[room].add(connection_id)
        logger.info(f"WS {connection_id} joined room: {room}")

    def leave_room(self, connection_id: str, room: str):
        """Remove connection from a room."""
        if connection_id in self._connections:
            self._connections[connection_id].rooms.discard(room)
        if room in self._rooms:
            self._rooms[room].discard(connection_id)

    def broadcast_to_room(self, room: str, message: Dict, exclude: Optional[List[str]] = None):
        """Broadcast message to all connections in a room."""
        if room not in self._rooms:
            return

        exclude = exclude or []
        for conn_id in self._rooms[room]:
            if conn_id not in exclude:
                self._send_to_connection(conn_id, message)

    def broadcast_all(self, message: Dict):
        """Broadcast to all connected clients."""
        for conn_id in self._connections:
            self._send_to_connection(conn_id, message)

    def _send_to_connection(self, connection_id: str, message: Dict):
        """Send message to specific connection."""
        conn = self._connections.get(connection_id)
        if conn:
            conn.last_activity = time.time()
        logger.debug(f"WS send to {connection_id}: {message.get('type', 'unknown')}")

    def register_message_handler(self, message_type: str, handler: Callable):
        """Register handler for message type."""
        self._message_handlers[message_type] = handler

    def get_room_members(self, room: str) -> List[str]:
        """Get all connection IDs in a room."""
        return list(self._rooms.get(room, set()))

    def get_connection_count(self) -> int:
        """Get total connection count."""
        return len(self._connections)

    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket statistics."""
        return {
            "total_connections": len(self._connections),
            "total_rooms": len(self._rooms),
            "room_distribution": {room: len(members) for room, members in self._rooms.items()},
        }


# Global default WS manager
default_ws_manager: Optional[WebSocketManager] = None


def init_ws_manager() -> WebSocketManager:
    global default_ws_manager
    default_ws_manager = WebSocketManager()
    return default_ws_manager
