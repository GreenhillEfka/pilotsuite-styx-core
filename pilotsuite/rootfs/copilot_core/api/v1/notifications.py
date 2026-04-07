"""
Notifications API v1 for PilotSuite Core.

Endpoints:
- POST /api/v1/notifications/send — Send a notification
- GET /api/v1/notifications/status — Get delivery status
- POST /api/v1/notifications/configure — Configure notification channels
- GET /api/v1/notifications/channels — List available channels
- GET /api/v1/notifications/rate-limit — Get rate limit status
- GET /api/v1/notifications/quiet-hours — Get quiet hours status
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...notifications.notification_manager import (
    get_notification_manager,
    NotificationManager,
)
from ...notifications.delivery_contracts import (
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    NotificationV1,
    NotificationDeliveryV1,
    DeliveryStatus,
)

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/v1/notifications")

# Global reference to notification manager (set during app initialization)
_notification_manager: Optional[NotificationManager] = None


def set_notification_manager(manager: NotificationManager) -> None:
    """Set the notification manager instance for API access."""
    global _notification_manager
    _notification_manager = manager
    logger.info("Notifications API: Manager set")


def get_notification_manager_api() -> Optional[NotificationManager]:
    """Get the notification manager instance."""
    return _notification_manager or get_notification_manager()


# =============================================================================
# POST /api/v1/notifications/send — Send a notification
# =============================================================================

@notifications_bp.route("/send", methods=["POST"])
def send_notification():
    """
    Send a notification through specified channel(s).
    
    Request Body:
        title (required): Notification title
        body (required): Notification body text
        channel (required): Target channel (telegram, pushover, email, etc.)
        recipient_id (required): Recipient identifier
        user_id (required): User ID for preferences/rate limiting
        priority (optional): Priority level (low, normal, high, critical). Default: normal
        type (optional): Notification type (alert, info, reminder, etc.). Default: info
        zone_id (optional): Zone ID for context
        action_url (optional): Action URL for buttons
        data (optional): Additional data dictionary
        idempotency_key (optional): Idempotency key to prevent duplicates
        channels (optional): List of channels for multi-send (alternative to channel)
    
    Returns:
        JSON response with delivery result
    """
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ["title", "body", "user_id"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return jsonify({
                "error": f"Missing required fields: {', '.join(missing)}",
                "success": False,
            }), 400
        
        # Channel validation
        channel_str = data.get("channel")
        channels_list = data.get("channels")
        
        if not channel_str and not channels_list:
            return jsonify({
                "error": "Either 'channel' or 'channels' must be provided",
                "success": False,
            }), 400
        
        manager = get_notification_manager_api()
        
        # Parse priority
        priority_str = data.get("priority", "normal").lower()
        try:
            priority = NotificationPriority(priority_str)
        except ValueError:
            return jsonify({
                "error": f"Invalid priority: {priority_str}. Must be one of: low, normal, high, critical",
                "success": False,
            }), 400
        
        # Parse type
        type_str = data.get("type", "info").lower()
        try:
            notification_type = NotificationType(type_str)
        except ValueError:
            return jsonify({
                "error": f"Invalid type: {type_str}. Must be one of: alert, info, reminder, digest, action_required, system",
                "success": False,
            }), 400
        
        # Single channel send
        if channel_str:
            try:
                channel = NotificationChannel(channel_str.lower())
            except ValueError:
                return jsonify({
                    "error": f"Invalid channel: {channel_str}. Available: telegram, pushover, email, ha_notification, webhook",
                    "success": False,
                }), 400
            
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                delivery = loop.run_until_complete(
                    manager.send(
                        title=data["title"],
                        body=data["body"],
                        channel=channel,
                        recipient_id=data.get("recipient_id", ""),
                        user_id=data["user_id"],
                        priority=priority,
                        notification_type=notification_type,
                        zone_id=data.get("zone_id"),
                        action_url=data.get("action_url"),
                        data=data.get("data", {}),
                        idempotency_key=data.get("idempotency_key"),
                        ttl_seconds=data.get("ttl_seconds"),
                    )
                )
            finally:
                loop.close()
            
            return jsonify({
                "success": True,
                "delivery": delivery.to_dict(),
                "message": f"Notification sent via {channel.value}",
            })
        
        # Multi-channel send
        else:
            channel_objects = []
            for ch_str in channels_list:
                try:
                    channel_objects.append(NotificationChannel(ch_str.lower()))
                except ValueError:
                    return jsonify({
                        "error": f"Invalid channel in list: {ch_str}",
                        "success": False,
                    }), 400
            
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    manager.send_to_all_channels(
                        title=data["title"],
                        body=data["body"],
                        user_id=data["user_id"],
                        recipient_id=data.get("recipient_id", ""),
                        priority=priority,
                        notification_type=notification_type,
                        channels=channel_objects,
                        zone_id=data.get("zone_id"),
                        action_url=data.get("action_url"),
                        data=data.get("data", {}),
                    )
                )
            finally:
                loop.close()
            
            return jsonify({
                "success": True,
                "deliveries": {
                    ch.value: delivery.to_dict()
                    for ch, delivery in results.items()
                },
                "message": f"Notification sent via {len(results)} channels",
            })
    
    except Exception as e:
        logger.exception("Error sending notification")
        return jsonify({
            "error": str(e),
            "success": False,
        }), 500


# =============================================================================
# GET /api/v1/notifications/status — Get delivery status
# =============================================================================

@notifications_bp.route("/status", methods=["GET"])
def get_notification_status():
    """
    Get notification delivery status.
    
    Query Parameters:
        delivery_id (optional): Specific delivery ID to query
        notification_id (optional): Filter by notification ID
        user_id (optional): Filter by user ID
        channel (optional): Filter by channel
        limit (optional): Limit results (default: 50)
    
    Returns:
        JSON response with delivery status information
    """
    try:
        delivery_id = request.args.get("delivery_id")
        notification_id = request.args.get("notification_id")
        user_id = request.args.get("user_id")
        channel_str = request.args.get("channel")
        limit = int(request.args.get("limit", 50))
        
        manager = get_notification_manager_api()
        
        # Get channel status overview
        channel_status = manager.get_channel_status()
        
        # Get rate limit state if user_id provided
        rate_limit_info = None
        if user_id and channel_str:
            try:
                channel = NotificationChannel(channel_str.lower())
                rate_limit_state = manager.get_rate_limit_state(user_id, channel)
                if rate_limit_state:
                    rate_limit_info = rate_limit_state.to_dict()
            except ValueError:
                pass
        
        # Get quiet hours state if user_id provided
        quiet_hours_info = None
        if user_id:
            quiet_hours_state = manager.get_quiet_hours_state(user_id)
            quiet_hours_info = quiet_hours_state.to_dict()
        
        # Build response
        response = {
            "channels": channel_status["channels"],
            "delivery_engine": channel_status["delivery_engine"],
            "rate_limit": rate_limit_info,
            "quiet_hours": quiet_hours_info,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add specific delivery info if delivery_id provided
        if delivery_id:
            # TODO: Query delivery store for specific delivery
            response["delivery"] = {
                "delivery_id": delivery_id,
                "note": "Delivery lookup requires delivery_store integration",
            }
        
        return jsonify({
            "success": True,
            "status": response,
        })
    
    except Exception as e:
        logger.exception("Error getting notification status")
        return jsonify({
            "error": str(e),
            "success": False,
        }), 500


# =============================================================================
# POST /api/v1/notifications/configure — Configure notification channels
# =============================================================================

@notifications_bp.route("/configure", methods=["POST"])
def configure_notification():
    """
    Configure a notification channel.
    
    Request Body:
        channel (required): Channel name (pushover, telegram, email, webhook, ha_notification)
        config (required): Channel-specific configuration object
        
        Pushover config:
            api_token (required): Pushover API token
            user_key (required): Pushover user key
            device (optional): Target device
            sound (optional): Notification sound
        
        Telegram config:
            bot_token (required): Telegram Bot API token
            default_chat_id (optional): Default chat ID
            parse_mode (optional): HTML or MarkdownV2
        
        Email config:
            smtp_host (required): SMTP server hostname
            smtp_port (required): SMTP server port
            username (optional): SMTP username
            password (optional): SMTP password
        
        Webhook config:
            url (required): Webhook URL
            headers (optional): HTTP headers dictionary
        
        HA Notification config:
            hass_client (internal): Home Assistant client (auto-injected)
    
    Returns:
        JSON response with configuration status
    """
    try:
        data = request.get_json() or {}
        
        channel_str = data.get("channel")
        config = data.get("config", {})
        
        if not channel_str:
            return jsonify({
                "error": "Missing required field: channel",
                "success": False,
            }), 400
        
        if not config:
            return jsonify({
                "error": "Missing required field: config",
                "success": False,
            }), 400
        
        manager = get_notification_manager_api()
        
        channel_lower = channel_str.lower()
        
        if channel_lower == "pushover":
            if not config.get("api_token") or not config.get("user_key"):
                return jsonify({
                    "error": "Pushover requires api_token and user_key",
                    "success": False,
                }), 400
            
            manager.configure_pushover(
                api_token=config["api_token"],
                user_key=config["user_key"],
                device=config.get("device"),
                sound=config.get("sound"),
            )
            
            return jsonify({
                "success": True,
                "channel": "pushover",
                "message": "Pushover configured successfully",
            })
        
        elif channel_lower == "telegram":
            if not config.get("bot_token"):
                return jsonify({
                    "error": "Telegram requires bot_token",
                    "success": False,
                }), 400
            
            manager.configure_telegram(
                bot_token=config["bot_token"],
                default_chat_id=config.get("default_chat_id"),
                parse_mode=config.get("parse_mode", "HTML"),
            )
            
            return jsonify({
                "success": True,
                "channel": "telegram",
                "message": "Telegram configured successfully",
            })
        
        elif channel_lower == "email":
            if not config.get("smtp_host") or not config.get("smtp_port"):
                return jsonify({
                    "error": "Email requires smtp_host and smtp_port",
                    "success": False,
                }), 400
            
            manager.configure_email(
                smtp_host=config["smtp_host"],
                smtp_port=config["smtp_port"],
                username=config.get("username"),
                password=config.get("password"),
            )
            
            return jsonify({
                "success": True,
                "channel": "email",
                "message": "Email configured successfully",
            })
        
        elif channel_lower == "webhook":
            if not config.get("url"):
                return jsonify({
                    "error": "Webhook requires url",
                    "success": False,
                }), 400
            
            manager.configure_webhook(
                url=config["url"],
                headers=config.get("headers", {}),
            )
            
            return jsonify({
                "success": True,
                "channel": "webhook",
                "message": "Webhook configured successfully",
            })
        
        elif channel_lower == "ha_notification":
            # HA notification requires hass_client which should be injected
            # This endpoint mainly confirms the channel is available
            manager.configure_ha_notification(hass_client=None)
            
            return jsonify({
                "success": True,
                "channel": "ha_notification",
                "message": "HA Notification channel enabled (requires hass_client injection)",
            })
        
        else:
            return jsonify({
                "error": f"Unknown channel: {channel_str}. Available: pushover, telegram, email, webhook, ha_notification",
                "success": False,
            }), 400
    
    except Exception as e:
        logger.exception("Error configuring notification channel")
        return jsonify({
            "error": str(e),
            "success": False,
        }), 500


# =============================================================================
# GET /api/v1/notifications/channels — List available channels
# =============================================================================

@notifications_bp.route("/channels", methods=["GET"])
def list_channels():
    """
    List available notification channels and their status.
    
    Returns:
        JSON response with channel list and configuration status
    """
    try:
        manager = get_notification_manager_api()
        channel_status = manager.get_channel_status()
        
        channels = []
        for channel_name, status in channel_status["channels"].items():
            channels.append({
                "name": channel_name,
                "enabled": status["enabled"],
                "configured": status["configured"],
            })
        
        return jsonify({
            "success": True,
            "channels": channels,
            "total": len(channels),
            "enabled_count": len([c for c in channels if c["enabled"]]),
        })
    
    except Exception as e:
        logger.exception("Error listing channels")
        return jsonify({
            "error": str(e),
            "success": False,
        }), 500


# =============================================================================
# GET /api/v1/notifications/rate-limit — Get rate limit status
# =============================================================================

@notifications_bp.route("/rate-limit", methods=["GET"])
def get_rate_limit():
    """
    Get rate limit status for a user/channel.
    
    Query Parameters:
        user_id (required): User ID
        channel (optional): Channel name (returns all if not specified)
    
    Returns:
        JSON response with rate limit information
    """
    try:
        user_id = request.args.get("user_id")
        channel_str = request.args.get("channel")
        
        if not user_id:
            return jsonify({
                "error": "Missing required parameter: user_id",
                "success": False,
            }), 400
        
        manager = get_notification_manager_api()
        
        if channel_str:
            try:
                channel = NotificationChannel(channel_str.lower())
                state = manager.get_rate_limit_state(user_id, channel)
                
                return jsonify({
                    "success": True,
                    "user_id": user_id,
                    "channel": channel_str,
                    "rate_limit": state.to_dict() if state else None,
                })
            except ValueError:
                return jsonify({
                    "error": f"Invalid channel: {channel_str}",
                    "success": False,
                }), 400
        else:
            # Return all channels
            all_states = {}
            for channel in NotificationChannel:
                state = manager.get_rate_limit_state(user_id, channel)
                if state:
                    all_states[channel.value] = state.to_dict()
            
            return jsonify({
                "success": True,
                "user_id": user_id,
                "rate_limits": all_states,
            })
    
    except Exception as e:
        logger.exception("Error getting rate limit")
        return jsonify({
            "error": str(e),
            "success": False,
        }), 500


# =============================================================================
# GET /api/v1/notifications/quiet-hours — Get quiet hours status
# =============================================================================

@notifications_bp.route("/quiet-hours", methods=["GET"])
def get_quiet_hours():
    """
    Get quiet hours status for a user.
    
    Query Parameters:
        user_id (required): User ID
    
    Returns:
        JSON response with quiet hours information
    """
    try:
        user_id = request.args.get("user_id")
        
        if not user_id:
            return jsonify({
                "error": "Missing required parameter: user_id",
                "success": False,
            }), 400
        
        manager = get_notification_manager_api()
        state = manager.get_quiet_hours_state(user_id)
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "quiet_hours": state.to_dict(),
        })
    
    except Exception as e:
        logger.exception("Error getting quiet hours")
        return jsonify({
            "error": str(e),
            "success": False,
        }), 500


# =============================================================================
# POST /api/v1/notifications/quiet-hours/set — Set quiet hours
# =============================================================================

@notifications_bp.route("/quiet-hours/set", methods=["POST"])
def set_quiet_hours():
    """
    Set quiet hours globally.
    
    Request Body:
        start_hour (required): Start hour (0-23)
        end_hour (required): End hour (0-23)
    
    Returns:
        JSON response with confirmation
    """
    try:
        data = request.get_json() or {}
        
        start_hour = data.get("start_hour")
        end_hour = data.get("end_hour")
        
        if start_hour is None or end_hour is None:
            return jsonify({
                "error": "Missing required fields: start_hour, end_hour",
                "success": False,
            }), 400
        
        if not (0 <= start_hour <= 23) or not (0 <= end_hour <= 23):
            return jsonify({
                "error": "Hours must be between 0 and 23",
                "success": False,
            }), 400
        
        manager = get_notification_manager_api()
        manager.set_quiet_hours(start_hour, end_hour)
        
        return jsonify({
            "success": True,
            "quiet_hours": {
                "start": start_hour,
                "end": end_hour,
                "display": f"{start_hour:02d}:00 - {end_hour:02d}:00",
            },
            "message": f"Quiet hours set to {start_hour:02d}:00 - {end_hour:02d}:00",
        })
    
    except Exception as e:
        logger.exception("Error setting quiet hours")
        return jsonify({
            "error": str(e),
            "success": False,
        }), 500


__all__ = [
    "notifications_bp",
    "set_notification_manager",
    "get_notification_manager_api",
]
