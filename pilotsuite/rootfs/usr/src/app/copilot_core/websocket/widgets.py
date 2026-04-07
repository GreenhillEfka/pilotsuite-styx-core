"""WebSocket Widget Channels — Slice 176 Live Updates."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Set

_LOGGER = logging.getLogger(__name__)


class WidgetWebSocketManager:
    """Manages WebSocket connections for dashboard widgets."""
    
    def __init__(self):
        self._connections: Dict[str, Set[Any]] = {}
        self._subscriptions: Dict[str, Set[str]] = {}
    
    def subscribe(self, client: Any, widget_type: str, widget_id: str):
        """Subscribe client to widget updates."""
        channel = f"widget:{widget_type}:{widget_id}"
        if channel not in self._connections:
            self._connections[channel] = set()
            self._subscriptions[channel] = set()
        self._connections[channel].add(client)
        self._subscriptions[channel].add(widget_id)
        _LOGGER.debug(f"Client subscribed to {channel}")
    
    def unsubscribe(self, client: Any, widget_type: str, widget_id: str):
        """Unsubscribe client from widget updates."""
        channel = f"widget:{widget_type}:{widget_id}"
        if channel in self._connections:
            self._connections[channel].discard(client)
    
    async def broadcast(self, widget_type: str, widget_id: str, data: Dict[str, Any]):
        """Broadcast update to all subscribers."""
        channel = f"widget:{widget_type}:{widget_id}"
        if channel not in self._connections:
            return
        
        message = json.dumps({
            "type": "widget_update",
            "widget_type": widget_type,
            "widget_id": widget_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        for client in self._connections[channel]:
            try:
                await client.send(message)
            except Exception as e:
                _LOGGER.warning(f"Failed to send to WebSocket client: {e}")


# Global instance
_widget_ws_manager: WidgetWebSocketManager | None = None


def get_widget_ws_manager() -> WidgetWebSocketManager:
    """Get the global WidgetWebSocketManager instance."""
    global _widget_ws_manager
    if _widget_ws_manager is None:
        _widget_ws_manager = WidgetWebSocketManager()
    return _widget_ws_manager


# ── Entity Change Handler ─────────────────────────────────

async def handle_entity_change(entity_id: str, old_state: Any, new_state: Any):
    """Broadcast entity changes to subscribed widgets."""
    manager = get_widget_ws_manager()
    
    # Notify entity_grid widgets
    await manager.broadcast("entity_grid", "*", {
        "entity_id": entity_id,
        "state": new_state
    })
    
    # Notify floorplan widgets if entity is on floorplan
    await manager.broadcast("floorplan", "*", {
        "type": "entity_update",
        "entity_id": entity_id,
        "state": new_state
    })
