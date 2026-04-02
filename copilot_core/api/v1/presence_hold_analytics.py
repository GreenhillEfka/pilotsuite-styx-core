"""Presence Hold Analytics API — Usage, Patterns, Effectiveness."""

from __future__ import annotations

from typing import Any, Dict, Optional
from flask import Blueprint, jsonify, request

from copilot_core.core.zone_presence_hold import get_zone_presence_hold_store
from copilot_core.presence.hold_analytics import HoldAnalyticsStore

presence_hold_analytics_bp = Blueprint("presence_hold_analytics", __name__, url_prefix="/presence/holds/analytics")


def _get_analytics_store() -> HoldAnalyticsStore:
    """Get HoldAnalyticsStore instance."""
    hold_store = get_zone_presence_hold_store()
    return HoldAnalyticsStore(hold_store=hold_store)


@presence_hold_analytics_bp.route("/usage", methods=["GET"])
def get_hold_usage_history() -> tuple[Any, int]:
    """
    Get Hold-Usage-Historie mit optionalen Filtern.
    
    Query params:
    - zone_id: Optional zone filter
    - time_range_start: Start of time range (ISO-8601)
    - time_range_end: End of time range (ISO-8601)
    - limit: Max entries (default 100, max 1000)
    
    Response: HoldUsageHistoryV1 with revision tracking.
    """
    zone_id: Optional[str] = request.args.get("zone_id")
    time_range_start: Optional[str] = request.args.get("time_range_start")
    time_range_end: Optional[str] = request.args.get("time_range_end")
    
    limit = 100
    if request.args.get("limit"):
        try:
            limit = int(request.args.get("limit", "100"))
            limit = max(1, min(limit, 1000))
        except (ValueError, TypeError):
            pass
    
    store = _get_analytics_store()
    
    try:
        result = store.build_usage_history(
            zone_id=zone_id,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            limit=limit,
        )
        return jsonify(result.to_dict() if hasattr(result, "to_dict") else {
            "entries": [e.__dict__ if hasattr(e, "__dict__") else str(e) for e in result.entries],
            "total_holds": result.total_holds,
            "total_force_on": result.total_force_on,
            "total_force_off": result.total_force_off,
            "total_auto": result.total_auto,
            "total_expired": result.total_expired,
            "total_manually_released": result.total_manually_released,
            "avg_duration_seconds": result.avg_duration_seconds,
            "revision": result.revision,
            "latest_change_at": result.latest_change_at,
            "time_range_start": result.time_range_start,
            "time_range_end": result.time_range_end,
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to build usage history: {str(e)}"}), 500


@presence_hold_analytics_bp.route("/patterns", methods=["GET"])
def get_hold_zone_patterns() -> tuple[Any, int]:
    """
    Get Zone-spezifische Hold-Patterns.
    
    Returns aggregated patterns per zone including:
    - total holds per zone
    - force_on/force_off counts
    - average hold duration
    - most common reason/state
    - holds in last 7/30 days
    
    Response: HoldZonePatternsV1 with revision tracking.
    """
    store = _get_analytics_store()
    
    try:
        result = store.build_zone_patterns()
        patterns_data = []
        for p in result.patterns:
            patterns_data.append({
                "zone_id": p.zone_id,
                "zone_name": p.zone_name,
                "total_holds": p.total_holds,
                "force_on_count": p.force_on_count,
                "force_off_count": p.force_off_count,
                "avg_hold_duration_seconds": p.avg_hold_duration_seconds,
                "most_common_reason": p.most_common_reason,
                "most_common_state": p.most_common_state,
                "last_hold_at": p.last_hold_at,
                "holds_last_7_days": p.holds_last_7_days,
                "holds_last_30_days": p.holds_last_30_days,
            })
        
        return jsonify({
            "patterns": patterns_data,
            "total_zones": result.total_zones,
            "zones_with_holds": result.zones_with_holds,
            "revision": result.revision,
            "latest_change_at": result.latest_change_at,
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to build zone patterns: {str(e)}"}), 500


@presence_hold_analytics_bp.route("/patterns/<zone_id>", methods=["GET"])
def get_hold_zone_pattern_for_zone(zone_id: str) -> tuple[Any, int]:
    """
    Get Hold-Pattern für eine spezifische Zone.
    
    Returns single zone pattern from the full patterns list.
    """
    store = _get_analytics_store()
    
    try:
        result = store.build_zone_patterns()
        for pattern in result.patterns:
            if pattern.zone_id == zone_id:
                return jsonify({
                    "patterns": [{
                        "zone_id": pattern.zone_id,
                        "zone_name": pattern.zone_name,
                        "total_holds": pattern.total_holds,
                        "force_on_count": pattern.force_on_count,
                        "force_off_count": pattern.force_off_count,
                        "avg_hold_duration_seconds": pattern.avg_hold_duration_seconds,
                        "most_common_reason": pattern.most_common_reason,
                        "most_common_state": pattern.most_common_state,
                        "last_hold_at": pattern.last_hold_at,
                        "holds_last_7_days": pattern.holds_last_7_days,
                        "holds_last_30_days": pattern.holds_last_30_days,
                    }],
                    "total_zones": 1,
                    "zones_with_holds": 1 if pattern.total_holds > 0 else 0,
                    "revision": result.revision,
                    "latest_change_at": result.latest_change_at,
                }), 200
        
        return jsonify({"error": f"No patterns found for zone {zone_id}"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to get zone pattern: {str(e)}"}), 500


@presence_hold_analytics_bp.route("/effectiveness", methods=["GET"])
def get_hold_effectiveness_metrics() -> tuple[Any, int]:
    """
    Get Hold-Effectiveness-Metriken.
    
    Returns effectiveness analytics including:
    - conflict rate (holds vs sensor conflicts)
    - flapping prevention rate
    - zones benefiting from holds
    - composite effectiveness score (0.0–1.0)
    
    Response: HoldEffectivenessMetricsV1 with revision tracking.
    """
    store = _get_analytics_store()
    
    try:
        result = store.build_effectiveness_metrics()
        return jsonify({
            "total_holds_analyzed": result.total_holds_analyzed,
            "holds_with_sensor_conflict": result.holds_with_sensor_conflict,
            "conflict_rate": result.conflict_rate,
            "holds_preventing_flapping": result.holds_preventing_flapping,
            "flapping_prevention_rate": result.flapping_prevention_rate,
            "avg_hold_duration_before_stable": result.avg_hold_duration_before_stable,
            "zones_benefiting_from_holds": result.zones_benefiting_from_holds,
            "zones_without_benefit": result.zones_without_benefit,
            "effectiveness_score": result.effectiveness_score,
            "revision": result.revision,
            "latest_change_at": result.latest_change_at,
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to build effectiveness metrics: {str(e)}"}), 500


@presence_hold_analytics_bp.route("/summary", methods=["GET"])
def get_hold_analytics_summary() -> tuple[Any, int]:
    """
    Get vollständige Hold-Analytics-Summary.
    
    Returns combined usage, patterns, and effectiveness metrics
    with a single summary revision for coordinated polling.
    """
    store = _get_analytics_store()
    
    try:
        result = store.build_summary()
        
        # Build usage dict
        usage_data = {
            "entries": [
                {
                    "hold_id": e.hold_id,
                    "zone_id": e.zone_id,
                    "hold_state": e.hold_state,
                    "reason": e.reason,
                    "set_at": e.set_at,
                    "released_at": e.released_at,
                    "duration_seconds": e.duration_seconds,
                    "actual_duration_seconds": e.actual_duration_seconds,
                    "expiration_reason": e.expiration_reason,
                }
                for e in result.usage.entries
            ],
            "total_holds": result.usage.total_holds,
            "total_force_on": result.usage.total_force_on,
            "total_force_off": result.usage.total_force_off,
            "total_auto": result.usage.total_auto,
            "total_expired": result.usage.total_expired,
            "total_manually_released": result.usage.total_manually_released,
            "avg_duration_seconds": result.usage.avg_duration_seconds,
            "revision": result.usage.revision,
            "latest_change_at": result.usage.latest_change_at,
        }
        
        # Build patterns dict
        patterns_data = [
            {
                "zone_id": p.zone_id,
                "zone_name": p.zone_name,
                "total_holds": p.total_holds,
                "force_on_count": p.force_on_count,
                "force_off_count": p.force_off_count,
                "avg_hold_duration_seconds": p.avg_hold_duration_seconds,
                "most_common_reason": p.most_common_reason,
                "most_common_state": p.most_common_state,
                "last_hold_at": p.last_hold_at,
                "holds_last_7_days": p.holds_last_7_days,
                "holds_last_30_days": p.holds_last_30_days,
            }
            for p in result.patterns.patterns
        ]
        
        return jsonify({
            "contract": "HoldAnalyticsSummaryV1",
            "usage": usage_data,
            "patterns": {
                "patterns": patterns_data,
                "total_zones": result.patterns.total_zones,
                "zones_with_holds": result.patterns.zones_with_holds,
                "revision": result.patterns.revision,
                "latest_change_at": result.patterns.latest_change_at,
            },
            "effectiveness": {
                "total_holds_analyzed": result.effectiveness.total_holds_analyzed,
                "holds_with_sensor_conflict": result.effectiveness.holds_with_sensor_conflict,
                "conflict_rate": result.effectiveness.conflict_rate,
                "holds_preventing_flapping": result.effectiveness.holds_preventing_flapping,
                "flapping_prevention_rate": result.effectiveness.flapping_prevention_rate,
                "avg_hold_duration_before_stable": result.effectiveness.avg_hold_duration_before_stable,
                "zones_benefiting_from_holds": result.effectiveness.zones_benefiting_from_holds,
                "zones_without_benefit": result.effectiveness.zones_without_benefit,
                "effectiveness_score": result.effectiveness.effectiveness_score,
                "revision": result.effectiveness.revision,
                "latest_change_at": result.effectiveness.latest_change_at,
            },
            "summary_revision": result.summary_revision,
            "latest_change_at": result.latest_change_at,
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to build analytics summary: {str(e)}"}), 500


@presence_hold_analytics_bp.route("", methods=["GET"])
def get_hold_analytics_index() -> tuple[Any, int]:
    """
    Get Hold Analytics API index.
    
    Lists available analytics endpoints.
    """
    return jsonify({
        "endpoints": {
            "usage": "/presence/holds/analytics/usage",
            "patterns": "/presence/holds/analytics/patterns",
            "patterns_by_zone": "/presence/holds/analytics/patterns/{zone_id}",
            "effectiveness": "/presence/holds/analytics/effectiveness",
            "summary": "/presence/holds/analytics/summary",
        },
        "description": "Hold Analytics provides usage history, zone patterns, and effectiveness metrics for Presence Hold states.",
    }), 200


def create_blueprint() -> Blueprint:
    """Create and return the presence hold analytics blueprint."""
    return presence_hold_analytics_bp
