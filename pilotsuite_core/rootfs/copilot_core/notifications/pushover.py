"""
Pushover Notification Integration for PilotSuite Core.

Provides real-time push notifications via Pushover.net API.
Supports priority levels, sounds, URLs, and delivery confirmation.
"""

from __future__ import annotations

import logging
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .delivery_contracts import (
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    NotificationV1,
    DeliveryStatus,
    DeliveryAttemptV1,
)

logger = logging.getLogger(__name__)

# Pushover API configuration
PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_SOUNDS = {
    "pushover": "Default",
    "bike": "Bike",
    "bugle": "Bugle",
    "cashregister": "Cash Register",
    "classical": "Classical",
    "cosmic": "Cosmic",
    "falling": "Falling",
    "gamelan": "Gamelan",
    "incoming": "Incoming",
    "intermission": "Intermission",
    "magic": "Magic",
    "mechanical": "Mechanical",
    "pianobar": "Piano Bar",
    "siren": "Siren",
    "spacealarm": "Space Alarm",
    "tugboat": "Tugboat",
    "alien": "Alien (long)",
    "climb": "Climb (long)",
    "persistent": "Persistent (long)",
    "echo": "Echo (long)",
    "updown": "Up Down (long)",
    "vibrate": "Vibrate Only",
    "none": "None (silent)",
}

# Priority mapping: our priority -> Pushover priority
PRIORITY_MAP = {
    NotificationPriority.LOW: -2,  # Lowest (silent)
    NotificationPriority.NORMAL: 0,  # Normal
    NotificationPriority.HIGH: 1,  # High (vibrate)
    NotificationPriority.CRITICAL: 2,  # Emergency (requires confirmation)
}


@dataclass
class PushoverConfig:
    """Pushover configuration."""
    api_token: str
    user_key: str
    device: Optional[str] = None
    sound: Optional[str] = None
    url: Optional[str] = None
    url_title: Optional[str] = None
    retry_seconds: int = 30  # For emergency priority
    expire_seconds: int = 3600  # For emergency priority
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_token": self.api_token,
            "user_key": self.user_key,
            "device": self.device,
            "sound": self.sound,
            "url": self.url,
            "url_title": self.url_title,
            "retry_seconds": self.retry_seconds,
            "expire_seconds": self.expire_seconds,
        }


@dataclass
class PushoverResponse:
    """Pushover API response."""
    status: int
    request_id: str
    errors: List[str] = field(default_factory=list)
    receipt: Optional[str] = None  # For emergency priority
    acked: Optional[bool] = None  # For emergency priority
    acked_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> PushoverResponse:
        status = data.get("status", 0)
        return cls(
            status=status,
            request_id=data.get("request", ""),
            errors=data.get("errors", []),
            receipt=data.get("receipt"),
        )


class PushoverHandler:
    """
    Pushover notification handler.
    
    Features:
    - Real-time push notifications
    - Priority levels with emergency support
    - Custom sounds
    - URL attachments
    - Delivery confirmation for emergency messages
    - Rate limiting awareness
    """
    
    def __init__(self, config: Optional[PushoverConfig] = None):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
    
    def configure(self, config: PushoverConfig) -> None:
        """Update Pushover configuration."""
        self.config = config
        logger.info("Pushover configured for user key: %s", config.user_key[:8] + "..." if config.user_key else "N/A")
    
    def is_configured(self) -> bool:
        """Check if Pushover is properly configured."""
        return bool(self.config and self.config.api_token and self.config.user_key)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _map_priority(self, priority: NotificationPriority) -> int:
        """Map internal priority to Pushover priority."""
        return PRIORITY_MAP.get(priority, 0)
    
    def _select_sound(self, priority: NotificationPriority, sound_override: Optional[str] = None) -> str:
        """Select appropriate sound based on priority."""
        if sound_override:
            return sound_override
        
        # Default sounds by priority
        if priority == NotificationPriority.CRITICAL:
            return "siren"
        elif priority == NotificationPriority.HIGH:
            return "incoming"
        elif priority == NotificationPriority.LOW:
            return "none"
        else:
            return "pushover"
    
    async def send(self, notification: NotificationV1) -> Dict[str, Any]:
        """
        Send notification via Pushover.
        
        Args:
            notification: Notification to send
            
        Returns:
            Delivery result dictionary
        """
        if not self.is_configured():
            raise RuntimeError("Pushover not configured. Missing api_token or user_key.")
        
        session = await self._get_session()
        
        # Build payload
        payload = {
            "token": self.config.api_token,
            "user": self.config.user_key,
            "title": notification.title,
            "message": notification.body,
            "priority": self._map_priority(notification.priority),
            "sound": self._select_sound(notification.priority, self.config.sound),
        }
        
        # Optional fields
        if self.config.device:
            payload["device"] = self.config.device
        
        if notification.action_url or self.config.url:
            payload["url"] = notification.action_url or self.config.url
            payload["url_title"] = notification.data.get("url_title") or self.config.url_title or "View Details"
        
        if notification.data.get("attachment"):
            payload["attachment"] = notification.data["attachment"]
        
        # Emergency priority settings
        if notification.priority == NotificationPriority.CRITICAL:
            payload["retry"] = self.config.retry_seconds
            payload["expire"] = self.config.expire_seconds
            if notification.idempotency_key:
                payload["receipt"] = notification.idempotency_key
        
        # Send request
        try:
            async with session.post(PUSHOVER_API_URL, data=payload) as response:
                response_data = await response.json()
                pushover_response = PushoverResponse.from_api_response(response_data)
                
                if pushover_response.status == 1:
                    result = {
                        "sent": True,
                        "channel": "pushover",
                        "request_id": pushover_response.request_id,
                        "message_id": pushover_response.request_id,
                        "receipt": pushover_response.receipt,
                        "priority": payload["priority"],
                    }
                    
                    if notification.priority == NotificationPriority.CRITICAL and pushover_response.receipt:
                        result["emergency_receipt"] = pushover_response.receipt
                        result["requires_confirmation"] = True
                    
                    logger.info(
                        "Pushover notification sent: %s (request: %s)",
                        notification.notification_id,
                        pushover_response.request_id,
                    )
                    return result
                else:
                    error_msg = "; ".join(pushover_response.errors) if pushover_response.errors else "Unknown error"
                    logger.error("Pushover API error: %s", error_msg)
                    raise RuntimeError(f"Pushover API error: {error_msg}")
        
        except aiohttp.ClientError as e:
            logger.error("Pushover HTTP error: %s", str(e))
            raise RuntimeError(f"Pushover HTTP error: {str(e)}")
        except Exception as e:
            logger.exception("Pushover send failed")
            raise
    
    async def check_emergency_receipt(self, receipt: str) -> Dict[str, Any]:
        """
        Check the status of an emergency notification.
        
        Args:
            receipt: Receipt ID from emergency notification
            
        Returns:
            Status dictionary with acknowledgment info
        """
        if not self.is_configured():
            raise RuntimeError("Pushover not configured.")
        
        session = await self._get_session()
        
        try:
            url = f"{PUSHOVER_API_URL}/receipt/{receipt}.json"
            params = {"token": self.config.api_token}
            
            async with session.get(url, params=params) as response:
                data = await response.json()
                
                return {
                    "receipt": receipt,
                    "status": data.get("status", 0),
                    "acked": data.get("acked", False),
                    "acked_at": datetime.fromtimestamp(data["acked_time"], tz=timezone.utc) if data.get("acked_time") else None,
                    "acknowledged_by": data.get("acknowledged_by"),
                    "last_delivered_at": datetime.fromtimestamp(data["last_delivered"], tz=timezone.utc) if data.get("last_delivered") else None,
                    "expires_at": datetime.fromtimestamp(data["expires"], tz=timezone.utc) if data.get("expires") else None,
                    "called_at": datetime.fromtimestamp(data["called_at"], tz=timezone.utc) if data.get("called_at") else None,
                }
        
        except Exception as e:
            logger.exception("Failed to check emergency receipt")
            raise
    
    async def cancel_emergency(self, receipt: str) -> bool:
        """
        Cancel an emergency notification (stop retries).
        
        Args:
            receipt: Receipt ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        if not self.is_configured():
            raise RuntimeError("Pushover not configured.")
        
        session = await self._get_session()
        
        try:
            url = f"{PUSHOVER_API_URL}/receipt/{receipt}/cancel.json"
            params = {"token": self.config.api_token}
            
            async with session.post(url, params=params) as response:
                data = await response.json()
                return data.get("status", 0) == 1
        
        except Exception as e:
            logger.exception("Failed to cancel emergency notification")
            raise


# Singleton instance
_pushover_handler: Optional[PushoverHandler] = None


def get_pushover_handler() -> PushoverHandler:
    """Get the singleton Pushover handler instance."""
    global _pushover_handler
    if _pushover_handler is None:
        _pushover_handler = PushoverHandler()
    return _pushover_handler


def configure_pushover(api_token: str, user_key: str, **kwargs) -> PushoverHandler:
    """Configure and return the Pushover handler."""
    handler = get_pushover_handler()
    config = PushoverConfig(api_token=api_token, user_key=user_key, **kwargs)
    handler.configure(config)
    return handler
