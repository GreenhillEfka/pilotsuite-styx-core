"""Calendar Notifications API Endpoints — Slice 69."""

from flask import Blueprint, request, jsonify
import logging
from datetime import datetime
from typing import Optional

from copilot_core.api.security import require_token
from copilot_core.notifications.calendar_notifications import (
    CalendarNotificationStore,
    CalendarNotificationType,
    NotificationPriority,
)

logger = logging.getLogger(__name__)


def create_calendar_notifications_blueprint(store: CalendarNotificationStore) -> Blueprint:
    """Create and configure calendar notifications blueprint."""
    bp = Blueprint("calendar_notifications", __name__, url_prefix="/api/v1/notifications/calendar")

    @bp.route("/digest", methods=["GET"])
    @require_token
    def get_digest():
        """Get calendar notification digest for workers."""
        since_revision = request.args.get("since_revision")
        status_filter = request.args.get("status")
        
        digest = store.get_digest(
            since_revision=int(since_revision) if since_revision else None,
            status_filter=status_filter,
        )
        
        return jsonify({
            "notifications": [
                {
                    "notification_id": n.notification_id,
                    "suggestion_id": n.suggestion_id,
                    "notification_type": n.notification_type,
                    "priority": n.priority,
                    "title": n.title,
                    "message": n.message,
                    "zone_id": n.zone_id,
                    "event_id": n.event_id,
                    "created_at": n.created_at,
                    "expires_at": n.expires_at,
                    "status": n.status,
                    "revision": n.revision,
                }
                for n in digest.notifications
            ],
            "total_count": digest.total_count,
            "pending_count": digest.pending_count,
            "revision": digest.revision,
            "latest_change_at": digest.latest_change_at,
            "has_changes": digest.has_changes,
        })

    @bp.route("/dispatch", methods=["GET"])
    @require_token
    def get_dispatch():
        """Get dispatch candidates for notification workers."""
        delivery_mode = request.args.get("delivery_mode", "immediate")
        recent_limit = int(request.args.get("limit", 50))
        since_revision = request.args.get("since_revision")
        
        digest = store.get_digest(since_revision=int(since_revision) if since_revision else None)
        candidates = [
            store.create_dispatch_candidate(n, delivery_mode)
            for n in digest.notifications[:recent_limit]
        ]
        
        return jsonify({
            "candidates": [
                {
                    "dispatch_id": c.dispatch_id,
                    "notification_id": c.notification_id,
                    "suggestion_id": c.suggestion_id,
                    "notification_type": c.notification_type,
                    "priority": c.priority,
                    "delivery_mode": c.delivery_mode,
                    "zone_id": c.zone_id,
                    "title": c.title,
                    "message": c.message,
                    "metadata": c.metadata,
                    "created_at": c.created_at,
                    "revision": c.revision,
                }
                for c in candidates
            ],
            "total_count": len(candidates),
            "revision": digest.revision,
        })

    @bp.route("/dispatch/claim", methods=["POST"])
    @require_token
    def claim_dispatch():
        """Claim a dispatch for processing."""
        data = request.get_json() or {}
        dispatch_id = data.get("dispatch_id")
        worker_id = data.get("worker_id", "unknown")
        lease_seconds = data.get("lease_seconds", 300)
        
        if not dispatch_id:
            return jsonify({"error": "dispatch_id required"}), 400
        
        claim = store.claim_dispatch(dispatch_id, worker_id, lease_seconds)
        
        return jsonify({
            "claim_id": claim.claim_id,
            "dispatch_id": claim.dispatch_id,
            "notification_id": claim.notification_id,
            "claimed_by": claim.claimed_by,
            "claimed_at": claim.claimed_at,
            "lease_seconds": claim.lease_seconds,
            "expires_at": claim.expires_at,
            "status": claim.status,
        })

    @bp.route("/claims", methods=["GET"])
    @require_token
    def get_claims():
        """Get summary of all claims."""
        since_revision = request.args.get("since_revision")
        summary = store.get_claim_summary(
            since_revision=int(since_revision) if since_revision else None,
        )
        
        return jsonify({
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "dispatch_id": c.dispatch_id,
                    "notification_id": c.notification_id,
                    "claimed_by": c.claimed_by,
                    "claimed_at": c.claimed_at,
                    "lease_seconds": c.lease_seconds,
                    "expires_at": c.expires_at,
                    "status": c.status,
                    "settlement": c.settlement,
                }
                for c in summary.claims
            ],
            "total_count": summary.total_count,
            "active_count": summary.active_count,
            "expired_count": summary.expired_count,
            "reassignable_count": summary.reassignable_count,
            "revision": summary.revision,
            "latest_change_at": summary.latest_change_at,
        })

    @bp.route("/claims/<claim_id>/release", methods=["POST"])
    @require_token
    def release_claim(claim_id: str):
        """Release a claim without settlement."""
        store.release_claim(claim_id)
        return jsonify({"claim_id": claim_id, "status": "released"})

    @bp.route("/claims/<claim_id>/settle", methods=["POST"])
    @require_token
    def settle_claim(claim_id: str):
        """Settle a claim with result."""
        data = request.get_json() or {}
        settlement = {
            "result": data.get("result", "completed"),
            "delivered_at": data.get("delivered_at"),
            "failure_reason": data.get("failure_reason"),
            "metadata": data.get("metadata", {}),
        }
        store.settle_claim(claim_id, settlement)
        return jsonify({"claim_id": claim_id, "status": "settled", "settlement": settlement})

    @bp.route("/receipts", methods=["GET"])
    @require_token
    def get_receipts():
        """Get summary of all delivery receipts."""
        since_revision = request.args.get("since_revision")
        summary = store.get_receipt_summary(
            since_revision=int(since_revision) if since_revision else None,
        )
        
        return jsonify({
            "receipts": [
                {
                    "receipt_id": r.receipt_id,
                    "dispatch_id": r.dispatch_id,
                    "notification_id": r.notification_id,
                    "delivery_status": r.delivery_status,
                    "delivered_at": r.delivered_at,
                    "read_at": r.read_at,
                    "acknowledged_at": r.acknowledged_at,
                    "failure_reason": r.failure_reason,
                    "retry_count": r.retry_count,
                    "next_retry_at": r.next_retry_at,
                    "metadata": r.metadata,
                }
                for r in summary.receipts
            ],
            "total_count": summary.total_count,
            "delivered_count": summary.delivered_count,
            "failed_count": summary.failed_count,
            "pending_count": summary.pending_count,
            "revision": summary.revision,
            "latest_change_at": summary.latest_change_at,
        })

    @bp.route("/dispatch/receipt", methods=["POST"])
    @require_token
    def record_receipt():
        """Record a delivery receipt."""
        data = request.get_json() or {}
        dispatch_id = data.get("dispatch_id")
        notification_id = data.get("notification_id")
        delivery_status = data.get("delivery_status", "sent")
        metadata = data.get("metadata", {})
        
        if not dispatch_id or not notification_id:
            return jsonify({"error": "dispatch_id and notification_id required"}), 400
        
        receipt = store.record_receipt(dispatch_id, notification_id, delivery_status, metadata)
        
        return jsonify({
            "receipt_id": receipt.receipt_id,
            "dispatch_id": receipt.dispatch_id,
            "notification_id": receipt.notification_id,
            "delivery_status": receipt.delivery_status,
            "delivered_at": receipt.delivered_at,
            "revision": receipt.revision,
        })

    @bp.route("/create", methods=["POST"])
    @require_token
    def create_notification():
        """Create a new calendar notification from a suggestion."""
        data = request.get_json() or {}
        suggestion_id = data.get("suggestion_id")
        notification_type = data.get("notification_type")
        priority = data.get("priority", "medium")
        title = data.get("title")
        message = data.get("message")
        zone_id = data.get("zone_id")
        event_id = data.get("event_id")
        expires_at = data.get("expires_at")
        metadata = data.get("metadata", {})
        
        if not suggestion_id or not notification_type or not title or not message:
            return jsonify({"error": "suggestion_id, notification_type, title, message required"}), 400
        
        notification = store.create_notification(
            suggestion_id=suggestion_id,
            notification_type=notification_type,
            priority=priority,
            title=title,
            message=message,
            zone_id=zone_id,
            event_id=event_id,
            expires_at=expires_at,
            metadata=metadata,
        )
        
        return jsonify({
            "notification_id": notification.notification_id,
            "suggestion_id": notification.suggestion_id,
            "notification_type": notification.notification_type,
            "priority": notification.priority,
            "title": notification.title,
            "message": notification.message,
            "status": notification.status,
            "revision": notification.revision,
        }), 201

    return bp
