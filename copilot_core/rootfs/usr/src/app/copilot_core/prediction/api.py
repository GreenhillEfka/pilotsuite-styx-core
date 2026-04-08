"""API v1 -- Prediction endpoints.

Exposes the ArrivalForecaster, EnergyOptimizer, MoodTimeSeriesForecaster,
and LoadShiftingScheduler via REST.

Endpoints:
    GET  /api/v1/predict/arrival/<person_id>           -- predict next arrival
    GET  /api/v1/predict/energy/optimal-window         -- cheapest energy window
    POST /api/v1/predict/energy/schedule               -- set manual price schedule
    POST /api/v1/predict/timeseries/fit/<zone_id>      -- fit Holt-Winters model  (v5.0.0)
    GET  /api/v1/predict/timeseries/forecast/<zone_id> -- forecast mood metrics   (v5.0.0)
    POST /api/v1/predict/energy/load-shift             -- schedule device run     (v5.0.0)
    GET  /api/v1/predict/energy/schedules              -- list load schedules     (v5.0.0)
    DELETE /api/v1/predict/energy/load-shift/<id>      -- cancel schedule         (v5.0.0)
"""
from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

prediction_bp = Blueprint("prediction", __name__, url_prefix="/api/v1/predict")

_forecaster = None
_optimizer = None
_ts_forecaster = None
_load_scheduler = None
_schedule_planner = None
_weather_optimizer = None


def init_prediction_api(
    forecaster=None,
    optimizer=None,
    ts_forecaster=None,
    load_scheduler=None,
    schedule_planner=None,
    weather_optimizer=None,
) -> None:
    """Inject service singletons at startup."""
    global _forecaster, _optimizer, _ts_forecaster, _load_scheduler, _schedule_planner, _weather_optimizer
    _forecaster = forecaster
    _optimizer = optimizer
    _ts_forecaster = ts_forecaster
    _load_scheduler = load_scheduler
    _schedule_planner = schedule_planner
    _weather_optimizer = weather_optimizer
    logger.info("Prediction API initialized")


# -- GET /api/v1/predict/arrival/<person_id> ------------------------------

@prediction_bp.route("/arrival/<person_id>", methods=["GET"])
@require_token
def predict_arrival(person_id: str):
    """Predict the next arrival time for a person."""
    if _forecaster is None:
        return jsonify({"ok": False, "error": "ArrivalForecaster not initialized"}), 503

    horizon = request.args.get("horizon", 120, type=int)

    try:
        result = _forecaster.predict_arrival(person_id, horizon_minutes=horizon)
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        logger.error("Arrival prediction failed for %s: %s", person_id, exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# -- GET /api/v1/predict/energy/optimal-window ----------------------------

@prediction_bp.route("/energy/optimal-window", methods=["GET"])
@require_token
def energy_optimal_window():
    """Find the cheapest energy window."""
    if _optimizer is None:
        return jsonify({"ok": False, "error": "EnergyOptimizer not initialized"}), 503

    duration = request.args.get("duration", 2.0, type=float)
    within = request.args.get("within", 24.0, type=float)

    try:
        result = _optimizer.find_optimal_window(
            duration_hours=duration, within_hours=within
        )
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        logger.error("Optimal window search failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# -- POST /api/v1/predict/energy/schedule ---------------------------------

@prediction_bp.route("/energy/schedule", methods=["POST"])
@require_token
def set_energy_schedule():
    """Manually set the energy price schedule.

    Expected JSON body::

        {
            "prices": [
                {"start": "2025-01-01T00:00:00+00:00",
                 "end":   "2025-01-01T01:00:00+00:00",
                 "price_eur_kwh": 0.25},
                ...
            ]
        }
    """
    if _optimizer is None:
        return jsonify({"ok": False, "error": "EnergyOptimizer not initialized"}), 503

    body = request.get_json(silent=True) or {}
    prices = body.get("prices")
    if not isinstance(prices, list):
        return jsonify({"ok": False, "error": "Missing or invalid 'prices' list"}), 400

    try:
        _optimizer.set_price_schedule(prices)
        return jsonify({"ok": True, "slots": len(prices)}), 200
    except Exception as exc:
        logger.error("Failed to set price schedule: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# v5.0.0 — Time Series Forecasting
# ═══════════════════════════════════════════════════════════════════════════

# -- POST /api/v1/predict/timeseries/fit/<zone_id> -------------------------

@prediction_bp.route("/timeseries/fit/<zone_id>", methods=["POST"])
@require_token
def fit_timeseries(zone_id: str):
    """Fit Holt-Winters model on mood history for a zone."""
    if _ts_forecaster is None:
        return jsonify({"ok": False, "error": "TimeSeriesForecaster not initialized"}), 503

    body = request.get_json(silent=True) or {}
    hours = body.get("hours", 168)

    try:
        result = _ts_forecaster.fit_zone(zone_id, hours=int(hours))
        return jsonify({"ok": True, "zone_id": zone_id, **result}), 200
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error("Timeseries fit failed for %s: %s", zone_id, exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# -- GET /api/v1/predict/timeseries/forecast/<zone_id> ---------------------

@prediction_bp.route("/timeseries/forecast/<zone_id>", methods=["GET"])
@require_token
def forecast_timeseries(zone_id: str):
    """Forecast mood metrics for a zone using fitted Holt-Winters model."""
    if _ts_forecaster is None:
        return jsonify({"ok": False, "error": "TimeSeriesForecaster not initialized"}), 503

    steps = request.args.get("steps", 24, type=int)
    steps = max(1, min(steps, 168))  # Clamp 1–168

    try:
        result = _ts_forecaster.forecast_zone(zone_id, steps=steps)
        return jsonify({"ok": True, **result}), 200
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error("Timeseries forecast failed for %s: %s", zone_id, exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# v5.0.0 — Energy Load Shifting
# ═══════════════════════════════════════════════════════════════════════════

# -- POST /api/v1/predict/energy/load-shift --------------------------------

@prediction_bp.route("/energy/load-shift", methods=["POST"])
@require_token
def schedule_load_shift():
    """Schedule a device run at the optimal price window."""
    if _load_scheduler is None:
        return jsonify({"ok": False, "error": "LoadShiftingScheduler not initialized"}), 503

    body = request.get_json(silent=True) or {}
    device_entity = body.get("device_entity")
    consumption_kwh = body.get("consumption_kwh")
    duration_hours = body.get("duration_hours")

    if not device_entity or consumption_kwh is None or duration_hours is None:
        return jsonify({
            "ok": False,
            "error": "Missing required fields: device_entity, consumption_kwh, duration_hours",
        }), 400

    try:
        result = _load_scheduler.schedule_device(
            device_entity=device_entity,
            consumption_kwh=float(consumption_kwh),
            duration_hours=float(duration_hours),
            priority=body.get("priority", 3),
            within_hours=body.get("within_hours", 24.0),
        )
        return jsonify({"ok": True, **result}), 201
    except Exception as exc:
        logger.error("Load shift scheduling failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# -- GET /api/v1/predict/energy/schedules ----------------------------------

@prediction_bp.route("/energy/schedules", methods=["GET"])
@require_token
def get_load_schedules():
    """Get all load shifting schedules."""
    if _load_scheduler is None:
        return jsonify({"ok": False, "error": "LoadShiftingScheduler not initialized"}), 503

    status_filter = request.args.get("status")

    try:
        schedules = _load_scheduler.get_schedules(status=status_filter)
        return jsonify({"ok": True, "schedules": schedules, "count": len(schedules)}), 200
    except Exception as exc:
        logger.error("Get schedules failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# -- DELETE /api/v1/predict/energy/load-shift/<schedule_id> ----------------

@prediction_bp.route("/energy/load-shift/<schedule_id>", methods=["DELETE"])
@require_token
def cancel_load_shift(schedule_id: str):
    """Cancel a pending load shifting schedule."""
    if _load_scheduler is None:
        return jsonify({"ok": False, "error": "LoadShiftingScheduler not initialized"}), 503

    try:
        result = _load_scheduler.cancel_schedule(schedule_id)
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        logger.error("Cancel schedule failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# v5.5.0 — Smart Schedule Planner
# ═══════════════════════════════════════════════════════════════════════════

# -- GET /api/v1/predict/schedule/daily -----------------------------------

@prediction_bp.route("/schedule/daily", methods=["GET"])
@require_token
def get_daily_schedule():
    """Generate optimal 24h device schedule.

    Query params:
        devices: comma-separated device types (default: all)
    """
    if _schedule_planner is None:
        return jsonify({"ok": False, "error": "SchedulePlanner not initialized"}), 503

    device_param = request.args.get("devices")
    device_list = device_param.split(",") if device_param else None

    # Get price data from optimizer if available
    price_schedule = None
    if _optimizer is not None:
        with _optimizer._lock:
            price_schedule = list(_optimizer._prices) if _optimizer._prices else None

    try:
        plan = _schedule_planner.generate_plan(
            price_schedule=price_schedule,
            device_list=device_list,
        )
        return jsonify({
            "ok": True,
            "date": plan.date,
            "generated_at": plan.generated_at,
            "devices_scheduled": plan.devices_scheduled,
            "unscheduled_devices": plan.unscheduled_devices,
            "total_estimated_cost_eur": plan.total_estimated_cost_eur,
            "total_pv_coverage_percent": plan.total_pv_coverage_percent,
            "peak_load_watts": plan.peak_load_watts,
            "schedules": [
                {
                    "device_type": s.device_type,
                    "start_hour": s.start_hour,
                    "end_hour": s.end_hour,
                    "start": s.start,
                    "end": s.end,
                    "estimated_cost_eur": s.estimated_cost_eur,
                    "pv_coverage_percent": s.pv_coverage_percent,
                    "priority": s.priority,
                }
                for s in plan.device_schedules
            ],
            "hourly_slots": [
                {
                    "hour": s.hour,
                    "pv_factor": round(s.pv_factor, 2),
                    "price_eur_kwh": round(s.price_eur_kwh, 4),
                    "allocated_watts": round(s.allocated_watts, 0),
                    "devices": s.devices,
                    "score": round(s.score, 3),
                }
                for s in plan.slots
            ],
        }), 200
    except Exception as exc:
        logger.error("Daily schedule generation failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# -- GET /api/v1/predict/schedule/next ------------------------------------

@prediction_bp.route("/schedule/next", methods=["GET"])
@require_token
def get_next_scheduled():
    """Get the next scheduled device run from today's plan."""
    if _schedule_planner is None:
        return jsonify({"ok": False, "error": "SchedulePlanner not initialized"}), 503

    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        plan = _schedule_planner.generate_plan()
        upcoming = [
            s for s in plan.device_schedules
            if datetime.fromisoformat(s.start) > now
        ]

        if not upcoming:
            return jsonify({
                "ok": True,
                "next": None,
                "message": "No upcoming scheduled devices today",
            }), 200

        upcoming.sort(key=lambda s: s.start)
        nxt = upcoming[0]

        return jsonify({
            "ok": True,
            "next": {
                "device_type": nxt.device_type,
                "start": nxt.start,
                "end": nxt.end,
                "start_hour": nxt.start_hour,
                "end_hour": nxt.end_hour,
                "estimated_cost_eur": nxt.estimated_cost_eur,
                "pv_coverage_percent": nxt.pv_coverage_percent,
            },
            "remaining_today": len(upcoming),
        }), 200
    except Exception as exc:
        logger.error("Next schedule lookup failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# v5.11.0 — Weather-Aware Energy Optimizer
# ═══════════════════════════════════════════════════════════════════════════

# -- GET /api/v1/predict/weather-optimize ---------------------------------

@prediction_bp.route("/weather-optimize", methods=["GET"])
@require_token
def weather_optimize():
    """Generate 48-hour weather-aware energy optimization plan.

    Query params:
        horizon: hours to plan (default 48, max 72)
    """
    if _weather_optimizer is None:
        return jsonify({"ok": False, "error": "WeatherAwareOptimizer not initialized"}), 503

    horizon = request.args.get("horizon", 48, type=int)
    horizon = max(1, min(horizon, 72))

    try:
        plan = _weather_optimizer.optimize(horizon=horizon)
        return jsonify({
            "ok": True,
            "generated_at": plan.generated_at,
            "base_date": plan.base_date,
            "horizon_hours": plan.horizon_hours,
            "summary": plan.summary,
            "alerts": plan.alerts,
            "top_windows": plan.top_windows,
            "battery_plan_count": len(plan.battery_plan),
            "hourly_count": len(plan.hourly_forecast),
        }), 200
    except Exception as exc:
        logger.error("Weather optimization failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# -- GET /api/v1/predict/weather-optimize/full ----------------------------

@prediction_bp.route("/weather-optimize/full", methods=["GET"])
@require_token
def weather_optimize_full():
    """Full 48-hour plan with all hourly data and battery actions."""
    if _weather_optimizer is None:
        return jsonify({"ok": False, "error": "WeatherAwareOptimizer not initialized"}), 503

    horizon = request.args.get("horizon", 48, type=int)
    horizon = max(1, min(horizon, 72))

    try:
        plan = _weather_optimizer.optimize(horizon=horizon)
        return jsonify({
            "ok": True,
            "generated_at": plan.generated_at,
            "base_date": plan.base_date,
            "horizon_hours": plan.horizon_hours,
            "summary": plan.summary,
            "alerts": plan.alerts,
            "top_windows": plan.top_windows,
            "battery_plan": plan.battery_plan,
            "hourly_forecast": plan.hourly_forecast,
        }), 200
    except Exception as exc:
        logger.error("Full weather optimization failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# -- GET /api/v1/predict/weather-optimize/best-window --------------------

@prediction_bp.route("/weather-optimize/best-window", methods=["GET"])
@require_token
def weather_best_window():
    """Find the best contiguous window considering weather + price.

    Query params:
        duration: hours needed (default 3)
    """
    if _weather_optimizer is None:
        return jsonify({"ok": False, "error": "WeatherAwareOptimizer not initialized"}), 503

    duration = request.args.get("duration", 3, type=int)
    duration = max(1, min(duration, 12))

    try:
        result = _weather_optimizer.get_best_window(duration_hours=duration)
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        logger.error("Weather best-window search failed: %s", exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500
