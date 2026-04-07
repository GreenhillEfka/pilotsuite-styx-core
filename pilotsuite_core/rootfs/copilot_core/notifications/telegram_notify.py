"""
Telegram Notification Integration for PilotSuite Core.

Provides real-time notifications via Telegram Bot API.
Supports markdown formatting, inline keyboards, photos, and group messaging.
"""

from __future__ import annotations

import logging
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from .delivery_contracts import (
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    NotificationV1,
    DeliveryStatus,
)

logger = logging.getLogger(__name__)

# Telegram Bot API configuration
TELEGRAM_API_BASE = "https://api.telegram.org/bot"

# Parse modes
PARSE_MODE_MARKDOWN = "MarkdownV2"
PARSE_MODE_HTML = "HTML"
PARSE_MODE_PLAIN = None


@dataclass
class TelegramConfig:
    """Telegram Bot configuration."""
    bot_token: str
    default_chat_id: Optional[str] = None
    parse_mode: str = PARSE_MODE_HTML
    disable_notification: bool = False  # Silent send
    protect_content: bool = False  # Disable forwarding
    
    @property
    def api_url(self) -> str:
        return f"{TELEGRAM_API_BASE}{self.bot_token}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bot_token": self.bot_token[:10] + "..." if self.bot_token else None,
            "default_chat_id": self.default_chat_id,
            "parse_mode": self.parse_mode,
            "disable_notification": self.disable_notification,
            "protect_content": self.protect_content,
        }


@dataclass
class TelegramInlineButton:
    """Inline keyboard button for Telegram messages."""
    text: str
    callback_data: str
    url: Optional[str] = None
    web_app_url: Optional[str] = None
    login_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        button = {"text": self.text}
        if self.callback_data:
            button["callback_data"] = self.callback_data
        if self.url:
            button["url"] = self.url
        if self.web_app_url:
            button["web_app"] = {"url": self.web_app_url}
        if self.login_url:
            button["login_url"] = {"url": self.login_url}
        return button


@dataclass
class TelegramResponse:
    """Telegram API response."""
    ok: bool
    message_id: Optional[int] = None
    chat_id: Optional[str] = None
    date: Optional[datetime] = None
    error_code: Optional[int] = None
    description: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> TelegramResponse:
        ok = data.get("ok", False)
        result = data.get("result", {})
        
        return cls(
            ok=ok,
            message_id=result.get("message_id") if result else None,
            chat_id=str(result.get("chat", {}).get("id")) if result else None,
            date=datetime.fromtimestamp(result["date"], tz=timezone.utc) if result and result.get("date") else None,
            error_code=data.get("error_code"),
            description=data.get("description"),
            result=result if result else None,
        )


class TelegramHandler:
    """
    Telegram Bot notification handler.
    
    Features:
    - Text messages with Markdown/HTML formatting
    - Inline keyboards with callback buttons
    - Photo, document, and media support
    - Group and channel messaging
    - Silent messages
    - Message editing and deletion
    - Webhook support for callbacks
    """
    
    def __init__(self, config: Optional[TelegramConfig] = None):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
    
    def configure(self, config: TelegramConfig) -> None:
        """Update Telegram configuration."""
        self.config = config
        logger.info("Telegram configured for bot token: %s", config.bot_token[:10] + "..." if config.bot_token else "N/A")
    
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.config and self.config.bot_token)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _api_call(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make a Telegram API call."""
        if not self.is_configured():
            raise RuntimeError("Telegram not configured. Missing bot_token.")
        
        session = await self._get_session()
        url = f"{self.config.api_url}/{method}"
        
        try:
            async with session.post(url, json=payload) as response:
                data = await response.json()
                
                if not data.get("ok"):
                    error_desc = data.get("description", "Unknown error")
                    error_code = data.get("error_code")
                    logger.error("Telegram API error (%d): %s", error_code, error_desc)
                    raise RuntimeError(f"Telegram API error ({error_code}): {error_desc}")
                
                return data
        
        except aiohttp.ClientError as e:
            logger.error("Telegram HTTP error: %s", str(e))
            raise RuntimeError(f"Telegram HTTP error: {str(e)}")
    
    def _build_message_payload(
        self,
        chat_id: str,
        title: str,
        body: str,
        notification: NotificationV1,
    ) -> Dict[str, Any]:
        """Build the sendMessage payload."""
        # Combine title and body
        if self.config.parse_mode == PARSE_MODE_HTML:
            text = f"<b>{self._escape_html(title)}</b>\n\n{body}"
        elif self.config.parse_mode == PARSE_MODE_MARKDOWN:
            text = f"*{self._escape_markdown(title)}*\n\n{body}"
        else:
            text = f"{title}\n\n{body}"
        
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": self.config.parse_mode,
            "disable_notification": self.config.disable_notification,
            "protect_content": self.config.protect_content,
        }
        
        # Add inline keyboard if present
        buttons = self._build_inline_keyboard(notification)
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}
        
        return payload
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))
    
    def _escape_markdown(self, text: str) -> str:
        """Escape MarkdownV2 special characters."""
        chars = r"_*[]()~`>#+-=|{}.!"
        for char in chars:
            text = text.replace(char, f"\\{char}")
        return text
    
    def _build_inline_keyboard(self, notification: NotificationV1) -> List[List[Dict[str, Any]]]:
        """Build inline keyboard from notification data."""
        buttons = []
        row = []
        
        # Primary action button
        if notification.action_url:
            row.append({
                "text": notification.data.get("action_label", "Open"),
                "url": notification.action_url,
            })
        
        # Callback buttons from data
        for key, value in notification.data.items():
            if key.startswith("callback_"):
                button_text = notification.data.get(f"label_{key}", key.replace("callback_", ""))
                row.append(TelegramInlineButton(
                    text=button_text,
                    callback_data=f"{notification.notification_id}:{key}:{value}",
                ).to_dict())
        
        if row:
            buttons.append(row)
        
        # Add dismiss button for non-critical notifications
        if notification.priority != NotificationPriority.CRITICAL:
            buttons.append([{
                "text": "✓ Dismiss",
                "callback_data": f"dismiss:{notification.notification_id}",
            }])
        
        return buttons
    
    async def send(self, notification: NotificationV1) -> Dict[str, Any]:
        """
        Send notification via Telegram.
        
        Args:
            notification: Notification to send
            
        Returns:
            Delivery result dictionary
        """
        if not self.is_configured():
            raise RuntimeError("Telegram not configured. Missing bot_token.")
        
        # Determine chat ID
        chat_id = notification.recipient_id or self.config.default_chat_id
        if not chat_id:
            raise ValueError("No chat_id provided for Telegram notification")
        
        # Build and send message
        payload = self._build_message_payload(
            chat_id=chat_id,
            title=notification.title,
            body=notification.body,
            notification=notification,
        )
        
        # Add priority-specific options
        if notification.priority == NotificationPriority.CRITICAL:
            payload["disable_notification"] = False  # Always notify for critical
        
        result = await self._api_call("sendMessage", payload)
        response = TelegramResponse.from_api_response(result)
        
        delivery_result = {
            "sent": True,
            "channel": "telegram",
            "message_id": response.message_id,
            "chat_id": response.chat_id or chat_id,
            "date": response.date.isoformat() if response.date else None,
        }
        
        logger.info(
            "Telegram notification sent: %s to chat %s (message %s)",
            notification.notification_id,
            chat_id,
            response.message_id,
        )
        
        return delivery_result
    
    async def send_photo(
        self,
        chat_id: str,
        photo: Union[str, bytes],
        caption: str = "",
        notification: Optional[NotificationV1] = None,
    ) -> Dict[str, Any]:
        """
        Send a photo message.
        
        Args:
            chat_id: Target chat ID
            photo: URL or file bytes
            caption: Photo caption
            notification: Optional notification context
            
        Returns:
            Delivery result dictionary
        """
        if not self.is_configured():
            raise RuntimeError("Telegram not configured.")
        
        payload = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": self.config.parse_mode,
        }
        
        if isinstance(photo, bytes):
            # Send as file upload
            session = await self._get_session()
            data = aiohttp.FormData()
            data.add_field("chat_id", chat_id)
            data.add_field("photo", photo, filename="image.jpg")
            data.add_field("caption", caption)
            if self.config.parse_mode:
                data.add_field("parse_mode", self.config.parse_mode)
            
            url = f"{self.config.api_url}/sendPhoto"
            async with session.post(url, data=data) as response:
                result = await response.json()
        else:
            # Send as URL
            payload["photo"] = photo
            result = await self._api_call("sendPhoto", payload)
        
        response = TelegramResponse.from_api_response(result)
        
        return {
            "sent": True,
            "channel": "telegram",
            "message_id": response.message_id,
            "chat_id": response.chat_id or chat_id,
            "type": "photo",
        }
    
    async def edit_message(
        self,
        chat_id: str,
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Edit a message text.
        
        Args:
            chat_id: Chat ID
            message_id: Message ID to edit
            text: New text
            reply_markup: Optional new inline keyboard
            
        Returns:
            True if edited successfully
        """
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": self.config.parse_mode,
        }
        
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        result = await self._api_call("editMessageText", payload)
        return result.get("ok", False)
    
    async def delete_message(self, chat_id: str, message_id: int) -> bool:
        """
        Delete a message.
        
        Args:
            chat_id: Chat ID
            message_id: Message ID to delete
            
        Returns:
            True if deleted successfully
        """
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
        }
        
        result = await self._api_call("deleteMessage", payload)
        return result.get("ok", False)
    
    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """
        Get chat information.
        
        Args:
            chat_id: Chat ID to query
            
        Returns:
            Chat information dictionary
        """
        payload = {"chat_id": chat_id}
        result = await self._api_call("getChat", payload)
        
        chat_info = result.get("result", {})
        return {
            "id": chat_info.get("id"),
            "type": chat_info.get("type"),
            "title": chat_info.get("title"),
            "username": chat_info.get("username"),
            "first_name": chat_info.get("first_name"),
            "last_name": chat_info.get("last_name"),
            "members_count": chat_info.get("members_count"),
            "description": chat_info.get("description"),
        }
    
    async def send_chat_action(self, chat_id: str, action: str = "typing") -> bool:
        """
        Send chat action (typing, uploading, etc.).
        
        Args:
            chat_id: Chat ID
            action: Action type (typing, upload_photo, record_video, etc.)
            
        Returns:
            True if sent successfully
        """
        payload = {
            "chat_id": chat_id,
            "action": action,
        }
        result = await self._api_call("sendChatAction", payload)
        return result.get("ok", False)


# Singleton instance
_telegram_handler: Optional[TelegramHandler] = None


def get_telegram_handler() -> TelegramHandler:
    """Get the singleton Telegram handler instance."""
    global _telegram_handler
    if _telegram_handler is None:
        _telegram_handler = TelegramHandler()
    return _telegram_handler


def configure_telegram(bot_token: str, default_chat_id: Optional[str] = None, **kwargs) -> TelegramHandler:
    """Configure and return the Telegram handler."""
    handler = get_telegram_handler()
    config = TelegramConfig(bot_token=bot_token, default_chat_id=default_chat_id, **kwargs)
    handler.configure(config)
    return handler
