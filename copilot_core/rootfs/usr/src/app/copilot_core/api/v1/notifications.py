"""Notifications API — Slice 228 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("notifications", __name__, url_prefix="/api/v1")
@bp.get("/notifications/categories")
def get_notification_categories():
    return jsonify({"ok": True, "categories": []})
@bp.get("/notifications/priority-queue")
def get_priority_queue():
    return jsonify({"ok": True, "queue": []})
@bp.post("/notifications/send")
def send_notification():
    data = request.get_json() or {}
    return jsonify({"ok": True, "notification_id": data.get("id")})

# Backwards-compatibility stubs (required by tests)
class NotificationManager:
    pass

def get_notification_manager():
    return NotificationManager()
# Action closure follow-up receipt summary (stub - function called but never implemented)
def _build_action_closure_follow_up_receipt_summary(zone_id=None, recent_limit=10):
    return {"total": 0, "items": [], "summary": "No follow-up receipts"}

def _describe_action_closure_follow_up_receipt_summary(receipt_summary):
    return "No pending follow-ups"
# Re-export for backwards compatibility
from copilot_core.notifications.engine import Notification, Priority, NotificationPriority, NotificationDigest

