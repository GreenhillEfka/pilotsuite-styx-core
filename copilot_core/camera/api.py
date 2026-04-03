"""Camera Analytics API — Slice 50."""

from flask import Blueprint, jsonify, request
from typing import Optional

from .analytics_store import get_camera_analytics_store


def create_camera_analytics_blueprint() -> Blueprint:
    """Camera Analytics Blueprint erstellen."""
    bp = Blueprint("camera_analytics", __name__, url_prefix="/api/v1/camera/analytics")

    @bp.route("/usage", methods=["GET"])
    def get_usage_history():
        """Camera-Usage-Historie abrufen."""
        store = get_camera_analytics_store()

        time_range_start = request.args.get("time_range_start")
        time_range_end = request.args.get("time_range_end")
        zone_id = request.args.get("zone_id")
        event_type = request.args.get("event_type")
        limit = int(request.args.get("limit", 100))

        usage = store.build_usage_history(
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            zone_id=zone_id,
            event_type=event_type,
            limit=limit,
        )

        return jsonify({
            "usage": {
                "entries": [
                    {
                        "entry_id": e.entry_id,
                        "zone_id": e.zone_id,
                        "zone_name": e.zone_name,
                        "camera_id": e.camera_id,
                        "camera_name": e.camera_name,
                        "event_type": e.event_type,
                        "source": e.source,
                        "snapshot_taken": e.snapshot_taken,
                        "recording_started": e.recording_started,
                        "recording_duration_seconds": e.recording_duration_seconds,
                        "thumbnail_generated": e.thumbnail_generated,
                        "notification_sent": e.notification_sent,
                        "processed_at": e.processed_at,
                    }
                    for e in usage.entries
                ],
                "total_events": usage.total_events,
                "total_snapshots": usage.total_snapshots,
                "total_recordings": usage.total_recordings,
                "total_recording_duration_seconds": usage.total_recording_duration_seconds,
                "avg_recording_duration_seconds": usage.avg_recording_duration_seconds,
                "revision": usage.revision,
                "latest_change_at": usage.latest_change_at,
                "time_range_start": usage.time_range_start,
                "time_range_end": usage.time_range_end,
            }
        })

    @bp.route("/patterns", methods=["GET"])
    def get_zone_patterns():
        """Zone-spezifische Camera-Patterns abrufen."""
        store = get_camera_analytics_store()

        zone_ids = request.args.getlist("zone_ids")
        zone_ids_param = zone_ids if zone_ids else None

        patterns = store.build_zone_patterns(zone_ids=zone_ids_param)

        return jsonify({
            "patterns": {
                "patterns": [
                    {
                        "zone_id": p.zone_id,
                        "zone_name": p.zone_name,
                        "total_events": p.total_events,
                        "motion_events": p.motion_events,
                        "person_events": p.person_events,
                        "vehicle_events": p.vehicle_events,
                        "sound_events": p.sound_events,
                        "doorbell_events": p.doorbell_events,
                        "snapshots_taken": p.snapshots_taken,
                        "recordings_started": p.recordings_started,
                        "avg_recording_duration_seconds": p.avg_recording_duration_seconds,
                        "peak_activity_hour": p.peak_activity_hour,
                        "events_last_24_hours": p.events_last_24_hours,
                        "events_last_7_days": p.events_last_7_days,
                        "most_common_event_type": p.most_common_event_type,
                        "most_common_source": p.most_common_source,
                    }
                    for p in patterns.patterns
                ],
                "total_zones": patterns.total_zones,
                "zones_with_camera_activity": patterns.zones_with_camera_activity,
                "revision": patterns.revision,
                "latest_change_at": patterns.latest_change_at,
            }
        })

    @bp.route("/effectiveness", methods=["GET"])
    def get_effectiveness():
        """Camera-Effectiveness-Metriken abrufen."""
        store = get_camera_analytics_store()
        effectiveness = store.get_effectiveness_metrics()

        return jsonify({
            "effectiveness": {
                "total_events_analyzed": effectiveness.total_events_analyzed,
                "events_by_type": effectiveness.events_by_type,
                "events_by_source": effectiveness.events_by_source,
                "motion_to_person_ratio": effectiveness.motion_to_person_ratio,
                "false_positive_rate": effectiveness.false_positive_rate,
                "notification_delivery_rate": effectiveness.notification_delivery_rate,
                "snapshot_capture_rate": effectiveness.snapshot_capture_rate,
                "recording_trigger_rate": effectiveness.recording_trigger_rate,
                "avg_events_per_zone": effectiveness.avg_events_per_zone,
                "zones_with_regular_activity": effectiveness.zones_with_regular_activity,
                "zones_with_rare_activity": effectiveness.zones_with_rare_activity,
                "peak_activity_time": effectiveness.peak_activity_time,
                "engagement_score": effectiveness.engagement_score,
                "revision": effectiveness.revision,
                "latest_change_at": effectiveness.latest_change_at,
            }
        })

    @bp.route("/summary", methods=["GET"])
    def get_summary():
        """Zusammenfassung aller Camera-Analytics abrufen."""
        store = get_camera_analytics_store()
        summary = store.build_summary()

        return jsonify({
            "summary": {
                "usage": {
                    "total_events": summary.usage.total_events,
                    "total_snapshots": summary.usage.total_snapshots,
                    "total_recordings": summary.usage.total_recordings,
                    "total_recording_duration_seconds": summary.usage.total_recording_duration_seconds,
                    "avg_recording_duration_seconds": summary.usage.avg_recording_duration_seconds,
                    "revision": summary.usage.revision,
                    "latest_change_at": summary.usage.latest_change_at,
                },
                "patterns": {
                    "total_zones": summary.patterns.total_zones,
                    "zones_with_camera_activity": summary.patterns.zones_with_camera_activity,
                    "revision": summary.patterns.revision,
                    "latest_change_at": summary.patterns.latest_change_at,
                },
                "effectiveness": {
                    "total_events_analyzed": summary.effectiveness.total_events_analyzed,
                    "engagement_score": summary.effectiveness.engagement_score,
                    "revision": summary.effectiveness.revision,
                    "latest_change_at": summary.effectiveness.latest_change_at,
                },
                "summary_revision": summary.summary_revision,
                "latest_change_at": summary.latest_change_at,
            }
        })

    return bp
