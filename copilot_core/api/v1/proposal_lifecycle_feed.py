"""
Proposal Lifecycle Feed API — Zone-Scoped (Slice 34)

Zone-scoped proposal lifecycle feeds for dashboard pollers and system contexts.
"""

from __future__ import annotations

from flask import Blueprint, request, jsonify
from typing import Any

from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine
from copilot_core.proposal_lifecycle_read_model import (
    ZoneProposalFeedStore,
    ZoneProposalFeedV1,
    ZoneProposalFeedSummaryV1,
)


def create_proposal_lifecycle_feed_blueprint(suggestion_engine: AutomationSuggestionEngine) -> Blueprint:
    """Create proposal lifecycle feed blueprint."""
    bp = Blueprint("proposal_lifecycle_feed", __name__, url_prefix="/api/v1/proposals/feed")
    feed_store = ZoneProposalFeedStore(suggestion_engine)

    @bp.route("", methods=["GET"])
    def list_zone_feeds() -> tuple[Any, int] | dict[str, Any]:
        """
        List zone-scoped proposal feeds.

        Query params:
        - zone_id: optional single zone filter
        - zone_ids: optional comma-separated zone list
        - since: optional revision cursor for delta responses
        - include_empty: include zones with no proposals (default: false)
        """
        zone_id = request.args.get("zone_id")
        zone_ids_param = request.args.get("zone_ids")
        since_revision = request.args.get("since", type=int)
        include_empty = request.args.get("include_empty", "false").lower() == "true"

        zone_ids: list[str] | None = None
        if zone_id:
            zone_ids = [zone_id]
        elif zone_ids_param:
            zone_ids = [z.strip() for z in zone_ids_param.split(",") if z.strip()]

        zone_names: dict[str, str] = {}
        try:
            from copilot_core.storage.zone_truth import ZoneTruthStore
            from copilot_core.storage.db import get_db

            db = get_db()
            zone_truth_store = ZoneTruthStore(db)
            zones = zone_truth_store.list_zones()
            for zone in zones:
                zone_names[zone.zone_id] = zone.name
        except Exception:
            pass

        if zone_id:
            feed = feed_store.build_zone_feed(
                zone_id=zone_id,
                zone_name=zone_names.get(zone_id),
            )
            if since_revision is not None and feed.revision <= since_revision:
                return {"revision": feed.revision, "has_changes": False}, 200

            return {
                "revision": feed.revision,
                "has_changes": True,
                "zone_id": feed.zone_id,
                "zone_name": feed.zone_name,
                "proposals": [
                    {
                        "proposal_id": e.proposal_id,
                        "zone_id": e.zone_id,
                        "zone_name": e.zone_name,
                        "status": e.status,
                        "title": e.title,
                        "summary": e.summary,
                        "created_at": e.created_at,
                        "updated_at": e.updated_at,
                        "revision": e.revision,
                        "source": e.source,
                        "confidence": e.confidence,
                        "action_closure_id": e.action_closure_id,
                        "follow_up_dispatch_id": e.follow_up_dispatch_id,
                    }
                    for e in feed.proposals
                ],
                "latest_change_at": feed.latest_change_at,
                "has_pending": feed.has_pending,
                "has_failed": feed.has_failed,
                "has_follow_up_open": feed.has_follow_up_open,
            }, 200

        summary = feed_store.build_zone_feed_summary(
            zone_ids=zone_ids if zone_ids and not include_empty else None,
            zone_names=zone_names,
        )

        if since_revision is not None and summary.revision <= since_revision:
            return {"revision": summary.revision, "has_changes": False}, 200

        zones_data = []
        for zone_feed in summary.zones:
            if not include_empty and not zone_feed.proposals:
                continue
            zones_data.append({
                "zone_id": zone_feed.zone_id,
                "zone_name": zone_feed.zone_name,
                "proposals": [
                    {
                        "proposal_id": e.proposal_id,
                        "zone_id": e.zone_id,
                        "zone_name": e.zone_name,
                        "status": e.status,
                        "title": e.title,
                        "summary": e.summary,
                        "created_at": e.created_at,
                        "updated_at": e.updated_at,
                        "revision": e.revision,
                        "source": e.source,
                        "confidence": e.confidence,
                        "action_closure_id": e.action_closure_id,
                        "follow_up_dispatch_id": e.follow_up_dispatch_id,
                    }
                    for e in zone_feed.proposals
                ],
                "revision": zone_feed.revision,
                "latest_change_at": zone_feed.latest_change_at,
                "has_pending": zone_feed.has_pending,
                "has_failed": zone_feed.has_failed,
                "has_follow_up_open": zone_feed.has_follow_up_open,
            })

        return {
            "revision": summary.revision,
            "has_changes": True,
            "zones": zones_data,
            "total_proposals": summary.total_proposals,
            "zones_with_pending": summary.zones_with_pending,
            "zones_with_failed": summary.zones_with_failed,
            "zones_with_follow_up": summary.zones_with_follow_up,
            "latest_change_at": summary.latest_change_at,
        }, 200

    @bp.route("/zone/<zone_id>", methods=["GET"])
    def get_zone_feed(zone_id: str) -> tuple[Any, int] | dict[str, Any]:
        """
        Get zone-scoped proposal feed for a specific zone.

        Query params:
        - since: optional revision cursor for delta responses
        """
        since_revision = request.args.get("since", type=int)

        zone_name: str | None = None
        try:
            from copilot_core.storage.zone_truth import ZoneTruthStore
            from copilot_core.storage.db import get_db

            db = get_db()
            zone_truth_store = ZoneTruthStore(db)
            zone = zone_truth_store.get_zone(zone_id)
            if zone:
                zone_name = zone.name
        except Exception:
            pass

        feed = feed_store.build_zone_feed(zone_id=zone_id, zone_name=zone_name)

        if since_revision is not None and feed.revision <= since_revision:
            return {"revision": feed.revision, "has_changes": False}, 200

        return {
            "revision": feed.revision,
            "has_changes": True,
            "zone_id": feed.zone_id,
            "zone_name": feed.zone_name,
            "proposals": [
                {
                    "proposal_id": e.proposal_id,
                    "zone_id": e.zone_id,
                    "zone_name": e.zone_name,
                    "status": e.status,
                    "title": e.title,
                    "summary": e.summary,
                    "created_at": e.created_at,
                    "updated_at": e.updated_at,
                    "revision": e.revision,
                    "source": e.source,
                    "confidence": e.confidence,
                    "action_closure_id": e.action_closure_id,
                    "follow_up_dispatch_id": e.follow_up_dispatch_id,
                }
                for e in feed.proposals
            ],
            "latest_change_at": feed.latest_change_at,
            "has_pending": feed.has_pending,
            "has_failed": feed.has_failed,
            "has_follow_up_open": feed.has_follow_up_open,
        }, 200

    return bp
