"""Zone Presence Hold Notifications API for Slice 43.

Provides REST API for zone presence hold notification surface:
- GET /api/v1/presence/holds/notifications - list notifications with filters
- GET /api/v1/presence/holds/notifications/<id> - single notification
- POST /api/v1/presence/holds/notifications/<id>/read - mark as read
- POST /api/v1/presence/holds/notifications/read-all - mark all as read
- GET /api/v1/presence/holds/notifications/summary - aggregated summary
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query

from copilot_core.core.zone_presence_hold_notifications import (
    get_zone_presence_hold_notification_store,
    ZonePresenceHoldNotificationSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/presence/holds/notifications", tags=["presence", "notifications"])


@router.get("")
async def list_hold_notifications(
    zone_id: Optional[str] = Query(None, description="Filter by zone ID"),
    notification_type: Optional[str] = Query(None, description="Filter by notification type"),
    recent_limit: int = Query(20, ge=1, le=100, description="Max recent notifications"),
    since_revision: Optional[int] = Query(None, description="Revision for delta responses"),
) -> Dict[str, Any]:
    """List zone presence hold notifications with optional filters."""
    store = get_zone_presence_hold_notification_store()
    
    summary = store.get_summary(
        zone_id=zone_id,
        notification_type=notification_type,
        recent_limit=recent_limit,
        since_revision=since_revision,
    )
    
    return {
        "contract": "ZonePresenceHoldNotificationsListV1",
        "summary": summary.to_dict(),
        "notifications": [n.to_dict() for n in summary.recent_notifications],
    }


@router.get("/summary")
async def get_hold_notifications_summary(
    zone_id: Optional[str] = Query(None, description="Filter by zone ID"),
    notification_type: Optional[str] = Query(None, description="Filter by notification type"),
    since_revision: Optional[int] = Query(None, description="Revision for delta responses"),
) -> Dict[str, Any]:
    """Get aggregated zone presence hold notification summary."""
    store = get_zone_presence_hold_notification_store()
    
    summary = store.get_summary(
        zone_id=zone_id,
        notification_type=notification_type,
        recent_limit=0,  # No recent items in summary endpoint
        since_revision=since_revision,
    )
    
    return summary.to_dict()


@router.get("/{notification_id}")
async def get_hold_notification(notification_id: str) -> Dict[str, Any]:
    """Get a single zone presence hold notification by ID."""
    store = get_zone_presence_hold_notification_store()
    
    notification = store.get_notification(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {
        "contract": "ZonePresenceHoldNotificationV1",
        "notification": notification.to_dict(),
    }


@router.post("/{notification_id}/read")
async def mark_hold_notification_read(notification_id: str) -> Dict[str, Any]:
    """Mark a zone presence hold notification as read."""
    store = get_zone_presence_hold_notification_store()
    
    if not store.get_notification(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    
    success = store.mark_read(notification_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to mark notification as read")
    
    return {
        "success": True,
        "notification_id": notification_id,
        "status": "read",
    }


@router.post("/read-all")
async def mark_all_hold_notifications_read(
    zone_id: Optional[str] = Query(None, description="Optional zone filter"),
) -> Dict[str, Any]:
    """Mark all zone presence hold notifications as read."""
    store = get_zone_presence_hold_notification_store()
    
    count = store.mark_all_read(zone_id=zone_id)
    
    return {
        "success": True,
        "marked_count": count,
        "zone_id": zone_id,
    }


def setup_routes(app) -> None:
    """Register routes with the FastAPI app."""
    app.include_router(router)
