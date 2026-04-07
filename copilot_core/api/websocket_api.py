"""P5-002: WebSocket API — Real-Time Events, Subscriptions."""
from __future__ import annotations

import logging
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class WSMessageType(Enum):
    """WebSocket message types."""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    EVENT = "event"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class WSChannel(Enum):
    """WebSocket channels."""
    SYSTEM = "system"
    EVENTS = "events"
    VOICE = "voice"
    ML = "ml"
    USER = "user"


@dataclass
class WSMessage:
    """WebSocket message."""
    type: WSMessageType
    channel: WSChannel
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "channel": self.channel.value,
            "data": self.data,
            "timestamp": self.timestamp
        })


@dataclass
class WSSubscription:
    """WebSocket subscription."""
    client_id: str
    channel: WSChannel
    filters: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class WebSocketAPI:
    """WebSocket API for real-time communication."""

    def __init__(self):
        self._clients: Dict[str, Any] = {}  # client_id -> ws_connection
        self._subscriptions: Dict[str, List[WSSubscription]] = {}  # channel -> subscriptions
        self._event_handlers: Dict[WSChannel, List[Callable]] = {}

    def register_client(self, client_id: str, ws_connection: Any):
        """Register a WebSocket client."""
        self._clients[client_id] = ws_connection
        logger.info(f"WebSocket client registered: {client_id}")

    def unregister_client(self, client_id: str):
        """Unregister a WebSocket client."""
        if client_id in self._clients:
            del self._clients[client_id]
        # Remove subscriptions
        for channel_subs in self._subscriptions.values():
            channel_subs[:] = [s for s in channel_subs if s.client_id != client_id]
        logger.info(f"WebSocket client unregistered: {client_id}")

    def subscribe(self, client_id: str, channel: WSChannel, filters: Optional[Dict] = None):
        """Subscribe client to a channel."""
        subscription = WSSubscription(
            client_id=client_id,
            channel=channel,
            filters=filters or {}
        )
        
        if channel.value not in self._subscriptions:
            self._subscriptions[channel.value] = []
        self._subscriptions[channel.value].append(subscription)
        
        logger.info(f"Client {client_id} subscribed to {channel.value}")

    def unsubscribe(self, client_id: str, channel: WSChannel):
        """Unsubscribe client from a channel."""
        if channel.value in self._subscriptions:
            self._subscriptions[channel.value] = [
                s for s in self._subscriptions[channel.value] if s.client_id != client_id
            ]

    def broadcast(self, channel: WSChannel, message: WSMessage):
        """Broadcast message to all subscribers of a channel."""
        if channel.value not in self._subscriptions:
            return
        
        for subscription in self._subscriptions[channel.value]:
            self._send_to_client(subscription.client_id, message)

    def _send_to_client(self, client_id: str, message: WSMessage):
        """Send message to a specific client."""
        if client_id not in self._clients:
            return
        
        try:
            ws = self._clients[client_id]
            # ws.send(message.to_json())
            logger.debug(f"Sent to {client_id}: {message.type.value}")
        except Exception as e:
            logger.error(f"Failed to send to {client_id}: {e}")
            self.unregister_client(client_id)

    def emit_event(self, channel: WSChannel, event_type: str, data: Dict[str, Any]):
        """Emit an event to a channel."""
        message = WSMessage(
            type=WSMessageType.EVENT,
            channel=channel,
            data={"event_type": event_type, **data}
        )
        self.broadcast(channel, message)

    def register_handler(self, channel: WSChannel, handler: Callable):
        """Register event handler for a channel."""
        if channel not in self._event_handlers:
            self._event_handlers[channel] = []
        self._event_handlers[channel].append(handler)

    def handle_message(self, client_id: str, raw_message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(raw_message)
            msg_type = WSMessageType(data.get("type", "event"))
            channel = WSChannel(data.get("channel", "system"))
            
            if msg_type == WSMessageType.SUBSCRIBE:
                self.subscribe(client_id, channel, data.get("filters"))
            elif msg_type == WSMessageType.UNSUBSCRIBE:
                self.unsubscribe(client_id, channel)
            elif msg_type == WSMessageType.PING:
                self._send_to_client(client_id, WSMessage(WSMessageType.PONG, channel, {}))
            
            # Call handlers
            for handler in self._event_handlers.get(channel, []):
                try:
                    handler(client_id, data)
                except Exception as e:
                    logger.error(f"Handler failed: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")
            error_msg = WSMessage(WSMessageType.ERROR, WSChannel.SYSTEM, {"error": str(e)})
            self._send_to_client(client_id, error_msg)

    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket API statistics."""
        return {
            "connected_clients": len(self._clients),
            "subscriptions": {ch: len(subs) for ch, subs in self._subscriptions.items()},
            "registered_handlers": sum(len(h) for h in self._event_handlers.values()),
        }


# Global default WebSocket API
default_ws_api: Optional[WebSocketAPI] = None


def init_websocket_api() -> WebSocketAPI:
    """Initialize global WebSocket API."""
    global default_ws_api
    default_ws_api = WebSocketAPI()
    return default_ws_api
