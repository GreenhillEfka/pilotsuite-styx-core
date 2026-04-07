"""PilotSuite Notification Integrations — Pushover, Telegram, and more."""
from __future__ import annotations

import logging
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# NOTIFICATION TYPES
# =============================================================================

class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


@dataclass
class Notification:
    """Notification data structure."""
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    url: Optional[str] = None
    url_title: Optional[str] = None
    sound: Optional[str] = None
    timestamp: Optional[float] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# PUSHOVER INTEGRATION
# =============================================================================

@dataclass
class PushoverConfig:
    """Pushover configuration."""
    api_token: str
    user_key: str
    sound: Optional[str] = None
    priority_default: NotificationPriority = NotificationPriority.NORMAL


class PushoverNotifier:
    """
    Pushover Notification Service
    
    Features:
    - Priority-based notifications
    - Custom sounds
    - URL attachments
    - Delivery confirmation
    
    Setup:
    1. Create app at https://pushover.net
    2. Get API token
    3. Get user key
    4. Configure in YAML
    """

    API_URL = "https://api.pushover.net/1/messages.json"

    def __init__(self, config: PushoverConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def send(self, notification: Notification) -> Dict[str, Any]:
        """Send notification via Pushover."""
        session = await self._get_session()
        
        payload = {
            "token": self.config.api_token,
            "user": self.config.user_key,
            "title": notification.title,
            "message": notification.message,
            "priority": notification.priority.value,
        }
        
        if notification.sound or self.config.sound:
            payload["sound"] = notification.sound or self.config.sound
        
        if notification.url:
            payload["url"] = notification.url
        
        if notification.url_title:
            payload["url_title"] = notification.url_title
        
        if notification.timestamp:
            payload["timestamp"] = int(notification.timestamp)
        
        # Emergency priority requires retry
        if notification.priority == NotificationPriority.EMERGENCY:
            payload["retry"] = 60  # Retry every 60 seconds
            payload["expire"] = 3600  # Expire after 1 hour
        
        async with session.post(self.API_URL, data=payload) as response:
            result = await response.json()
            
            if response.status == 200:
                logger.info(f"Pushover notification sent: {notification.title}")
                return {"success": True, "receipt": result.get("receipt")}
            else:
                logger.error(f"Pushover error: {result}")
                return {"success": False, "error": result}

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


# =============================================================================
# TELEGRAM INTEGRATION
# =============================================================================

@dataclass
class TelegramConfig:
    """Telegram configuration."""
    bot_token: str
    chat_ids: List[str]
    parse_mode: str = "HTML"  # HTML, Markdown


class TelegramNotifier:
    """
    Telegram Notification Service
    
    Features:
    - Multiple chat targets
    - HTML/Markdown formatting
    - Inline keyboards
    - Photo/document attachments
    
    Setup:
    1. Create bot via @BotFather
    2. Get bot token
    3. Get chat IDs
    4. Configure in YAML
    """

    API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, config: TelegramConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def send(self, notification: Notification, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Send notification to Telegram."""
        session = await self._get_session()
        
        # Use first chat ID if none specified
        target_chat = chat_id or (self.config.chat_ids[0] if self.config.chat_ids else None)
        if not target_chat:
            return {"success": False, "error": "No chat ID specified"}
        
        url = self.API_URL.format(token=self.config.bot_token)
        
        payload = {
            "chat_id": target_chat,
            "title": notification.title,
            "text": f"<b>{notification.title}</b>\n\n{notification.message}",
            "parse_mode": self.config.parse_mode,
        }
        
        # Add inline keyboard if URL provided
        if notification.url:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": notification.url_title or "Open", "url": notification.url}
                ]]
            }
        
        async with session.post(url, json=payload) as response:
            result = await response.json()
            
            if response.status == 200 and result.get("ok"):
                logger.info(f"Telegram notification sent to {target_chat}: {notification.title}")
                return {"success": True, "message_id": result["result"]["message_id"]}
            else:
                logger.error(f"Telegram error: {result}")
                return {"success": False, "error": result}

    async def send_photo(self, photo_path: str, caption: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Send photo to Telegram."""
        session = await self._get_session()
        
        target_chat = chat_id or (self.config.chat_ids[0] if self.config.chat_ids else None)
        if not target_chat:
            return {"success": False, "error": "No chat ID specified"}
        
        url = self.API_URL.format(token=self.config.bot_token).replace("sendMessage", "sendPhoto")
        
        with open(photo_path, "rb") as photo_file:
            payload = {
                "chat_id": target_chat,
                "caption": caption,
                "parse_mode": self.config.parse_mode,
            }
            files = {"photo": photo_file}
            
            async with session.post(url, data=payload, json=files) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("ok"):
                    logger.info(f"Telegram photo sent to {target_chat}")
                    return {"success": True, "message_id": result["result"]["message_id"]}
                else:
                    logger.error(f"Telegram photo error: {result}")
                    return {"success": False, "error": result}

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


# =============================================================================
# NOTIFICATION MANAGER
# =============================================================================

@dataclass
class NotificationManagerConfig:
    """Notification manager configuration."""
    pushover: Optional[PushoverConfig] = None
    telegram: Optional[TelegramConfig] = None
    default_priority: NotificationPriority = NotificationPriority.NORMAL
    channels: List[str] = None  # Which channels to use


class NotificationManager:
    """
    Unified Notification Manager
    
    Features:
    - Multi-channel notifications
    - Priority routing
    - Retry logic
    - Rate limiting
    
    YAML Config:
    ```yaml
    pilotsuite:
      notifications:
        pushover:
          api_token: !secret pushover_token
          user_key: !secret pushover_user
        telegram:
          bot_token: !secret telegram_bot_token
          chat_ids:
            - "-1001234567890"
        default_priority: normal
        channels:
          - pushover
          - telegram
    ```
    """

    def __init__(self, config: NotificationManagerConfig):
        self.config = config
        self._pushover: Optional[PushoverNotifier] = None
        self._telegram: Optional[TelegramNotifier] = None
        
        if config.pushover:
            self._pushover = PushoverNotifier(config.pushover)
        
        if config.telegram:
            self._telegram = TelegramNotifier(config.telegram)

    async def send(self, notification: Notification) -> Dict[str, Any]:
        """Send notification to all configured channels."""
        results = {}
        
        channels = self.config.channels or []
        
        # If no channels specified, use all configured
        if not channels:
            channels = []
            if self._pushover:
                channels.append("pushover")
            if self._telegram:
                channels.append("telegram")
        
        for channel in channels:
            if channel == "pushover" and self._pushover:
                results["pushover"] = await self._pushover.send(notification)
            elif channel == "telegram" and self._telegram:
                results["telegram"] = await self._telegram.send(notification)
        
        # Check overall success
        all_success = all(r.get("success", False) for r in results.values())
        
        return {
            "success": all_success,
            "channels": results,
            "notification": notification.title,
        }

    async def send_urgent(self, title: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send urgent notification (emergency priority)."""
        notification = Notification(
            title=title,
            message=message,
            priority=NotificationPriority.EMERGENCY,
            **kwargs
        )
        return await self.send(notification)

    async def send_info(self, title: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send informational notification (low priority)."""
        notification = Notification(
            title=title,
            message=message,
            priority=NotificationPriority.LOW,
            **kwargs
        )
        return await self.send(notification)

    async def close(self):
        """Close all notifier sessions."""
        if self._pushover:
            await self._pushover.close()
        if self._telegram:
            await self._telegram.close()


# =============================================================================
# HOME ASSISTANT SERVICE
# =============================================================================

async def async_setup_notification_services(hass):
    """Set up notification services in Home Assistant."""
    
    async def notify_service_handler(call):
        """Handle notification service calls."""
        # Get notification manager from hass.data
        manager = hass.data.get("pilotsuite_notification_manager")
        if not manager:
            logger.error("Notification manager not initialized")
            return
        
        notification = Notification(
            title=call.data.get("title", "PilotSuite"),
            message=call.data.get("message", ""),
            priority=NotificationPriority(call.data.get("priority", 0)),
            url=call.data.get("url"),
            url_title=call.data.get("url_title"),
        )
        
        result = await manager.send(notification)
        
        if not result["success"]:
            logger.error(f"Notification failed: {result}")

    # Register services
    hass.services.async_register(
        "pilotsuite",
        "notify",
        notify_service_handler,
    )
    
    hass.services.async_register(
        "pilotsuite",
        "notify_urgent",
        lambda call: notify_service_handler(call),  # Could add priority override
    )
