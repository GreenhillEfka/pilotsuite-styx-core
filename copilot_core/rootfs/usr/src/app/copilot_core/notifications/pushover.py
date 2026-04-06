"""
Pushover Notification Integration for PilotSuite.

Provides Pushover push notification support.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
import asyncio
import aiohttp
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)


@dataclass
class PushoverConfig:
    """Pushover configuration."""
    api_token: str
    user_key: str
    device: Optional[str] = None
    priority: int = 0  # -2, -1, 0, 1, 2
    sound: str = "default"


@dataclass
class PushoverMessage:
    """Pushover message payload."""
    title: str
    message: str
    priority: int = 0
    sound: str = "default"
    url: Optional[str] = None
    url_title: Optional[str] = None
    device: Optional[str] = None
    timestamp: Optional[int] = None
    retry: int = 30
    expire: int = 3600


class PushoverNotifier:
    """Pushover notification service."""

    API_URL = "https://api.pushover.net/1/messages.json"

    def __init__(self, config: PushoverConfig) -> None:
        """Initialize Pushover notifier."""
        self._config = config

    async def send(
        self,
        title: str,
        message: str,
        priority: int = 0,
        sound: str = "default",
        url: Optional[str] = None,
        url_title: Optional[str] = None,
    ) -> bool:
        """Send Pushover notification."""
        payload = {
            "token": self._config.api_token,
            "user": self._config.user_key,
            "title": title[:256],  # Pushover title limit
            "message": message,
            "priority": priority,
            "sound": sound,
        }

        if self._config.device:
            payload["device"] = self._config.device
        if url:
            payload["url"] = url
            if url_title:
                payload["url_title"] = url_title
        if priority == 2:  # Emergency priority
            payload["retry"] = 30
            payload["expire"] = 3600

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.API_URL, data=payload) as response:
                    result = await response.json()
                    if result.get("status") == 1:
                        _LOGGER.info("Pushover notification sent: %s", title)
                        return True
                    else:
                        _LOGGER.error("Pushover error: %s", result.get("errors"))
                        return False
        except Exception as e:
            _LOGGER.error("Pushover send failed: %s", e)
            return False

    async def send_batch(self, messages: list[PushoverMessage]) -> Dict[str, bool]:
        """Send multiple notifications."""
        results = {}
        for i, msg in enumerate(messages):
            success = await self.send(
                title=msg.title,
                message=msg.message,
                priority=msg.priority,
                sound=msg.sound,
                url=msg.url,
                url_title=msg.url_title,
            )
            results[f"msg_{i}"] = success
        return results


# Factory function
def create_pushover_notifier(api_token: str, user_key: str, **kwargs) -> PushoverNotifier:
    """Create Pushover notifier instance."""
    config = PushoverConfig(api_token=api_token, user_key=user_key, **kwargs)
    return PushoverNotifier(config)


__all__ = [
    "PushoverNotifier",
    "PushoverConfig", 
    "PushoverMessage",
    "create_pushover_notifier",
]
