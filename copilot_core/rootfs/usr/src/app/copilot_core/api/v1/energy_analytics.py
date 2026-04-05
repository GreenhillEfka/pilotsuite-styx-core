"""Energy Analytics API — Slice 47."""
from flask import Blueprint, jsonify, request

from .analytics import EnergyAnalyticsPeriod
from .analytics_store import EnergyAnalyticsStore

analytics_bp = Blueprint("energy_analytics", __name__, url_prefix="/api/v1/energy/analytics")

_store: EnergyAnalyticsStore | None = None


def get_store() -> EnergyAnalyticsStore:
    """Get or create analytics store singleton."""
    global _store
    if _store is None:
        _store = EnergyAnalyticsStore()
    return _store


@analytics_bp.route("/usage", methods=["GET"])
def get_usage_history():
    """Get energy usage history."""
    store = get_store()
    
    # Parse query params
    period_str = request.args.get("period", "daily")
    zone_id = request.args.get("zone_id")
    since_revision = request.args.get("since_revision", type=int)
    
    try:
        period = EnergyAnalyticsPeriod(period_str)
    except ValueError:
        period = EnergyAnalyticsPeriod.DAILY
    
    history = store.build_usage_history(
        period=period,
        zone_id=zone_id,
        since_revision=since_revision,
    )
    
    return jsonify({
        "period": history.period.value,
        "start_at": history.start_at,
        "end_at": history.end_at,
        "total_consumption_wh": history.total_consumption_wh,
        "total_cost_eur": history.total_cost_eur,
        "revision": history.revision,
        "latest_change_at": history.latest_change_at,
        "has_changes": since_revision is None or history.revision > since_revision,
        "entries": [
            {
                "timestamp": e.timestamp,
                "zone_id": e.zone_id,
                "module_id": e.module_id,
                "entity_id": e.entity_id,
                "consumption_wh": e.consumption_wh,
                "cost_eur": e.cost_eur,
                "tariff_rate": e.tariff_rate,
                "source": e.source,
            }
            for e in history.entries
        ],
    })


@analytics_bp.route("/patterns", methods=["GET"])
def get_zone_patterns():
    """Get zone energy patterns."""
    store = get_store()
    
    zone_id = request.args.get("zone_id")
    since_revision = request.args.get("since_revision", type=int)
    
    patterns = store.build_zone_patterns(zone_id=zone_id, since_revision=since_revision)
    
    return jsonify({
        "revision": patterns.revision,
        "latest_change_at": patterns.latest_change_at,
        "has_changes": since_revision is None or patterns.revision > since_revision,
        "patterns": [
            {
                "zone_id": p.zone_id,
                "zone_name": p.zone_name,
                "avg_daily_consumption_wh": p.avg_daily_consumption_wh,
                "peak_hour": p.peak_hour,
                "peak_consumption_wh": p.peak_consumption_wh,
                "off_peak_consumption_wh": p.off_peak_consumption_wh,
                "weekday_pattern": p.weekday_pattern,
                "weekend_pattern": p.weekend_pattern,
                "dominant_modules": p.dominant_modules,
                "trend_7d": p.trend_7d,
                "trend_30d": p.trend_30d,
            }
            for p in patterns.patterns
        ],
    })


@analytics_bp.route("/effectiveness", methods=["GET"])
def get_effectiveness():
    """Get energy optimization effectiveness metrics."""
    store = get_store()
    metrics = store.get_effectiveness_metrics()
    
    return jsonify({
        "total_savings_eur": metrics.total_savings_eur,
        "total_savings_wh": metrics.total_savings_wh,
        "optimization_success_rate": metrics.optimization_success_rate,
        "avg_shift_duration_minutes": metrics.avg_shift_duration_minutes,
        "peak_reduction_percentage": metrics.peak_reduction_percentage,
        "pv_self_consumption_rate": metrics.pv_self_consumption_rate,
        "battery_efficiency": metrics.battery_efficiency,
        "suggestions_accepted": metrics.suggestions_accepted,
        "suggestions_rejected": metrics.suggestions_rejected,
        "suggestions_pending": metrics.suggestions_pending,
        "load_shifts_executed": metrics.load_shifts_executed,
        "revision": metrics.revision,
        "latest_change_at": metrics.latest_change_at,
    })


@analytics_bp.route("/summary", methods=["GET"])
def get_summary():
    """Get energy analytics summary."""
    store = get_store()
    summary = store.get_summary()
    
    return jsonify({
        "period": summary.period.value,
        "start_at": summary.start_at,
        "end_at": summary.end_at,
        "total_consumption_wh": summary.total_consumption_wh,
        "total_cost_eur": summary.total_cost_eur,
        "avg_daily_consumption_wh": summary.avg_daily_consumption_wh,
        "peak_consumption_wh": summary.peak_consumption_wh,
        "peak_hour": summary.peak_hour,
        "zone_count": summary.zone_count,
        "module_count": summary.module_count,
        "entity_count": summary.entity_count,
        "pv_generation_wh": summary.pv_generation_wh,
        "battery_cycles": summary.battery_cycles,
        "grid_import_wh": summary.grid_import_wh,
        "grid_export_wh": summary.grid_export_wh,
        "revision": summary.revision,
        "latest_change_at": summary.latest_change_at,
    })


@analytics_bp.route("/usage", methods=["POST"])
def add_usage_entry():
    """Add energy usage entry (for testing/integration)."""
    store = get_store()
    data = request.get_json()
    
    from .analytics import EnergyUsageEntryV1
    
    entry = EnergyUsageEntryV1(
        timestamp=data["timestamp"],
        zone_id=data["zone_id"],
        module_id=data["module_id"],
        entity_id=data["entity_id"],
        consumption_wh=data["consumption_wh"],
        cost_eur=data["cost_eur"],
        tariff_rate=data["tariff_rate"],
        source=data["source"],
    )
    
    store.add_usage_entry(entry)
    
    return jsonify({"status": "ok", "message": "Entry added"}), 201


@analytics_bp.route("/patterns", methods=["POST"])
def update_pattern():
    """Update zone energy pattern (for testing/integration)."""
    store = get_store()
    data = request.get_json()
    
    from .analytics import ZoneEnergyPatternV1
    
    pattern = ZoneEnergyPatternV1(
        zone_id=data["zone_id"],
        zone_name=data["zone_name"],
        avg_daily_consumption_wh=data["avg_daily_consumption_wh"],
        peak_hour=data["peak_hour"],
        peak_consumption_wh=data["peak_consumption_wh"],
        off_peak_consumption_wh=data["off_peak_consumption_wh"],
        weekday_pattern=data.get("weekday_pattern", []),
        weekend_pattern=data.get("weekend_pattern", []),
        dominant_modules=data.get("dominant_modules", []),
        trend_7d=data.get("trend_7d", 0.0),
        trend_30d=data.get("trend_30d", 0.0),
    )
    
    store.update_zone_pattern(pattern)
    
    return jsonify({"status": "ok", "message": "Pattern updated"}), 200


@analytics_bp.route("/effectiveness", methods=["PUT"])
def update_effectiveness():
    """Update effectiveness metrics (for testing/integration)."""
    store = get_store()
    data = request.get_json()
    
    from .analytics import EnergyEffectivenessMetricsV1
    
    metrics = EnergyEffectivenessMetricsV1(
        total_savings_eur=data.get("total_savings_eur", 0.0),
        total_savings_wh=data.get("total_savings_wh", 0.0),
        optimization_success_rate=data.get("optimization_success_rate", 0.0),
        avg_shift_duration_minutes=data.get("avg_shift_duration_minutes", 0.0),
        peak_reduction_percentage=data.get("peak_reduction_percentage", 0.0),
        pv_self_consumption_rate=data.get("pv_self_consumption_rate", 0.0),
        battery_efficiency=data.get("battery_efficiency", 0.0),
        suggestions_accepted=data.get("suggestions_accepted", 0),
        suggestions_rejected=data.get("suggestions_rejected", 0),
        suggestions_pending=data.get("suggestions_pending", 0),
        load_shifts_executed=data.get("load_shifts_executed", 0),
    )
    
    store.update_effectiveness_metrics(metrics)
    
    return jsonify({"status": "ok", "message": "Metrics updated"}), 200
