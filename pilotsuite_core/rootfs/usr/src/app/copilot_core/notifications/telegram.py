"""
Telegram Notification Integration for PilotSuite.

Provides Telegram Bot push notification support.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import asyncio
import aiohttp

_LOGGER = logging.getLogger(__name__)


@dataclass
class TelegramConfig:
    """Telegram configuration."""
    bot_token: str
    chat_id: str
    parse_mode: str = "Markdown"  # Markdown or HTML
    disable_notification: bool = False


@dataclass
class TelegramMessage:
    """Telegram message payload."""
    text: str
    chat_id: Optional[str] = None
    parse_mode: str = "Markdown"
    disable_web_page_preview: bool = True
    disable_notification: bool = False
    reply_to_message_id: Optional[int] = None


class TelegramNotifier:
    """Telegram notification service."""

    API_URL = "https://api.telegram.org/bot{bot_token}/{method}"

    def __init__(self, config: TelegramConfig) -> None:
        """Initialize Telegram notifier."""
        self._config = config
        self._bot_token = config.bot_token
        self._default_chat_id = config.chat_id

    def _get_url(self, method: str) -> str:
        """Get Telegram API URL."""
        return self.API_URL.format(bot_token=self._bot_token, method=method)

    async def send(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "Markdown",
        disable_web_page_preview: bool = True,
        disable_notification: bool = False,
    ) -> bool:
        """Send Telegram message."""
        payload = {
            "chat_id": chat_id or self._default_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
            "disable_notification": disable_notification,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._get_url("sendMessage"), json=payload
                ) as response:
                    result = await response.json()
                    if result.get("ok"):
                        _LOGGER.info("Telegram notification sent")
                        return True
                    else:
                        _LOGGER.error("Telegram error: %s", result.get("description"))
                        return False
        except Exception as e:
            _LOGGER.error("Telegram send failed: %s", e)
            return False

    async def send_photo(
        self,
        photo_url: str,
        caption: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> bool:
        """Send photo via Telegram."""
        payload = {
            "chat_id": chat_id or self._default_chat_id,
            "photo": photo_url,
        }
        if caption:
            payload["caption"] = caption

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._get_url("sendPhoto"), json=payload
                ) as response:
                    result = await response.json()
                    return result.get("ok", False)
        except Exception as e:
            _LOGGER.error("Telegram photo send failed: %s", e)
            return False

    async def send_document(
        self,
        document_url: str,
        caption: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> bool:
        """Send document via Telegram."""
        payload = {
            "chat_id": chat_id or self._default_chat_id,
            "document": document_url,
        }
        if caption:
            payload["caption"] = caption

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._get_url("sendDocument"), json=payload
                ) as response:
                    result = await response.json()
                    return result.get("ok", False)
        except Exception as e:
            _LOGGER.error("Telegram document send failed: %s", e)
            return False

    async def send_location(
        self,
        latitude: float,
        longitude: float,
        chat_id: Optional[str] = None,
    ) -> bool:
        """Send location via Telegram."""
        payload = {
            "chat_id": chat_id or self._default_chat_id,
            "latitude": latitude,
            "longitude": longitude,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._get_url("sendLocation"), json=payload
                ) as response:
                    result = await response.json()
                    return result.get("ok", False)
        except Exception as e:
            _LOGGER.error("Telegram location send failed: %s", e)
            return False

    async def get_updates(self) -> List[Dict[str, Any]]:
        """Get Telegram updates (for bot interactions)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._get_url("getUpdates")
                ) as response:
                    result = await response.json()
                    if result.get("ok"):
                        return result.get("result", [])
                    return []
        except Exception as e:
            _LOGGER.error("Telegram get_updates failed: %s", e)
            return []


# Factory function
def create_telegram_notifier(bot_token: str, chat_id: str, **kwargs) -> TelegramNotifier:
    """Create Telegram notifier instance."""
    config = TelegramConfig(bot_token=bot_token, chat_id=chat_id, **kwargs)
    return TelegramNotifier(config)


__all__ = [
    "TelegramNotifier",
    "TelegramConfig",
    "TelegramMessage",
    "create_telegram_notifier",
]
