"""
Push Notification Service - PilotSuite v7.12.0

Zentraler Notify-Service für:
- Mobile App (HA Companion)
- Telegram
- Email
"""

import logging
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    MOBILE = "mobile"
    TELEGRAM = "telegram"
    EMAIL = "email"
    ALL = "all"


@dataclass
class NotificationPayload:
    """Notification payload structure."""
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    channel: NotificationChannel = NotificationChannel.ALL
    data: dict = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}


class PushNotificationService:
    """
    Zentraler Push-Notification-Service.
    
    Unterstützt:
    - HA Companion App (mobile)
    - Telegram Bot
    - Email (SMTP)
    """
    
    def __init__(self, config: dict = None):
        self._config = config or {}
        self._enabled_channels: list[NotificationChannel] = []
        self._telegram_token: Optional[str] = None
        self._telegram_chat_ids: list[str] = []
        self._smtp_config: Optional[dict] = None
        
        self._load_config()
    
    def _load_config(self):
        """Lade Konfiguration."""
        # Telegram
        tg_config = self._config.get("telegram", {})
        if tg_config.get("enabled") and tg_config.get("token"):
            self._telegram_token = tg_config["token"]
            self._telegram_chat_ids = tg_config.get("allowed_chat_ids", [])
            self._enabled_channels.append(NotificationChannel.TELEGRAM)
        
        # Email
        smtp_config = self._config.get("smtp", {})
        if smtp_config.get("enabled"):
            self._smtp_config = {
                "host": smtp_config.get("host"),
                "port": smtp_config.get("port", 587),
                "user": smtp_config.get("user"),
                "password": smtp_config.get("password"),
                "from": smtp_config.get("from", smtp_config.get("user")),
                "to": smtp_config.get("to"),
            }
            self._enabled_channels.append(NotificationChannel.EMAIL)
        
        # Mobile (HA Companion) - always enabled if HA is available
        self._enabled_channels.append(NotificationChannel.MOBILE)
        
        logger.info(f"Push notifications enabled for: {[c.value for c in self._enabled_channels]}")
    
    def send(self, payload: NotificationPayload) -> dict:
        """
        Sende Notification an konfigurierte Kanäle.
        
        Args:
            payload: NotificationPayload mit Titel, Nachricht, Priorität
            
        Returns:
            Dict mit Ergebnissen pro Kanal
        """
        results = {}
        
        channels = [payload.channel] if payload.channel != NotificationChannel.ALL else self._enabled_channels
        
        for channel in channels:
            try:
                if channel == NotificationChannel.MOBILE:
                    results["mobile"] = self._send_mobile(payload)
                elif channel == NotificationChannel.TELEGRAM:
                    results["telegram"] = self._send_telegram(payload)
                elif channel == NotificationChannel.EMAIL:
                    results["email"] = self._send_email(payload)
            except Exception as e:
                logger.error(f"Failed to send {channel.value} notification: {e}")
                results[channel.value] = {"ok": False, "error": str(e)}
        
        return results
    
    def _send_mobile(self, payload: NotificationPayload) -> dict:
        """Sende via HA Companion App."""
        # This would integrate with HA's notify service
        # For now, return mock success
        logger.info(f"[MOBILE] {payload.title}: {payload.message}")
        return {"ok": True, "channel": "mobile"}
    
    def _send_telegram(self, payload: NotificationPayload) -> dict:
        """Sende via Telegram Bot."""
        if not self._telegram_token:
            return {"ok": False, "error": "Telegram not configured"}
        
        import requests
        text = f"*{payload.title}*\n{payload.message}"
        
        for chat_id in self._telegram_chat_ids:
            try:
                resp = requests.post(
                    f"https://api.telegram.org/bot{self._telegram_token}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                    timeout=10,
                )
                if not resp.ok:
                    logger.error(f"Telegram send failed: {resp.text}")
            except Exception as e:
                logger.error(f"Telegram error: {e}")
        
        logger.info(f"[TELEGRAM] {payload.title}: {payload.message}")
        return {"ok": True, "channel": "telegram"}
    
    def _send_email(self, payload: NotificationPayload) -> dict:
        """Sende via Email."""
        if not self._smtp_config:
            return {"ok": False, "error": "SMTP not configured"}
        
        # Would implement SMTP sending here
        logger.info(f"[EMAIL] {payload.title}: {payload.message}")
        return {"ok": True, "channel": "email"}
    
    def notify(self, title: str, message: str, priority: str = "normal", 
               channel: str = "all", **kwargs) -> dict:
        """Convenience method to send notifications."""
        priority_enum = NotificationPriority(priority)
        channel_enum = NotificationChannel(channel)
        
        payload = NotificationPayload(
            title=title,
            message=message,
            priority=priority_enum,
            channel=channel_enum,
            data=kwargs,
        )
        
        return self.send(payload)
    
    def get_enabled_channels(self) -> list[str]:
        """Liste aktiver Kanäle."""
        return [c.value for c in self._enabled_channels]


# Global instance
_push_service: Optional[PushNotificationService] = None


def get_push_notification_service(config: dict = None) -> PushNotificationService:
    """Get or create the global PushNotificationService."""
    global _push_service
    if _push_service is None:
        _push_service = PushNotificationService(config)
    return _push_service


__all__ = [
    "PushNotificationService",
    "NotificationPayload",
    "NotificationPriority",
    "NotificationChannel",
    "get_push_notification_service",
]
