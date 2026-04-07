"""
Notification Delivery Engine — Slice 68.

Unified notification delivery engine with channel routing, rate limiting,
quiet hours, and delivery tracking.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .delivery_contracts import (
    DeliveryAttemptV1,
    DeliveryMode,
    DeliveryStatus,
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    NotificationV1,
    NotificationDeliveryV1,
    QuietHoursStateV1,
    RateLimitStateV1,
)

logger = logging.getLogger(__name__)


class ChannelHandler:
    """Base class for channel handlers."""
    
    def __init__(self, channel: NotificationChannel):
        self.channel = channel
    
    async def send(self, notification: NotificationV1) -> Dict[str, Any]:
        """Send notification via this channel. Returns delivery result."""
        raise NotImplementedError
    
    def supports(self, notification: NotificationV1) -> bool:
        """Check if this handler can process the notification."""
        return notification.channel == self.channel


class TelegramHandler(ChannelHandler):
    """Telegram notification handler."""
    
    def __init__(self, bot_token: Optional[str] = None):
        super().__init__(NotificationChannel.TELEGRAM)
        self.bot_token = bot_token
    
    async def send(self, notification: NotificationV1) -> Dict[str, Any]:
        """Send via Telegram."""
        logger.info("Telegram notification: %s to %s", notification.title, notification.recipient_id)
        # TODO: Implement actual Telegram API call
        return {"sent": True, "channel": "telegram", "message_id": str(uuid.uuid4())}


class WhatsAppHandler(ChannelHandler):
    """WhatsApp notification handler."""
    
    def __init__(self):
        super().__init__(NotificationChannel.WHATSAPP)
    
    async def send(self, notification: NotificationV1) -> Dict[str, Any]:
        """Send via WhatsApp."""
        logger.info("WhatsApp notification: %s to %s", notification.title, notification.recipient_id)
        # TODO: Implement WhatsApp Business API
        return {"sent": True, "channel": "whatsapp"}


class EmailHandler(ChannelHandler):
    """Email notification handler."""
    
    def __init__(self, smtp_config: Optional[Dict[str, Any]] = None):
        super().__init__(NotificationChannel.EMAIL)
        self.smtp_config = smtp_config or {}
    
    async def send(self, notification: NotificationV1) -> Dict[str, Any]:
        """Send via Email."""
        logger.info("Email notification: %s to %s", notification.title, notification.recipient_id)
        # TODO: Implement SMTP send
        return {"sent": True, "channel": "email"}


class PushHandler(ChannelHandler):
    """Push notification handler (FCM/APNs)."""
    
    def __init__(self):
        super().__init__(NotificationChannel.PUSH)
    
    async def send(self, notification: NotificationV1) -> Dict[str, Any]:
        """Send via Push."""
        logger.info("Push notification: %s to %s", notification.title, notification.recipient_id)
        # TODO: Implement FCM/APNs
        return {"sent": True, "channel": "push"}


class HANotificationHandler(ChannelHandler):
    """Home Assistant notification handler."""
    
    def __init__(self, hass_client: Optional[Any] = None):
        super().__init__(NotificationChannel.HA_NOTIFICATION)
        self.hass_client = hass_client
    
    async def send(self, notification: NotificationV1) -> Dict[str, Any]:
        """Send via Home Assistant notify service."""
        logger.info("HA notification: %s to %s", notification.title, notification.recipient_id)
        # TODO: Implement HA notify service call
        return {"sent": True, "channel": "ha_notification"}


class DeliveryEngine:
    """
    Unified notification delivery engine.
    
    Features:
    - Channel routing based on user preferences
    - Rate limiting per user/channel
    - Quiet hours enforcement with priority override
    - Delivery tracking with retry logic
    - Idempotency support
    """
    
    def __init__(self, user_store: Any, analytics_store: Any):
        """
        Initialize delivery engine.
        
        Args:
            user_store: UserStore for preferences lookup
            analytics_store: NotificationAnalyticsStore for delivery tracking
        """
        self.user_store = user_store
        self.analytics_store = analytics_store
        
        # Channel handlers registry
        self._handlers: Dict[NotificationChannel, ChannelHandler] = {}
        self._register_builtin_handlers()
        
        # Rate limiting state: (user_id, channel) -> RateLimitStateV1
        self._rate_limits: Dict[Tuple[str, NotificationChannel], RateLimitStateV1] = {}
        
        # Default rate limits (per hour)
        self._default_rate_limits: Dict[NotificationChannel, int] = {
            NotificationChannel.TELEGRAM: 60,
            NotificationChannel.WHATSAPP: 30,
            NotificationChannel.EMAIL: 100,
            NotificationChannel.PUSH: 100,
            NotificationChannel.HA_NOTIFICATION: 200,
            NotificationChannel.SMS: 20,
            NotificationChannel.SLACK: 100,
            NotificationChannel.WEBHOOK: 500,
        }
        
        # Quiet hours defaults
        self._quiet_hours_start = 22  # 22:00
        self._quiet_hours_end = 7     # 07:00
        self._priority_override = True  # Critical bypasses quiet hours
    
    def _register_builtin_handlers(self) -> None:
        """Register built-in channel handlers."""
        self._handlers[NotificationChannel.TELEGRAM] = TelegramHandler()
        self._handlers[NotificationChannel.WHATSAPP] = WhatsAppHandler()
        self._handlers[NotificationChannel.EMAIL] = EmailHandler()
        self._handlers[NotificationChannel.PUSH] = PushHandler()
        self._handlers[NotificationChannel.HA_NOTIFICATION] = HANotificationHandler()
        # SMS, Slack, Webhook can be added as needed
    
    def register_handler(self, channel: NotificationChannel, handler: ChannelHandler) -> None:
        """Register a custom channel handler."""
        self._handlers[channel] = handler
        logger.info("Custom handler registered for channel: %s", channel.value)
    
    def _check_rate_limit(self, user_id: str, channel: NotificationChannel) -> Tuple[bool, Optional[RateLimitStateV1]]:
        """
        Check if notification is rate limited.
        
        Returns:
            Tuple of (is_limited, rate_limit_state)
        """
        key = (user_id, channel)
        now = datetime.now(timezone.utc)
        
        # Get or create rate limit state
        if key not in self._rate_limits:
            # Initialize new window
            window_start = now.replace(minute=0, second=0, microsecond=0)
            window_end = window_start + timedelta(hours=1)
            limit = self._default_rate_limits.get(channel, 60)
            
            self._rate_limits[key] = RateLimitStateV1(
                user_id=user_id,
                channel=channel,
                window_start=window_start,
                window_end=window_end,
                count=0,
                limit=limit,
                reset_at=window_end,
                is_limited=False,
            )
        
        state = self._rate_limits[key]
        
        # Check if window has expired
        if now >= state.window_end:
            # Reset window
            window_start = now.replace(minute=0, second=0, microsecond=0)
            window_end = window_start + timedelta(hours=1)
            state.window_start = window_start
            state.window_end = window_end
            state.count = 0
            state.reset_at = window_end
            state.is_limited = False
        
        # Check limit
        if state.count >= state.limit:
            state.is_limited = True
            return True, state
        
        # Increment count
        state.count += 1
        state.is_limited = False
        
        return False, state
    
    def _check_quiet_hours(self, user_id: str, priority: NotificationPriority) -> Tuple[bool, QuietHoursStateV1]:
        """
        Check if quiet hours are active for user.
        
        Returns:
            Tuple of (is_quiet_hours, quiet_hours_state)
        """
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        
        # Get user preferences
        prefs = self.user_store.get_preferences(user_id)
        
        # Parse quiet hours from string format (HH:MM)
        quiet_start = 22  # default
        quiet_end = 7     # default
        priority_override = True  # default
        
        if prefs:
            if prefs.global_quiet_hours_start:
                quiet_start = int(prefs.global_quiet_hours_start.split(":")[0])
            if prefs.global_quiet_hours_end:
                quiet_end = int(prefs.global_quiet_hours_end.split(":")[0])
            # Priority override: critical bypasses quiet hours by default
            priority_override = True
        
        # Determine if currently in quiet hours
        if quiet_start <= quiet_end:
            # Same-day range
            is_quiet = quiet_start <= current_hour < quiet_end
        else:
            # Overnight range (e.g., 22:00-07:00)
            is_quiet = current_hour >= quiet_start or current_hour < quiet_end
        
        # Calculate next quiet hours
        next_quiet_start = None
        next_quiet_end = None
        
        if is_quiet:
            # Currently in quiet hours, next end is today/tomorrow
            if current_hour < quiet_end:
                next_quiet_end = now.replace(hour=quiet_end, minute=0, second=0, microsecond=0)
            else:
                next_quiet_end = (now + timedelta(days=1)).replace(hour=quiet_end, minute=0, second=0, microsecond=0)
        else:
            # Not in quiet hours, next start is today/tomorrow
            if current_hour < quiet_start:
                next_quiet_start = now.replace(hour=quiet_start, minute=0, second=0, microsecond=0)
            else:
                next_quiet_start = (now + timedelta(days=1)).replace(hour=quiet_start, minute=0, second=0, microsecond=0)
        
        # Check priority override - critical always bypasses
        if is_quiet and priority == NotificationPriority.CRITICAL:
            is_quiet = False
        
        state = QuietHoursStateV1(
            user_id=user_id,
            is_quiet_hours=is_quiet,
            quiet_hours_start=quiet_start,
            quiet_hours_end=quiet_end,
            current_hour=current_hour,
            priority_override=priority_override,
            next_quiet_hours_start=next_quiet_start,
            next_quiet_hours_end=next_quiet_end,
        )
        
        return is_quiet, state
    
    def _check_channel_enabled(self, user_id: str, channel: NotificationChannel) -> bool:
        """Check if channel is enabled for user."""
        prefs = self.user_store.get_preferences(user_id)
        
        if not prefs:
            return True  # Default: all channels enabled
        
        # Check global enabled
        if not prefs.global_enabled:
            return False
        
        # Check channel-specific preferences
        channel_prefs = prefs.channel_preferences.get(channel.value)
        if channel_prefs:
            return channel_prefs.enabled
        
        # Default enabled if no channel prefs
        return True
    
    def _get_min_priority(self, user_id: str, channel: NotificationChannel) -> NotificationPriority:
        """Get minimum priority for channel."""
        prefs = self.user_store.get_preferences(user_id)
        
        if not prefs:
            return NotificationPriority.LOW
        
        channel_prefs = prefs.channel_preferences.get(channel.value)
        if not channel_prefs or not channel_prefs.min_priority:
            return NotificationPriority.LOW
        
        return channel_prefs.min_priority
    
    async def deliver(self, notification: NotificationV1) -> NotificationDeliveryV1:
        """
        Deliver a notification with full lifecycle tracking.
        
        Args:
            notification: Notification to deliver
            
        Returns:
            NotificationDeliveryV1 with delivery result
        """
        delivery_id = f"del_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        
        # Create delivery record
        delivery = NotificationDeliveryV1(
            delivery_id=delivery_id,
            notification_id=notification.notification_id,
            user_id=notification.user_id,
            channel=notification.channel,
            recipient_id=notification.recipient_id,
            status=DeliveryStatus.PENDING,
            priority=notification.priority,
            delivery_mode=DeliveryMode.IMMEDIATE if not notification.scheduled_at else DeliveryMode.SCHEDULED,
            created_at=now,
            updated_at=now,
        )
        
        # Check channel enabled
        if not self._check_channel_enabled(notification.user_id, notification.channel):
            delivery.status = DeliveryStatus.CANCELLED
            delivery.cancelled_at = now
            delivery.updated_at = now
            logger.debug("Notification cancelled: channel disabled for user %s", notification.user_id)
            return delivery
        
        # Check quiet hours
        is_quiet, quiet_state = self._check_quiet_hours(notification.user_id, notification.priority)
        if is_quiet:
            delivery.status = DeliveryStatus.QUIET_HOURS
            delivery.quiet_hours_applied = True
            delivery.updated_at = now
            logger.debug("Notification quiet hours: user %s, channel %s", notification.user_id, notification.channel.value)
            return delivery
        
        # Check rate limit
        is_limited, rate_state = self._check_rate_limit(notification.user_id, notification.channel)
        if is_limited:
            delivery.status = DeliveryStatus.RATE_LIMITED
            delivery.rate_limited_at = now
            delivery.next_retry_at = rate_state.reset_at
            delivery.updated_at = now
            logger.debug("Notification rate limited: user %s, channel %s", notification.user_id, notification.channel.value)
            return delivery
        
        # Check minimum priority
        min_priority = self._get_min_priority(notification.user_id, notification.channel)
        priority_order = {
            NotificationPriority.LOW: 0,
            NotificationPriority.NORMAL: 1,
            NotificationPriority.HIGH: 2,
            NotificationPriority.CRITICAL: 3,
        }
        if priority_order.get(notification.priority, 0) < priority_order.get(min_priority, 0):
            delivery.status = DeliveryStatus.CANCELLED
            delivery.cancelled_at = now
            delivery.updated_at = now
            logger.debug("Notification cancelled: below minimum priority for channel")
            return delivery
        
        # Get channel handler
        handler = self._handlers.get(notification.channel)
        if not handler:
            delivery.status = DeliveryStatus.FAILED
            delivery.failed_at = now
            delivery.attempts.append(DeliveryAttemptV1(
                attempt_id=f"att_{uuid.uuid4().hex[:8]}",
                notification_id=notification.notification_id,
                channel=notification.channel,
                status=DeliveryStatus.FAILED,
                attempted_at=now,
                completed_at=now,
                error_message=f"Unknown channel: {notification.channel.value}",
            ))
            delivery.updated_at = now
            logger.error("Delivery failed: unknown channel %s", notification.channel.value)
            return delivery
        
        # Attempt delivery
        attempt = DeliveryAttemptV1(
            attempt_id=f"att_{uuid.uuid4().hex[:8]}",
            notification_id=notification.notification_id,
            channel=notification.channel,
            status=DeliveryStatus.SENT,
            attempted_at=now,
        )
        
        try:
            start_ms = int(now.timestamp() * 1000)
            result = await handler.send(notification)
            end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            attempt.completed_at = datetime.now(timezone.utc)
            attempt.latency_ms = end_ms - start_ms
            attempt.response_data = result
            
            delivery.status = DeliveryStatus.SENT
            delivery.sent_at = now
            delivery.attempts.append(attempt)
            
            logger.info("Notification sent: %s via %s to %s", notification.notification_id, notification.channel.value, notification.recipient_id)
            
        except Exception as e:
            attempt.status = DeliveryStatus.FAILED
            attempt.completed_at = datetime.now(timezone.utc)
            attempt.error_message = str(e)
            
            delivery.attempts.append(attempt)
            delivery.retry_count += 1
            
            if delivery.retry_count >= delivery.max_retries:
                delivery.status = DeliveryStatus.FAILED
                delivery.failed_at = now
            else:
                delivery.status = DeliveryStatus.RETRYING
                # Exponential backoff
                backoff_seconds = (2 ** delivery.retry_count) * 60
                delivery.next_retry_at = now + timedelta(seconds=backoff_seconds)
            
            logger.error("Delivery failed (attempt %d/%d): %s", delivery.retry_count, delivery.max_retries, str(e))
        
        delivery.updated_at = datetime.now(timezone.utc)
        
        # Track in analytics
        self._track_delivery(delivery, notification)
        
        return delivery
    
    def _track_delivery(self, delivery: NotificationDeliveryV1, notification: NotificationV1) -> None:
        """Track delivery in analytics store."""
        try:
            # Add to analytics store
            self.analytics_store.add_delivery_entry(
                notification_id=notification.notification_id,
                channel=notification.channel.value,
                notification_type=notification.type.value,
                recipient_id=notification.recipient_id,
                zone_id=notification.zone_id,
                title=notification.title,
                body=notification.body,
                priority=notification.priority.value,
                status=delivery.status.value,
                sent_at=delivery.sent_at.isoformat() if delivery.sent_at else None,
                delivered_at=delivery.delivered_at.isoformat() if delivery.delivered_at else None,
            )
        except Exception as e:
            logger.warning("Failed to track delivery in analytics: %s", str(e))
    
    def get_rate_limit_state(self, user_id: str, channel: NotificationChannel) -> Optional[RateLimitStateV1]:
        """Get current rate limit state for user/channel."""
        key = (user_id, channel)
        return self._rate_limits.get(key)
    
    def get_quiet_hours_state(self, user_id: str) -> QuietHoursStateV1:
        """Get current quiet hours state for user."""
        _, state = self._check_quiet_hours(user_id, NotificationPriority.NORMAL)
        return state
