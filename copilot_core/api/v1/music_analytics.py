"""Music/Media Analytics API — Slice 49."""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

from copilot_core.media.analytics_store import get_music_analytics_store

_LOGGER = logging.getLogger(__name__)

music_analytics_bp = Blueprint("music_analytics", __name__, url_prefix="/api/v1/media/analytics")


# =============================================================================
# API Endpoints
# =============================================================================

@music_analytics_bp.route("/usage", methods=["GET"])
def get_music_usage_history():
    """Music Usage History — mit optionalen Filtern."""
    store = get_music_analytics_store()

    time_range_start = request.args.get("time_range_start")
    time_range_end = request.args.get("time_range_end")
    zone_id = request.args.get("zone_id")
    media_type = request.args.get("media_type")
    limit = int(request.args.get("limit", 100))

    history = store.build_usage_history(
        time_range_start=time_range_start,
        time_range_end=time_range_end,
        zone_id=zone_id,
        media_type=media_type,
        limit=limit,
    )

    return jsonify({
        "entries": [
            {
                "entry_id": e.entry_id,
                "zone_id": e.zone_id,
                "zone_name": e.zone_name,
                "media_type": e.media_type,
                "media_id": e.media_id,
                "media_name": e.media_name,
                "player_id": e.player_id,
                "source": e.source,
                "volume": e.volume,
                "duration_seconds": e.duration_seconds,
                "started_at": e.started_at,
                "ended_at": e.ended_at,
                "created_at": e.created_at,
            }
            for e in history.entries
        ],
        "total_sessions": history.total_sessions,
        "total_duration_seconds": history.total_duration_seconds,
        "avg_duration_seconds": history.avg_duration_seconds,
        "total_sonos_sessions": history.total_sonos_sessions,
        "total_musikwolke_sessions": history.total_musikwolke_sessions,
        "revision": history.revision,
        "latest_change_at": history.latest_change_at,
        "time_range_start": history.time_range_start,
        "time_range_end": history.time_range_end,
    })


@music_analytics_bp.route("/patterns", methods=["GET"])
def get_music_zone_patterns():
    """Music Zone Patterns — zone-spezifische Patterns."""
    store = get_music_analytics_store()

    zone_ids_param = request.args.get("zone_ids")
    zone_ids: Optional[List[str]] = None
    if zone_ids_param:
        zone_ids = zone_ids_param.split(",")

    patterns = store.build_zone_patterns(zone_ids=zone_ids)

    return jsonify({
        "patterns": [
            {
                "zone_id": p.zone_id,
                "zone_name": p.zone_name,
                "total_sessions": p.total_sessions,
                "avg_session_duration_seconds": p.avg_session_duration_seconds,
                "most_used_media_type": p.most_used_media_type,
                "most_common_source": p.most_common_source,
                "avg_volume": p.avg_volume,
                "peak_listening_hour": p.peak_listening_hour,
                "sessions_last_7_days": p.sessions_last_7_days,
                "sessions_last_30_days": p.sessions_last_30_days,
                "favorite_media": p.favorite_media,
            }
            for p in patterns.patterns
        ],
        "total_zones": patterns.total_zones,
        "zones_with_music": patterns.zones_with_music,
        "revision": patterns.revision,
        "latest_change_at": patterns.latest_change_at,
    })


@music_analytics_bp.route("/effectiveness", methods=["GET"])
def get_music_effectiveness_metrics():
    """Music Effectiveness Metrics — Engagement, Diversity, Acceptance-Rates."""
    store = get_music_analytics_store()
    metrics = store.get_effectiveness_metrics()

    return jsonify({
        "total_sessions_analyzed": metrics.total_sessions_analyzed,
        "sessions_by_source": metrics.sessions_by_source,
        "auto_presence_acceptance_rate": metrics.auto_presence_acceptance_rate,
        "schedule_reliability": metrics.schedule_reliability,
        "avg_volume_by_time_of_day": metrics.avg_volume_by_time_of_day,
        "zones_with_regular_usage": metrics.zones_with_regular_usage,
        "zones_with_rare_usage": metrics.zones_with_rare_usage,
        "favorite_diversity_score": metrics.favorite_diversity_score,
        "engagement_score": metrics.engagement_score,
        "revision": metrics.revision,
        "latest_change_at": metrics.latest_change_at,
    })


@music_analytics_bp.route("/summary", methods=["GET"])
def get_music_analytics_summary():
    """Music Analytics Summary — alle Analytics in einer Surface."""
    store = get_music_analytics_store()
    summary = store.build_summary()

    return jsonify({
        "usage": {
            "total_sessions": summary.usage.total_sessions,
            "total_duration_seconds": summary.usage.total_duration_seconds,
            "avg_duration_seconds": summary.usage.avg_duration_seconds,
            "total_sonos_sessions": summary.usage.total_sonos_sessions,
            "total_musikwolke_sessions": summary.usage.total_musikwolke_sessions,
            "revision": summary.usage.revision,
            "latest_change_at": summary.usage.latest_change_at,
        },
        "patterns": {
            "total_zones": summary.patterns.total_zones,
            "zones_with_music": summary.patterns.zones_with_music,
            "revision": summary.patterns.revision,
            "latest_change_at": summary.patterns.latest_change_at,
        },
        "effectiveness": {
            "total_sessions_analyzed": summary.effectiveness.total_sessions_analyzed,
            "engagement_score": summary.effectiveness.engagement_score,
            "favorite_diversity_score": summary.effectiveness.favorite_diversity_score,
            "revision": summary.effectiveness.revision,
            "latest_change_at": summary.effectiveness.latest_change_at,
        },
        "summary_revision": summary.summary_revision,
        "latest_change_at": summary.latest_change_at,
    })
