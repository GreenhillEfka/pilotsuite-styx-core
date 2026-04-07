"""HomeAssistant Event Handler & Subscription Manager.

Provides event subscription, routing, and throttling for HomeAssistant events:
- Event subscription management
- Event queue with throttling (100ms default)
- Event routing to specific handlers
- Event history tracking (last 100 events)
- Socket.IO broadcast integration
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional, List, Dict, Set
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Supported HomeAssistant event types."""
    STATE_CHANGED = "state_changed"
    CALL_SERVICE = "call_service"
    AREA_REGISTRY_UPDATED = "area_registry_updated"
    DEVICE_REGISTRY_UPDATED = "device_registry_updated"
    ENTITY_REGISTRY_UPDATED = "entity_registry_updated"
    SERVICE_REGISTERED = "service_registered"
    SERVICE_REMOVED = "service_removed"
    COMPONENT_LOADED = "component_loaded"
    THEME_UPDATED = "theme_updated"
    CUSTOM = "custom"


@dataclass
class HAEvent:
    """Represents a HomeAssistant event."""
    
    event_type: str
    data: dict[str, Any]
    origin: str = "LOCAL"
    time_fired: Optional[datetime] = None
    received_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "origin": self.origin,
            "time_fired": self.time_fired.isoformat() if self.time_fired else None,
            "received_at": self.received_at.isoformat()
        }


@dataclass
class EventSubscription:
    """Event subscription configuration."""
    
    event_type: str
    handlers: List[Callable[[HAEvent], None]] = field(default_factory=list)
    throttle_ms: int = 100
    enabled: bool = True


class EventQueue:
    """Thread-safe event queue with throttling."""
    
    def __init__(self, max_size: int = 1000, throttle_ms: int = 100):
        self._queue: asyncio.Queue[HAEvent] = asyncio.Queue(maxsize=max_size)
        self._throttle_ms = throttle_ms
        self._last_emit_time: Dict[str, datetime] = {}
        self._dropped_count: Dict[str, int] = {}
        self._lock = asyncio.Lock()
    
    async def put(self, event: HAEvent) -> bool:
        """Add event to queue with throttling.
        
        Args:
            event: Event to add
        
        Returns:
            True if event was queued, False if dropped due to throttling.
        """
        event_key = f"{event.event_type}:{self._get_event_identifier(event)}"
        now = datetime.now()
        
        async with self._lock:
            # Check throttling
            last_time = self._last_emit_time.get(event_key)
            
            if last_time:
                elapsed_ms = (now - last_time).total_seconds() * 1000
                
                if elapsed_ms < self._throttle_ms:
                    # Throttled - drop event
                    self._dropped_count[event_key] = self._dropped_count.get(event_key, 0) + 1
                    
                    if self._dropped_count[event_key] % 100 == 0:
                        logger.debug(
                            f"Throttled {self._dropped_count[event_key]} events "
                            f"for {event_key} (throttle: {self._throttle_ms}ms)"
                        )
                    
                    return False
            
            # Queue event
            try:
                self._queue.put_nowait(event)
                self._last_emit_time[event_key] = now
                
                # Reset dropped count
                if event_key in self._dropped_count:
                    del self._dropped_count[event_key]
                
                return True
            
            except asyncio.QueueFull:
                logger.warning(f"Event queue full, dropping event: {event.event_type}")
                return False
    
    def _get_event_identifier(self, event: HAEvent) -> str:
        """Extract identifier from event for throttling key."""
        data = event.data
        
        # State changed events - use entity_id
        if event.event_type == "state_changed":
            return data.get("entity_id", "unknown")
        
        # Call service events - use domain.service
        elif event.event_type == "call_service":
            domain = data.get("domain", "unknown")
            service = data.get("service", "unknown")
            return f"{domain}.{service}"
        
        # Registry updates - use id
        elif "registry_id" in data:
            return str(data["registry_id"])
        
        # Default - use event type
        return event.event_type
    
    async def get(self, timeout: Optional[float] = None) -> Optional[HAEvent]:
        """Get next event from queue.
        
        Args:
            timeout: Maximum time to wait for event
        
        Returns:
            Next event, or None if timeout
        """
        try:
            if timeout:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            else:
                return await self._queue.get()
        except asyncio.TimeoutError:
            return None
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
    
    def qsize(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    @property
    def throttle_ms(self) -> int:
        """Get current throttle setting."""
        return self._throttle_ms
    
    @throttle_ms.setter
    def throttle_ms(self, value: int) -> None:
        """Set throttle interval in milliseconds."""
        self._throttle_ms = max(0, value)


class EventHistory:
    """Event history tracker (last N events)."""
    
    def __init__(self, max_events: int = 100):
        self._history: deque[HAEvent] = deque(maxlen=max_events)
        self._lock = asyncio.Lock()
    
    async def add(self, event: HAEvent) -> None:
        """Add event to history."""
        async with self._lock:
            self._history.append(event)
    
    async def get_recent(self, limit: int = 100) -> List[HAEvent]:
        """Get recent events from history.
        
        Args:
            limit: Maximum number of events to return
        
        Returns:
            List of recent events (most recent first)
        """
        async with self._lock:
            events = list(self._history)
            events.reverse()  # Most recent first
            return events[:limit]
    
    async def get_by_type(self, event_type: str, limit: int = 50) -> List[HAEvent]:
        """Get recent events of specific type.
        
        Args:
            event_type: Event type to filter
            limit: Maximum number of events to return
        
        Returns:
            List of matching events (most recent first)
        """
        async with self._lock:
            events = [
                e for e in self._history
                if e.event_type == event_type
            ]
            events.reverse()
            return events[:limit]
    
    async def clear(self) -> None:
        """Clear event history."""
        async with self._lock:
            self._history.clear()
    
    @property
    def size(self) -> int:
        """Get current history size."""
        return len(self._history)
    
    @property
    def max_size(self) -> int:
        """Get maximum history size."""
        return self._history.maxlen


class EventHandler:
    """HomeAssistant event handler with subscription and routing."""
    
    def __init__(self, throttle_ms: int = 100, history_size: int = 100):
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._queue = EventQueue(throttle_ms=throttle_ms)
        self._history = EventHistory(max_events=history_size)
        self._running = False
        self._process_task: Optional[asyncio.Task] = None
        self._socketio_server = None
        self._socketio_room = "ha_events"
        self._lock = asyncio.Lock()
    
    def set_socketio_server(self, server) -> None:
        """Set Socket.IO server for broadcasting events.
        
        Args:
            server: Flask-SocketIO server instance
        """
        self._socketio_server = server
        logger.info("Socket.IO server configured for event broadcasting")
    
    def set_socketio_room(self, room: str) -> None:
        """Set Socket.IO room for event broadcasting.
        
        Args:
            room: Room name for broadcasting
        """
        self._socketio_room = room
    
    async def subscribe(
        self,
        event_type: str,
        handler: Optional[Callable[[HAEvent], None]] = None,
        throttle_ms: int = 100
    ) -> None:
        """Subscribe to an event type.
        
        Args:
            event_type: HomeAssistant event type (e.g., "state_changed")
            handler: Optional callback function for event handling
            throttle_ms: Throttle interval in milliseconds
        """
        async with self._lock:
            if event_type not in self._subscriptions:
                self._subscriptions[event_type] = EventSubscription(
                    event_type=event_type,
                    throttle_ms=throttle_ms
                )
                logger.info(f"Created subscription for event: {event_type}")
            else:
                # Update throttle if different
                if throttle_ms != self._subscriptions[event_type].throttle_ms:
                    self._subscriptions[event_type].throttle_ms = throttle_ms
            
            # Add handler if provided
            if handler and handler not in self._subscriptions[event_type].handlers:
                self._subscriptions[event_type].handlers.append(handler)
                logger.debug(f"Added handler to {event_type} (total: {len(self._subscriptions[event_type].handlers)})")
    
    async def unsubscribe(
        self,
        event_type: str,
        handler: Optional[Callable[[HAEvent], None]] = None
    ) -> None:
        """Unsubscribe from an event type.
        
        Args:
            event_type: Event type to unsubscribe from
            handler: Optional specific handler to remove.
                    If None, removes all handlers for the event type.
        """
        async with self._lock:
            if event_type not in self._subscriptions:
                return
            
            if handler:
                # Remove specific handler
                if handler in self._subscriptions[event_type].handlers:
                    self._subscriptions[event_type].handlers.remove(handler)
                    logger.debug(f"Removed handler from {event_type}")
                
                # Remove subscription if no handlers left
                if not self._subscriptions[event_type].handlers:
                    del self._subscriptions[event_type]
                    logger.info(f"Removed subscription for {event_type} (no handlers)")
            else:
                # Remove all handlers
                del self._subscriptions[event_type]
                logger.info(f"Removed all subscriptions for {event_type}")
    
    async def handle_event(self, ws_message: dict[str, Any]) -> None:
        """Process WebSocket message from HomeAssistant.
        
        Args:
            ws_message: Raw WebSocket message dict from HA
        """
        # Check if it's an event message
        if ws_message.get("type") != "event":
            return
        
        event_data = ws_message.get("data", {})
        event_type = event_data.get("event_type")
        
        if not event_type:
            return
        
        # Check if we have subscribers
        async with self._lock:
            if event_type not in self._subscriptions:
                return
            
            subscription = self._subscriptions[event_type]
            
            if not subscription.enabled:
                return
        
        # Create HAEvent object
        ha_event = HAEvent(
            event_type=event_type,
            data=event_data.get("data", {}),
            origin=event_data.get("origin", "LOCAL"),
            time_fired=self._parse_time(event_data.get("time_fired"))
        )
        
        # Add to history
        await self._history.add(ha_event)
        
        # Queue event for processing (with throttling)
        queued = await self._queue.put(ha_event)
        
        if queued:
            logger.debug(f"Queued event: {event_type}")
        else:
            logger.debug(f"Throttled event: {event_type}")
    
    def _parse_time(self, time_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO format time string."""
        if not time_str:
            return None
        
        try:
            # Handle both with and without timezone
            if time_str.endswith("Z"):
                time_str = time_str[:-1] + "+00:00"
            return datetime.fromisoformat(time_str)
        except Exception:
            return datetime.now()
    
    async def start_processing(self) -> None:
        """Start event processing loop.
        
        This method runs indefinitely, processing queued events
        and dispatching them to handlers.
        """
        self._running = True
        
        while self._running:
            try:
                # Get next event from queue
                event = await self._queue.get(timeout=1.0)
                
                if event:
                    await self._dispatch_event(event)
            
            except asyncio.TimeoutError:
                # No events in queue, continue
                pass
            
            except asyncio.CancelledError:
                logger.info("Event processing cancelled")
                break
            
            except Exception as e:
                logger.error(f"Event processing error: {e}")
    
    async def _dispatch_event(self, event: HAEvent) -> None:
        """Dispatch event to all registered handlers and Socket.IO.
        
        Args:
            event: Event to dispatch
        """
        async with self._lock:
            subscription = self._subscriptions.get(event.event_type)
            
            if not subscription or not subscription.enabled:
                return
            
            handlers = subscription.handlers.copy()
        
        # Call registered handlers
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.event_type}: {e}")
        
        # Broadcast via Socket.IO
        await self._broadcast_via_socketio(event)
    
    async def _broadcast_via_socketio(self, event: HAEvent) -> None:
        """Broadcast event to Socket.IO clients.
        
        Args:
            event: Event to broadcast
        """
        if not self._socketio_server:
            return
        
        try:
            event_data = event.to_dict()
            
            # Emit to specific room
            self._socketio_server.emit(
                "ha_event",
                event_data,
                room=self._socketio_room
            )
            
            logger.debug(f"Broadcast event via Socket.IO: {event.event_type}")
        
        except Exception as e:
            logger.error(f"Socket.IO broadcast error: {e}")
    
    async def join_socketio_room(self, sid: str) -> None:
        """Add client to event broadcast room.
        
        Args:
            sid: Socket.IO session ID
        """
        if self._socketio_server:
            await self._socketio_server.enter_room(sid, self._socketio_room)
            logger.debug(f"Client {sid} joined {self._socketio_room}")
    
    async def leave_socketio_room(self, sid: str) -> None:
        """Remove client from event broadcast room.
        
        Args:
            sid: Socket.IO session ID
        """
        if self._socketio_server:
            await self._socketio_server.leave_room(sid, self._socketio_room)
            logger.debug(f"Client {sid} left {self._socketio_room}")
    
    async def get_history(self, limit: int = 100, event_type: Optional[str] = None) -> List[dict[str, Any]]:
        """Get event history.
        
        Args:
            limit: Maximum number of events to return
            event_type: Optional event type filter
        
        Returns:
            List of events as dictionaries
        """
        if event_type:
            events = await self._history.get_by_type(event_type, limit=limit)
        else:
            events = await self._history.get_recent(limit=limit)
        
        return [e.to_dict() for e in events]
    
    async def clear_history(self) -> None:
        """Clear event history."""
        await self._history.clear()
        logger.info("Event history cleared")
    
    def enable_subscription(self, event_type: str) -> bool:
        """Enable a subscription.
        
        Args:
            event_type: Event type to enable
        
        Returns:
            True if successful, False if subscription not found
        """
        if event_type in self._subscriptions:
            self._subscriptions[event_type].enabled = True
            logger.info(f"Enabled subscription: {event_type}")
            return True
        return False
    
    def disable_subscription(self, event_type: str) -> bool:
        """Disable a subscription.
        
        Args:
            event_type: Event type to disable
        
        Returns:
            True if successful, False if subscription not found
        """
        if event_type in self._subscriptions:
            self._subscriptions[event_type].enabled = False
            logger.info(f"Disabled subscription: {event_type}")
            return True
        return False
    
    async def stop_processing(self) -> None:
        """Stop event processing loop."""
        self._running = False
        
        if self._process_task:
            self._process_task.cancel()
            self._process_task = None
        
        logger.info("Event processing stopped")
    
    @property
    def active_subscriptions(self) -> List[str]:
        """Get list of active subscription event types."""
        return [
            event_type for event_type, sub in self._subscriptions.items()
            if sub.enabled
        ]
    
    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    @property
    def history_size(self) -> int:
        """Get current history size."""
        return self._history.size
    
    @property
    def throttle_ms(self) -> int:
        """Get current throttle setting."""
        return self._queue.throttle_ms
    
    @throttle_ms.setter
    def throttle_ms(self, value: int) -> None:
        """Set throttle interval in milliseconds."""
        self._queue.throttle_ms = value
        logger.info(f"Event throttle set to {value}ms")


# Convenience function to create standard subscriptions
def create_standard_subscriptions(handler: EventHandler) -> None:
    """Create standard event subscriptions for common HA events.
    
    Args:
        handler: EventHandler instance to configure
    """
    standard_events = [
        EventType.STATE_CHANGED.value,
        EventType.CALL_SERVICE.value,
        EventType.AREA_REGISTRY_UPDATED.value,
    ]
    
    for event_type in standard_events:
        asyncio.create_task(handler.subscribe(event_type, throttle_ms=100))
    
    logger.info(f"Created standard subscriptions for {len(standard_events)} event types")
