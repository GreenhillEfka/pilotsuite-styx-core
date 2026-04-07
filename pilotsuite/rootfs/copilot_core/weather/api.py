"""Weather Analytics API — Slice 51."""

from flask import Blueprint, jsonify, request
from typing import Optional

from .analytics_store import get_weather_analytics_store


def create_weather_analytics_blueprint() -> Blueprint:
    """Weather Analytics Blueprint erstellen."""
    bp = Blueprint("weather_analytics", __name__, url_prefix="/api/v1/weather/analytics")

    @bp.route("/usage", methods=["GET"])
    def get_observation_history():
        """Weather-Observation-Historie abrufen."""
        store = get_weather_analytics_store()

        time_range_start = request.args.get("time_range_start")
        time_range_end = request.args.get("time_range_end")
        zone_id = request.args.get("zone_id")
        event_type = request.args.get("event_type")
        limit = int(request.args.get("limit", 100))

        usage = store.build_observation_history(
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
                        "event_type": e.event_type,
                        "source": e.source,
                        "temperature_celsius": e.temperature_celsius,
                        "humidity_percent": e.humidity_percent,
                        "wind_speed_kmh": e.wind_speed_kmh,
                        "precipitation_mm": e.precipitation_mm,
                        "pressure_hpa": e.pressure_hpa,
                        "uv_index": e.uv_index,
                        "air_quality_index": e.air_quality_index,
                        "alert_triggered": e.alert_triggered,
                        "notification_sent": e.notification_sent,
                        "automation_triggered": e.automation_triggered,
                        "observed_at": e.observed_at,
                    }
                    for e in usage.entries
                ],
                "total_observations": usage.total_observations,
                "total_alerts": usage.total_alerts,
                "total_notifications": usage.total_notifications,
                "total_automations": usage.total_automations,
                "avg_temperature_celsius": usage.avg_temperature_celsius,
                "avg_humidity_percent": usage.avg_humidity_percent,
                "revision": usage.revision,
                "latest_change_at": usage.latest_change_at,
                "time_range_start": usage.time_range_start,
                "time_range_end": usage.time_range_end,
            }
        })

    @bp.route("/patterns", methods=["GET"])
    def get_zone_patterns():
        """Zone-spezifische Weather-Patterns abrufen."""
        store = get_weather_analytics_store()

        zone_ids = request.args.getlist("zone_ids")
        zone_ids_param = zone_ids if zone_ids else None

        patterns = store.build_zone_patterns(zone_ids=zone_ids_param)

        return jsonify({
            "patterns": {
                "patterns": [
                    {
                        "zone_id": p.zone_id,
                        "zone_name": p.zone_name,
                        "total_observations": p.total_observations,
                        "temperature_events": p.temperature_events,
                        "precipitation_events": p.precipitation_events,
                        "wind_events": p.wind_events,
                        "alert_events": p.alert_events,
                        "avg_temperature_celsius": p.avg_temperature_celsius,
                        "min_temperature_celsius": p.min_temperature_celsius,
                        "max_temperature_celsius": p.max_temperature_celsius,
                        "avg_humidity_percent": p.avg_humidity_percent,
                        "avg_wind_speed_kmh": p.avg_wind_speed_kmh,
                        "total_precipitation_mm": p.total_precipitation_mm,
                        "observations_last_24_hours": p.observations_last_24_hours,
                        "observations_last_7_days": p.observations_last_7_days,
                        "most_common_event_type": p.most_common_event_type,
                        "most_common_source": p.most_common_source,
                        "peak_alert_hour": p.peak_alert_hour,
                    }
                    for p in patterns.patterns
                ],
                "total_zones": patterns.total_zones,
                "zones_with_weather_data": patterns.zones_with_weather_data,
                "revision": patterns.revision,
                "latest_change_at": patterns.latest_change_at,
            }
        })

    @bp.route("/effectiveness", methods=["GET"])
    def get_effectiveness():
        """Weather-Effectiveness-Metriken abrufen."""
        store = get_weather_analytics_store()
        effectiveness = store.get_effectiveness_metrics()

        return jsonify({
            "effectiveness": {
                "total_observations_analyzed": effectiveness.total_observations_analyzed,
                "observations_by_type": effectiveness.observations_by_type,
                "observations_by_source": effectiveness.observations_by_source,
                "alert_accuracy_rate": effectiveness.alert_accuracy_rate,
                "notification_delivery_rate": effectiveness.notification_delivery_rate,
                "automation_trigger_rate": effectiveness.automation_trigger_rate,
                "avg_observations_per_zone": effectiveness.avg_observations_per_zone,
                "zones_with_regular_data": effectiveness.zones_with_regular_data,
                "zones_with_rare_data": effectiveness.zones_with_rare_data,
                "peak_weather_time": effectiveness.peak_weather_time,
                "forecast_accuracy_score": effectiveness.forecast_accuracy_score,
                "engagement_score": effectiveness.engagement_score,
                "revision": effectiveness.revision,
                "latest_change_at": effectiveness.latest_change_at,
            }
        })

    @bp.route("/summary", methods=["GET"])
    def get_summary():
        """Zusammenfassung aller Weather-Analytics abrufen."""
        store = get_weather_analytics_store()
        summary = store.build_summary()

        return jsonify({
            "summary": {
                "usage": {
                    "total_observations": summary.usage.total_observations,
                    "total_alerts": summary.usage.total_alerts,
                    "total_notifications": summary.usage.total_notifications,
                    "total_automations": summary.usage.total_automations,
                    "avg_temperature_celsius": summary.usage.avg_temperature_celsius,
                    "avg_humidity_percent": summary.usage.avg_humidity_percent,
                    "revision": summary.usage.revision,
                    "latest_change_at": summary.usage.latest_change_at,
                },
                "patterns": {
                    "total_zones": summary.patterns.total_zones,
                    "zones_with_weather_data": summary.patterns.zones_with_weather_data,
                    "revision": summary.patterns.revision,
                    "latest_change_at": summary.patterns.latest_change_at,
                },
                "effectiveness": {
                    "total_observations_analyzed": summary.effectiveness.total_observations_analyzed,
                    "engagement_score": summary.effectiveness.engagement_score,
                    "revision": summary.effectiveness.revision,
                    "latest_change_at": summary.effectiveness.latest_change_at,
                },
                "summary_revision": summary.summary_revision,
                "latest_change_at": summary.latest_change_at,
            }
        })

    return bp
