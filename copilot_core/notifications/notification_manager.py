"""
Unified Notification Manager for PilotSuite Core.

Provides a single API for sending notifications across multiple channels
(Pushover, Telegram, Email, etc.) with configuration management,
channel routing, and delivery tracking.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable, Awaitable

from .delivery_contracts import (
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    NotificationV1,
    NotificationDeliveryV1,
    DeliveryStatus,
    DeliveryAttemptV1,
    DeliveryMode,
    RateLimitStateV1,
    QuietHoursStateV1,
)
from .delivery_engine import DeliveryEngine
from .pushover import PushoverHandler, PushoverConfig, get_pushover_handler, configure_pushover
from .telegram_notify import TelegramHandler, TelegramConfig, get_telegram_handler, configure_telegram

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Unified notification manager for PilotSuite Core.
    
    Features:
    - Multi-channel support (Pushover, Telegram, Email, etc.)
    - Configuration management per channel
    - User preference integration
    - Rate limiting and quiet hours
    - Delivery tracking and analytics
    - Priority-based routing
    """
    
    def __init__(
        self,
        user_store: Optional[Any] = None,
        analytics_store: Optional[Any] = None,
        delivery_engine: Optional[DeliveryEngine] = None,
    ):
        """
        Initialize notification manager.
        
        Args:
            user_store: UserStore for preferences lookup
            analytics_store: AnalyticsStore for delivery tracking
            delivery_engine: Optional pre-configured DeliveryEngine
        """
        self.user_store = user_store
        self.analytics_store = analytics_store
        
        # Initialize delivery engine
        self.delivery_engine = delivery_engine or DeliveryEngine(
            user_store=user_store,
            analytics_store=analytics_store,
        )
        
        # Channel handlers
        self._pushover: Optional[PushoverHandler] = None
        self._telegram: Optional[TelegramHandler] = None
        
        # Channel configuration state
        self._channel_configs: Dict[NotificationChannel, Dict[str, Any]] = {}
        self._channel_enabled: Dict[NotificationChannel, bool] = {
            NotificationChannel.PUSHOVER: False,
            NotificationChannel.TELEGRAM: False,
            NotificationChannel.EMAIL: False,
            NotificationChannel.HA_NOTIFICATION: False,
            NotificationChannel.WEBHOOK: False,
        }
        
        # Register channel handlers with delivery engine
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Register channel handlers with the delivery engine."""
        # Pushover handler (maps to PUSH channel)
        self._pushover = get_pushover_handler()
        self.delivery_engine._handlers[NotificationChannel.PUSH] = self._pushover
        
        # Telegram handler
        self._telegram = get_telegram_handler()
        self.delivery_engine._handlers[NotificationChannel.TELEGRAM] = self._telegram
        
        logger.info("Notification manager: channel handlers registered")
    
    # =========================================================================
    # Configuration Methods
    # =========================================================================
    
    def configure_pushover(self, api_token: str, user_key: str, **kwargs) -> None:
        """
        Configure Pushover integration.
        
        Args:
            api_token: Pushover API token
            user_key: Pushover user key
            **kwargs: Additional PushoverConfig options
        """
        self._pushover = configure_pushover(api_token, user_key, **kwargs)
        self._channel_enabled[NotificationChannel.PUSH] = True
        self._channel_configs[NotificationChannel.PUSH] = {
            "api_token": api_token[:10] + "...",
            "user_key": user_key[:8] + "...",
            **kwargs,
        }
        logger.info("Pushover configured and enabled")
    
    def configure_telegram(self, bot_token: str, default_chat_id: Optional[str] = None, **kwargs) -> None:
        """
        Configure Telegram integration.
        
        Args:
            bot_token: Telegram Bot API token
            default_chat_id: Default chat ID for notifications
            **kwargs: Additional TelegramConfig options
        """
        self._telegram = configure_telegram(bot_token, default_chat_id, **kwargs)
        self._channel_enabled[NotificationChannel.TELEGRAM] = True
        self._channel_configs[NotificationChannel.TELEGRAM] = {
            "bot_token": bot_token[:10] + "...",
            "default_chat_id": default_chat_id,
            **kwargs,
        }
        logger.info("Telegram configured and enabled")
    
    def configure_email(self, smtp_host: str, smtp_port: int, **kwargs) -> None:
        """
        Configure Email integration.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            **kwargs: Additional email configuration
        """
        self._channel_configs[NotificationChannel.EMAIL] = {
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            **kwargs,
        }
        self._channel_enabled[NotificationChannel.EMAIL] = True
        logger.info("Email configured and enabled")
    
    def configure_webhook(self, url: str, headers: Optional[Dict[str, str]] = None) -> None:
        """
        Configure Webhook integration.
        
        Args:
            url: Webhook URL
            headers: Optional HTTP headers
        """
        self._channel_configs[NotificationChannel.WEBHOOK] = {
            "url": url,
            "headers": headers or {},
        }
        self._channel_enabled[NotificationChannel.WEBHOOK] = True
        logger.info("Webhook configured and enabled")
    
    def configure_ha_notification(self, hass_client: Any) -> None:
        """
        Configure Home Assistant notification integration.
        
        Args:
            hass_client: Home Assistant client instance
        """
        self._channel_configs[NotificationChannel.HA_NOTIFICATION] = {
            "hass_client": hass_client,
        }
        self._channel_enabled[NotificationChannel.HA_NOTIFICATION] = True
        logger.info("HA Notification configured and enabled")
    
    def is_channel_enabled(self, channel: NotificationChannel) -> bool:
        """Check if a channel is enabled."""
        return self._channel_enabled.get(channel, False)
    
    def get_channel_status(self) -> Dict[str, Any]:
        """Get status of all channels."""
        return {
            "channels": {
                channel.value: {
                    "enabled": self._channel_enabled.get(channel, False),
                    "configured": bool(self._channel_configs.get(channel)),
                    "config": self._channel_configs.get(channel, {}),
                }
                for channel in NotificationChannel
            },
            "delivery_engine": {
                "rate_limits": len(self.delivery_engine._rate_limits),
                "quiet_hours_start": self.delivery_engine._quiet_hours_start,
                "quiet_hours_end": self.delivery_engine._quiet_hours_end,
            },
        }
    
    # =========================================================================
    # Notification Sending Methods
    # =========================================================================
    
    async def send(
        self,
        title: str,
        body: str,
        channel: NotificationChannel,
        recipient_id: str,
        user_id: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        notification_type: NotificationType = NotificationType.INFO,
        zone_id: Optional[str] = None,
        action_url: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        scheduled_at: Optional[datetime] = None,
    ) -> NotificationDeliveryV1:
        """
        Send a notification through the specified channel.
        
        Args:
            title: Notification title
            body: Notification body text
            channel: Target notification channel
            recipient_id: Recipient identifier (chat_id, user_key, email, etc.)
            user_id: User ID for preferences/rate limiting
            priority: Notification priority
            notification_type: Type of notification
            zone_id: Optional zone ID for context
            action_url: Optional action URL
            data: Optional additional data
            idempotency_key: Optional idempotency key
            ttl_seconds: Optional TTL
            scheduled_at: Optional scheduled delivery time
            
        Returns:
            NotificationDeliveryV1 with delivery result
        """
        notification_id = idempotency_key or f"notif_{uuid.uuid4().hex[:12]}"
        
        notification = NotificationV1(
            notification_id=notification_id,
            type=notification_type,
            priority=priority,
            channel=channel,
            recipient_id=recipient_id,
            user_id=user_id,
            zone_id=zone_id,
            title=title,
            body=body,
            data=data or {},
            action_url=action_url,
            idempotency_key=idempotency_key,
            ttl_seconds=ttl_seconds,
            scheduled_at=scheduled_at,
        )
        
        # Check channel is enabled
        if not self._channel_enabled.get(channel, False):
            logger.warning("Notification cancelled: channel %s not enabled", channel.value)
            # Return cancelled delivery
            now = datetime.now(timezone.utc)
            return NotificationDeliveryV1(
                delivery_id=f"del_{uuid.uuid4().hex[:12]}",
                notification_id=notification_id,
                user_id=user_id,
                channel=channel,
                recipient_id=recipient_id,
                status=DeliveryStatus.CANCELLED,
                priority=priority,
                delivery_mode=DeliveryMode.SCHEDULED if scheduled_at else DeliveryMode.IMMEDIATE,
                cancelled_at=now,
                created_at=now,
                updated_at=now,
            )
        
        # Deliver via engine
        delivery = await self.delivery_engine.deliver(notification)
        
        logger.info(
            "Notification sent: %s via %s to %s (status: %s)",
            notification_id,
            channel.value,
            recipient_id,
            delivery.status.value,
        )
        
        return delivery
    
    async def send_to_all_channels(
        self,
        title: str,
        body: str,
        user_id: str,
        recipient_id: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        notification_type: NotificationType = NotificationType.INFO,
        channels: Optional[List[NotificationChannel]] = None,
        **kwargs,
    ) -> Dict[NotificationChannel, NotificationDeliveryV1]:
        """
        Send notification to multiple channels.
        
        Args:
            title: Notification title
            body: Notification body
            user_id: User ID
            recipient_id: Recipient identifier
            priority: Priority level
            notification_type: Notification type
            channels: List of channels (default: all enabled)
            **kwargs: Additional send() arguments
            
        Returns:
            Dictionary mapping channels to delivery results
        """
        if channels is None:
            channels = [ch for ch, enabled in self._channel_enabled.items() if enabled]
        
        results = {}
        for channel in channels:
            try:
                delivery = await self.send(
                    title=title,
                    body=body,
                    channel=channel,
                    recipient_id=recipient_id,
                    user_id=user_id,
                    priority=priority,
                    notification_type=notification_type,
                    **kwargs,
                )
                results[channel] = delivery
            except Exception as e:
                logger.exception("Failed to send via %s: %s", channel.value, str(e))
                # Create failed delivery record
                now = datetime.now(timezone.utc)
                results[channel] = NotificationDeliveryV1(
                    delivery_id=f"del_{uuid.uuid4().hex[:12]}",
                    notification_id=f"notif_{uuid.uuid4().hex[:12]}",
                    user_id=user_id,
                    channel=channel,
                    recipient_id=recipient_id,
                    status=DeliveryStatus.FAILED,
                    priority=priority,
                    delivery_mode=DeliveryMode.IMMEDIATE,
                    failed_at=now,
                    created_at=now,
                    updated_at=now,
                )
        
        return results
    
    async def send_alert(
        self,
        title: str,
        body: str,
        channel: NotificationChannel,
        recipient_id: str,
        user_id: str,
        zone_id: Optional[str] = None,
        action_url: Optional[str] = None,
    ) -> NotificationDeliveryV1:
        """Send a high-priority alert notification."""
        return await self.send(
            title=title,
            body=body,
            channel=channel,
            recipient_id=recipient_id,
            user_id=user_id,
            priority=NotificationPriority.HIGH,
            notification_type=NotificationType.ALERT,
            zone_id=zone_id,
            action_url=action_url,
        )
    
    async def send_critical(
        self,
        title: str,
        body: str,
        channel: NotificationChannel,
        recipient_id: str,
        user_id: str,
        zone_id: Optional[str] = None,
        action_url: Optional[str] = None,
    ) -> NotificationDeliveryV1:
        """Send a critical priority notification (bypasses quiet hours)."""
        return await self.send(
            title=title,
            body=body,
            channel=channel,
            recipient_id=recipient_id,
            user_id=user_id,
            priority=NotificationPriority.CRITICAL,
            notification_type=NotificationType.ALERT,
            zone_id=zone_id,
            action_url=action_url,
        )
    
    async def send_info(
        self,
        title: str,
        body: str,
        channel: NotificationChannel,
        recipient_id: str,
        user_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> NotificationDeliveryV1:
        """Send a low-priority informational notification."""
        return await self.send(
            title=title,
            body=body,
            channel=channel,
            recipient_id=recipient_id,
            user_id=user_id,
            priority=NotificationPriority.LOW,
            notification_type=NotificationType.INFO,
            data=data,
        )
    
    # =========================================================================
    # Status and Management Methods
    # =========================================================================
    
    def get_rate_limit_state(self, user_id: str, channel: NotificationChannel) -> Optional[RateLimitStateV1]:
        """Get current rate limit state for user/channel."""
        return self.delivery_engine.get_rate_limit_state(user_id, channel)
    
    def get_quiet_hours_state(self, user_id: str) -> QuietHoursStateV1:
        """Get current quiet hours state for user."""
        return self.delivery_engine.get_quiet_hours_state(user_id)
    
    def set_quiet_hours(self, start_hour: int, end_hour: int) -> None:
        """
        Set quiet hours for all users.
        
        Args:
            start_hour: Start hour (0-23)
            end_hour: End hour (0-23)
        """
        self.delivery_engine._quiet_hours_start = start_hour
        self.delivery_engine._quiet_hours_end = end_hour
        logger.info("Quiet hours set: %02d:00 - %02d:00", start_hour, end_hour)
    
    def set_rate_limit(self, channel: NotificationChannel, limit_per_hour: int) -> None:
        """
        Set rate limit for a channel.
        
        Args:
            channel: Notification channel
            limit_per_hour: Maximum notifications per hour
        """
        self.delivery_engine._default_rate_limits[channel] = limit_per_hour
        logger.info("Rate limit set for %s: %d/hour", channel.value, limit_per_hour)
    
    async def close(self) -> None:
        """Close all channel handlers and cleanup resources."""
        if self._pushover:
            await self._pushover.close()
        if self._telegram:
            await self._telegram.close()
        logger.info("Notification manager closed")


# Singleton instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get the singleton NotificationManager instance."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def initialize_notification_manager(
    user_store: Optional[Any] = None,
    analytics_store: Optional[Any] = None,
    pushover_config: Optional[Dict[str, str]] = None,
    telegram_config: Optional[Dict[str, str]] = None,
) -> NotificationManager:
    """
    Initialize the notification manager with configuration.
    
    Args:
        user_store: UserStore for preferences
        analytics_store: AnalyticsStore for tracking
        pushover_config: Optional Pushover configuration
        telegram_config: Optional Telegram configuration
        
    Returns:
        Configured NotificationManager instance
    """
    global _notification_manager
    _notification_manager = NotificationManager(
        user_store=user_store,
        analytics_store=analytics_store,
    )
    
    if pushover_config:
        _notification_manager.configure_pushover(
            api_token=pushover_config.get("api_token", ""),
            user_key=pushover_config.get("user_key", ""),
        )
    
    if telegram_config:
        _notification_manager.configure_telegram(
            bot_token=telegram_config.get("bot_token", ""),
            default_chat_id=telegram_config.get("default_chat_id"),
        )
    
    return _notification_manager
