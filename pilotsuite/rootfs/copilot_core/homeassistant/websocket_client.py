"""HomeAssistant Async WebSocket Client.

Provides persistent WebSocket connection to HomeAssistant with:
- Long-Lived Access Token authentication
- Auto-Reconnect with Exponential Backoff
- Event subscription and streaming
- Connection state management
"""
from __future__ import annotations

import asyncio
import json
import logging
import ssl
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, List
from datetime import datetime

import aiohttp
from aiohttp import ClientWebSocketResponse, WSMsgType, ClientTimeout, TCPConnector

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class WebSocketConfig:
    """Configuration for WebSocket connection."""
    
    base_url: str = "ws://homeassistant.local:8123"
    access_token: str = ""
    timeout_seconds: float = 5.0
    verify_ssl: bool = True
    max_reconnect_attempts: int = 10
    initial_reconnect_delay: float = 1.0
    max_reconnect_delay: float = 60.0
    ping_interval: float = 30.0


@dataclass
class WebSocketStatus:
    """Status of WebSocket connection."""
    
    state: ConnectionState = ConnectionState.DISCONNECTED
    connected_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    last_error: Optional[str] = None
    reconnect_attempts: int = 0
    messages_received: int = 0


class HomeAssistantWebSocketClient:
    """Async WebSocket client for HomeAssistant real-time updates."""
    
    def __init__(self, config: Optional[WebSocketConfig] = None):
        self.config = config or WebSocketConfig()
        self._ws: Optional[ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._status = WebSocketStatus()
        self._lock = asyncio.Lock()
        self._running = False
        self._message_id = 0
        self._subscriptions: List[str] = []
        self._message_handlers: List[Callable[[dict[str, Any]], None]] = []
        self._reconnect_task: Optional[asyncio.Task] = None
    
    def _get_ws_url(self) -> str:
        """Construct WebSocket URL from base URL."""
        base = self.config.base_url
        if base.startswith("http://"):
            base = "ws://" + base[7:]
        elif base.startswith("https://"):
            base = "wss://" + base[8:]
        
        # Remove trailing slash
        base = base.rstrip("/")
        
        return f"{base}/api/websocket"
    
    async def _create_session(self) -> aiohttp.ClientSession:
        """Create aiohttp session with appropriate settings."""
        timeout = ClientTimeout(total=self.config.timeout_seconds)
        
        # SSL context configuration
        if not self.config.verify_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = TCPConnector(ssl=ssl_context)
        else:
            connector = TCPConnector()
        
        return aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        )
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session with lock."""
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    self._session = await self._create_session()
        return self._session
    
    async def connect(self) -> bool:
        """Establish WebSocket connection to HomeAssistant.
        
        Returns:
            True if connection successful, False otherwise.
        """
        async with self._lock:
            if self._status.state == ConnectionState.CONNECTED:
                return True
            
            self._status.state = ConnectionState.CONNECTING
            self._running = True
            
            try:
                session = await self._get_session()
                ws_url = self._get_ws_url()
                
                logger.info(f"Connecting to HA WebSocket at {ws_url}")
                
                self._ws = await session.ws_connect(
                    ws_url,
                    heartbeat=self.config.ping_interval,
                    timeout=self.config.timeout_seconds
                )
                
                # Wait for auth_required message
                msg = await self._ws.receive(timeout=self.config.timeout_seconds)
                
                if msg.type != WSMsgType.TEXT:
                    raise ConnectionError(f"Unexpected message type: {msg.type}")
                
                auth_msg = json.loads(msg.data)
                
                if auth_msg.get("type") != "auth_required":
                    raise ConnectionError(f"Expected auth_required, got: {auth_msg}")
                
                # Send authentication
                self._status.state = ConnectionState.AUTHENTICATING
                
                await self._ws.send_json({
                    "type": "auth",
                    "access_token": self.config.access_token
                })
                
                # Wait for auth_ok or auth_invalid
                msg = await self._ws.receive(timeout=self.config.timeout_seconds)
                
                if msg.type != WSMsgType.TEXT:
                    raise ConnectionError(f"Auth response unexpected type: {msg.type}")
                
                auth_result = json.loads(msg.data)
                
                if auth_result.get("type") == "auth_ok":
                    self._status.state = ConnectionState.CONNECTED
                    self._status.connected_at = datetime.now()
                    self._status.reconnect_attempts = 0
                    logger.info("HA WebSocket authenticated successfully")
                    
                    # Resubscribe to events if we had subscriptions
                    if self._subscriptions:
                        await self._resubscribe_events()
                    
                    return True
                
                elif auth_result.get("type") == "auth_invalid":
                    raise PermissionError(f"Authentication failed: {auth_result.get('message', 'Unknown error')}")
                
                else:
                    raise ConnectionError(f"Unexpected auth response: {auth_result}")
            
            except asyncio.TimeoutError:
                self._status.state = ConnectionState.FAILED
                self._status.last_error = "Connection timeout"
                logger.warning("HA WebSocket connection timeout")
                return False
            
            except aiohttp.ClientError as e:
                self._status.state = ConnectionState.FAILED
                self._status.last_error = str(e)
                logger.warning(f"HA WebSocket connection error: {e}")
                return False
            
            except Exception as e:
                self._status.state = ConnectionState.FAILED
                self._status.last_error = str(e)
                logger.error(f"HA WebSocket unexpected error: {e}")
                return False
    
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._running = False
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        
        if self._ws and not self._ws.closed:
            await self._ws.close()
            self._ws = None
        
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        
        self._status.state = ConnectionState.DISCONNECTED
        self._status.connected_at = None
        logger.info("HA WebSocket disconnected")
    
    async def _reconnect_with_backoff(self) -> None:
        """Reconnect with exponential backoff."""
        if not self._running:
            return
        
        self._status.state = ConnectionState.RECONNECTING
        
        while self._running and self._status.reconnect_attempts < self.config.max_reconnect_attempts:
            self._status.reconnect_attempts += 1
            
            # Calculate delay with exponential backoff
            delay = min(
                self.config.initial_reconnect_delay * (2 ** (self._status.reconnect_attempts - 1)),
                self.config.max_reconnect_delay
            )
            
            logger.info(f"Reconnecting to HA WebSocket in {delay:.1f}s (attempt {self._status.reconnect_attempts})")
            await asyncio.sleep(delay)
            
            if await self.connect():
                logger.info("Reconnection successful")
                return
        
        if self._status.reconnect_attempts >= self.config.max_reconnect_attempts:
            self._status.state = ConnectionState.FAILED
            self._status.last_error = f"Max reconnect attempts ({self.config.max_reconnect_attempts}) reached"
            logger.error(self._status.last_error)
    
    async def start_listening(self) -> None:
        """Start listening for WebSocket messages.
        
        This method runs indefinitely until disconnect() is called.
        It automatically handles reconnection on connection loss.
        """
        while self._running:
            try:
                if self._status.state != ConnectionState.CONNECTED:
                    if not await self.connect():
                        await self._reconnect_with_backoff()
                        continue
                
                if not self._ws:
                    await asyncio.sleep(1)
                    continue
                
                # Receive message
                msg = await self._ws.receive(timeout=self.config.ping_interval * 2)
                
                if msg.type == WSMsgType.TEXT:
                    self._status.last_message_at = datetime.now()
                    self._status.messages_received += 1
                    
                    try:
                        data = json.loads(msg.data)
                        await self._dispatch_message(data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse message: {e}")
                
                elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                    logger.warning(f"WebSocket closed/error: {msg.type}")
                    self._status.state = ConnectionState.DISCONNECTED
                    await self._reconnect_with_backoff()
                
                elif msg.type == WSMsgType.CLOSING:
                    logger.info("WebSocket closing")
                    break
            
            except asyncio.TimeoutError:
                # Ping timeout - connection might be stale
                logger.warning("WebSocket ping timeout")
                self._status.state = ConnectionState.DISCONNECTED
                await self._reconnect_with_backoff()
            
            except asyncio.CancelledError:
                logger.info("WebSocket listening cancelled")
                break
            
            except Exception as e:
                logger.error(f"WebSocket listening error: {e}")
                self._status.state = ConnectionState.DISCONNECTED
                await self._reconnect_with_backoff()
    
    async def _dispatch_message(self, data: dict[str, Any]) -> None:
        """Dispatch message to all registered handlers."""
        for handler in self._message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Message handler error: {e}")
    
    def add_message_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Add a message handler callback.
        
        Args:
            handler: Callback function that receives message data dict.
        """
        self._message_handlers.append(handler)
        logger.debug(f"Added message handler (total: {len(self._message_handlers)})")
    
    def remove_message_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Remove a message handler callback."""
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)
            logger.debug(f"Removed message handler (total: {len(self._message_handlers)})")
    
    async def subscribe_events(self, event_types: List[str]) -> bool:
        """Subscribe to HomeAssistant events.
        
        Args:
            event_types: List of event types to subscribe to.
                        Common types: "state_changed", "call_service", 
                                     "area_registry_updated", "device_registry_updated"
        
        Returns:
            True if subscription successful, False otherwise.
        """
        if self._status.state != ConnectionState.CONNECTED:
            logger.warning("Cannot subscribe - not connected")
            return False
        
        try:
            for event_type in event_types:
                self._message_id += 1
                
                await self._ws.send_json({
                    "id": self._message_id,
                    "type": "subscribe_events",
                    "event_type": event_type
                })
                
                # Wait for subscription confirmation
                msg = await self._ws.receive(timeout=self.config.timeout_seconds)
                
                if msg.type != WSMsgType.TEXT:
                    logger.warning(f"Subscription response unexpected type: {msg.type}")
                    continue
                
                result = json.loads(msg.data)
                
                if result.get("type") == "result" and result.get("success", False):
                    if event_type not in self._subscriptions:
                        self._subscriptions.append(event_type)
                    logger.info(f"Subscribed to event: {event_type}")
                else:
                    logger.warning(f"Failed to subscribe to {event_type}: {result}")
            
            return True
        
        except Exception as e:
            logger.error(f"Event subscription error: {e}")
            return False
    
    async def _resubscribe_events(self) -> None:
        """Resubscribe to all events after reconnection."""
        if self._subscriptions:
            logger.info(f"Resubscribing to {len(self._subscriptions)} events")
            await self.subscribe_events(self._subscriptions)
    
    async def unsubscribe_events(self, event_types: Optional[List[str]] = None) -> bool:
        """Unsubscribe from events.
        
        Args:
            event_types: List of event types to unsubscribe from.
                        If None, unsubscribe from all.
        
        Returns:
            True if successful, False otherwise.
        """
        if self._status.state != ConnectionState.CONNECTED:
            return False
        
        try:
            events_to_unsub = event_types or self._subscriptions.copy()
            
            for event_type in events_to_unsub:
                self._message_id += 1
                
                await self._ws.send_json({
                    "id": self._message_id,
                    "type": "unsubscribe_events",
                    "subscription": self._message_id
                })
                
                if event_type in self._subscriptions:
                    self._subscriptions.remove(event_type)
                
                logger.info(f"Unsubscribed from event: {event_type}")
            
            return True
        
        except Exception as e:
            logger.error(f"Event unsubscription error: {e}")
            return False
    
    async def call_service(self, domain: str, service: str, service_data: Optional[dict[str, Any]] = None) -> bool:
        """Call a HomeAssistant service.
        
        Args:
            domain: Service domain (e.g., "light", "switch")
            service: Service name (e.g., "turn_on", "turn_off")
            service_data: Service data payload
        
        Returns:
            True if call successful, False otherwise.
        """
        if self._status.state != ConnectionState.CONNECTED:
            logger.warning("Cannot call service - not connected")
            return False
        
        try:
            self._message_id += 1
            
            await self._ws.send_json({
                "id": self._message_id,
                "type": "call_service",
                "domain": domain,
                "service": service,
                "service_data": service_data or {}
            })
            
            # Wait for result
            msg = await self._ws.receive(timeout=self.config.timeout_seconds)
            
            if msg.type != WSMsgType.TEXT:
                logger.warning(f"Service call response unexpected type: {msg.type}")
                return False
            
            result = json.loads(msg.data)
            
            if result.get("type") == "result" and result.get("success", False):
                logger.info(f"Service call successful: {domain}.{service}")
                return True
            else:
                logger.warning(f"Service call failed: {result}")
                return False
        
        except Exception as e:
            logger.error(f"Service call error: {e}")
            return False
    
    async def get_states(self) -> Optional[list[dict[str, Any]]]:
        """Get all entity states via WebSocket.
        
        Returns:
            List of entity states, or None if failed.
        """
        if self._status.state != ConnectionState.CONNECTED:
            logger.warning("Cannot get states - not connected")
            return None
        
        try:
            self._message_id += 1
            
            await self._ws.send_json({
                "id": self._message_id,
                "type": "get_states"
            })
            
            # Wait for result
            msg = await self._ws.receive(timeout=self.config.timeout_seconds)
            
            if msg.type != WSMsgType.TEXT:
                logger.warning(f"Get states response unexpected type: {msg.type}")
                return None
            
            result = json.loads(msg.data)
            
            if result.get("type") == "result" and result.get("success", False):
                return result.get("result", [])
            else:
                logger.warning(f"Get states failed: {result}")
                return None
        
        except Exception as e:
            logger.error(f"Get states error: {e}")
            return None
    
    @property
    def status(self) -> WebSocketStatus:
        """Get current connection status."""
        return self._status
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._status.state == ConnectionState.CONNECTED
    
    @property
    def subscriptions(self) -> List[str]:
        """Get list of active subscriptions."""
        return self._subscriptions.copy()
    
    async def __aenter__(self) -> "HomeAssistantWebSocketClient":
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
