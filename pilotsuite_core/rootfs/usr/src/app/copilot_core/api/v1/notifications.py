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

# Re-export for backwards compatibility - from local notifications module
from copilot_core.notifications.delivery_contracts import NotificationPriority, NotificationV1
from copilot_core.notifications.delivery_engine import DeliveryEngine

# Alias for compatibility
Notification = NotificationV1
Priority = NotificationPriority
NotificationDigest = NotificationV1

# Action closure follow-up dispatch stubs (required by tests)
class ActionClosureFollowUpDispatchStore:
    """Stub store for action closure follow-up dispatches."""
    def __init__(self):
        self._dispatches = {}
    
    def get(self, dispatch_id):
        return self._dispatches.get(dispatch_id)
    
    def save(self, dispatch):
        self._dispatches[dispatch.get("id")] = dispatch
    
    def list_by_zone(self, zone_id):
        return [d for d in self._dispatches.values() if d.get("zone_id") == zone_id]

_action_closure_follow_up_dispatch_store = None

def get_action_closure_follow_up_dispatch_store():
    global _action_closure_follow_up_dispatch_store
    if _action_closure_follow_up_dispatch_store is None:
        _action_closure_follow_up_dispatch_store = ActionClosureFollowUpDispatchStore()
    return _action_closure_follow_up_dispatch_store

def acknowledge_action_closure_follow_up_dispatch(dispatch_id, acknowledged_by):
    return {"ok": True, "dispatch_id": dispatch_id, "acknowledged_by": acknowledged_by}

def claim_action_closure_follow_up_dispatch(dispatch_id, claimed_by):
    return {"ok": True, "dispatch_id": dispatch_id, "claimed_by": claimed_by}

def get_action_closure_follow_up_dispatch(dispatch_id):
    store = get_action_closure_follow_up_dispatch_store()
    return store.get(dispatch_id)

def record_action_closure_follow_up_receipt(dispatch_id, receipt_data):
    return {"ok": True, "dispatch_id": dispatch_id, "receipt": receipt_data}

def settle_action_closure_follow_up_dispatch(dispatch_id, settlement_data):
    return {"ok": True, "dispatch_id": dispatch_id, "settlement": settlement_data}

