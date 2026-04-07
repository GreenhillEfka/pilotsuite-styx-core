"""Notifications Analytics API — Slice 52."""

from flask import Blueprint, jsonify, request
from typing import List, Optional

from .analytics_store import get_notification_analytics_store


def create_notification_analytics_blueprint() -> Blueprint:
    """Notification Analytics Blueprint erstellen."""
    bp = Blueprint("notification_analytics", __name__, url_prefix="/api/v1/notifications/analytics")

    @bp.route("/delivery", methods=["GET"])
    def get_delivery_history():
        """Notification-Delivery-Historie abrufen."""
        store = get_notification_analytics_store()

        time_range_start = request.args.get("time_range_start")
        time_range_end = request.args.get("time_range_end")
        channel = request.args.get("channel")
        notification_type = request.args.get("notification_type")
        zone_id = request.args.get("zone_id")
        limit = int(request.args.get("limit", 100))

        history = store.build_delivery_history(
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            channel=channel,
            notification_type=notification_type,
            zone_id=zone_id,
            limit=limit,
        )

        return jsonify({
            "delivery": {
                "entries": [
                    {
                        "entry_id": e.entry_id,
                        "notification_id": e.notification_id,
                        "channel": e.channel,
                        "notification_type": e.notification_type,
                        "recipient_id": e.recipient_id,
                        "zone_id": e.zone_id,
                        "zone_name": e.zone_name,
                        "title": e.title,
                        "body": e.body,
                        "priority": e.priority,
                        "status": e.status,
                        "sent_at": e.sent_at,
                        "delivered_at": e.delivered_at,
                        "read_at": e.read_at,
                        "acknowledged_at": e.acknowledged_at,
                        "failed_reason": e.failed_reason,
                        "retry_count": e.retry_count,
                    }
                    for e in history.entries
                ],
                "total_notifications": history.total_notifications,
                "total_sent": history.total_sent,
                "total_delivered": history.total_delivered,
                "total_failed": history.total_failed,
                "total_read": history.total_read,
                "total_acknowledged": history.total_acknowledged,
                "avg_delivery_time_seconds": history.avg_delivery_time_seconds,
                "revision": history.revision,
                "latest_change_at": history.latest_change_at,
                "time_range_start": history.time_range_start,
                "time_range_end": history.time_range_end,
            }
        })

    @bp.route("/channels", methods=["GET"])
    def get_channel_patterns():
        """Channel-spezifische Notification-Patterns abrufen."""
        store = get_notification_analytics_store()

        channels_param = request.args.get("channels")
        channels: Optional[List[str]] = None
        if channels_param:
            channels = channels_param.split(",")

        patterns = store.build_channel_patterns(channels=channels)

        return jsonify({
            "channels": {
                "patterns": [
                    {
                        "channel": p.channel,
                        "total_notifications": p.total_notifications,
                        "sent_count": p.sent_count,
                        "delivered_count": p.delivered_count,
                        "failed_count": p.failed_count,
                        "read_count": p.read_count,
                        "acknowledged_count": p.acknowledged_count,
                        "avg_delivery_time_seconds": p.avg_delivery_time_seconds,
                        "failure_rate": p.failure_rate,
                        "most_common_type": p.most_common_type,
                        "peak_delivery_hour": p.peak_delivery_hour,
                        "notifications_last_24_hours": p.notifications_last_24_hours,
                        "notifications_last_7_days": p.notifications_last_7_days,
                        "unique_recipients": p.unique_recipients,
                    }
                    for p in patterns.patterns
                ],
                "total_channels": patterns.total_channels,
                "channels_with_activity": patterns.channels_with_activity,
                "revision": patterns.revision,
                "latest_change_at": patterns.latest_change_at,
            }
        })

    @bp.route("/effectiveness", methods=["GET"])
    def get_effectiveness():
        """Notification-Effectiveness-Metriken abrufen."""
        store = get_notification_analytics_store()
        effectiveness = store.get_effectiveness_metrics()

        return jsonify({
            "effectiveness": {
                "total_notifications_analyzed": effectiveness.total_notifications_analyzed,
                "notifications_by_type": effectiveness.notifications_by_type,
                "notifications_by_channel": effectiveness.notifications_by_channel,
                "overall_delivery_rate": effectiveness.overall_delivery_rate,
                "overall_read_rate": effectiveness.overall_read_rate,
                "overall_ack_rate": effectiveness.overall_ack_rate,
                "avg_delivery_time_by_channel": effectiveness.avg_delivery_time_by_channel,
                "failure_rate_by_type": effectiveness.failure_rate_by_type,
                "zones_with_notifications": effectiveness.zones_with_notifications,
                "peak_notification_time": effectiveness.peak_notification_time,
                "engagement_score": effectiveness.engagement_score,
                "revision": effectiveness.revision,
                "latest_change_at": effectiveness.latest_change_at,
            }
        })

    @bp.route("/summary", methods=["GET"])
    def get_summary():
        """Zusammenfassung aller Notification-Analytics abrufen."""
        store = get_notification_analytics_store()
        summary = store.build_summary()

        return jsonify({
            "summary": {
                "delivery": {
                    "total_notifications": summary.usage.total_notifications,
                    "total_sent": summary.usage.total_sent,
                    "total_delivered": summary.usage.total_delivered,
                    "total_failed": summary.usage.total_failed,
                    "total_read": summary.usage.total_read,
                    "total_acknowledged": summary.usage.total_acknowledged,
                    "avg_delivery_time_seconds": summary.usage.avg_delivery_time_seconds,
                    "revision": summary.usage.revision,
                    "latest_change_at": summary.usage.latest_change_at,
                },
                "channels": {
                    "total_channels": summary.patterns.total_channels,
                    "channels_with_activity": summary.patterns.channels_with_activity,
                    "revision": summary.patterns.revision,
                    "latest_change_at": summary.patterns.latest_change_at,
                },
                "effectiveness": {
                    "total_notifications_analyzed": summary.effectiveness.total_notifications_analyzed,
                    "overall_delivery_rate": summary.effectiveness.overall_delivery_rate,
                    "overall_read_rate": summary.effectiveness.overall_read_rate,
                    "overall_ack_rate": summary.effectiveness.overall_ack_rate,
                    "engagement_score": summary.effectiveness.engagement_score,
                    "revision": summary.effectiveness.revision,
                    "latest_change_at": summary.effectiveness.latest_change_at,
                },
                "summary_revision": summary.summary_revision,
                "latest_change_at": summary.latest_change_at,
            }
        })

    return bp
