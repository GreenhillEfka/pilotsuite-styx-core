"""Regional Context API endpoints (v6.3.0)."""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from dataclasses import asdict

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

regional_bp = Blueprint("regional", __name__, url_prefix="/api/v1/regional")

_provider = None
_warning_manager = None
_fuel_tracker = None
_tariff_engine = None
_alert_engine = None
_forecast_engine = None
_battery_optimizer = None
_heat_pump_controller = None
_ev_charging_planner = None
_gas_meter = None


def init_regional_api(
    provider=None,
    warning_manager=None,
    fuel_tracker=None,
    tariff_engine=None,
    alert_engine=None,
    forecast_engine=None,
    battery_optimizer=None,
    heat_pump_controller=None,
    ev_charging_planner=None,
    gas_meter=None,
) -> None:
    """Initialize all regional services."""
    global _provider, _warning_manager, _fuel_tracker, _tariff_engine, _alert_engine, _forecast_engine, _battery_optimizer, _heat_pump_controller, _ev_charging_planner, _gas_meter
    _provider = provider
    _warning_manager = warning_manager
    _fuel_tracker = fuel_tracker
    _tariff_engine = tariff_engine
    _alert_engine = alert_engine
    _forecast_engine = forecast_engine
    _battery_optimizer = battery_optimizer
    _heat_pump_controller = heat_pump_controller
    _ev_charging_planner = ev_charging_planner
    _gas_meter = gas_meter
    logger.info(
        "Regional API initialized (warnings: %s, fuel: %s, tariff: %s, alerts: %s, forecast: %s, battery: %s, heatpump: %s, ev: %s, gas: %s)",
        warning_manager is not None,
        fuel_tracker is not None,
        tariff_engine is not None,
        alert_engine is not None,
        forecast_engine is not None,
        battery_optimizer is not None,
        heat_pump_controller is not None,
        ev_charging_planner is not None,
        gas_meter is not None,
    )


@regional_bp.route("/context", methods=["GET"])
@require_token
def get_context():
    """Get complete regional context (location + solar + defaults)."""
    if not _provider:
        return jsonify({"error": "Regional provider not initialized"}), 503
    ctx = _provider.get_context()
    return jsonify({"ok": True, **asdict(ctx)})


@regional_bp.route("/solar", methods=["GET"])
@require_token
def get_solar():
    """Get current solar position."""
    if not _provider:
        return jsonify({"error": "Regional provider not initialized"}), 503
    solar = _provider.get_solar_position()
    return jsonify({"ok": True, **asdict(solar)})


@regional_bp.route("/solar/factor", methods=["GET"])
@require_token
def get_pv_factor():
    """Get current PV production factor (0-1)."""
    if not _provider:
        return jsonify({"error": "Regional provider not initialized"}), 503
    factor = _provider.get_pv_factor()
    return jsonify({"ok": True, "pv_factor": factor})


@regional_bp.route("/defaults", methods=["GET"])
@require_token
def get_defaults():
    """Get regional defaults (pricing, services, language)."""
    if not _provider:
        return jsonify({"error": "Regional provider not initialized"}), 503
    defaults = _provider.defaults
    return jsonify({"ok": True, **asdict(defaults)})


@regional_bp.route("/day-info", methods=["GET"])
@require_token
def get_day_info():
    """Get day info (sunrise, sunset, pricing, etc.)."""
    if not _provider:
        return jsonify({"error": "Regional provider not initialized"}), 503
    info = _provider.get_day_info()
    return jsonify({"ok": True, **info})


@regional_bp.route("/location", methods=["POST"])
@require_token
def update_location():
    """Update location from HA zone.home.

    JSON body: {latitude, longitude, elevation_m, timezone}
    """
    if not _provider:
        return jsonify({"error": "Regional provider not initialized"}), 503

    body = request.get_json(silent=True) or {}
    lat = body.get("latitude")
    lon = body.get("longitude")
    if lat is None or lon is None:
        return jsonify({"ok": False, "error": "latitude and longitude required"}), 400

    _provider.update_location(
        latitude=float(lat),
        longitude=float(lon),
        elevation_m=float(body.get("elevation_m", 200)),
        timezone=body.get("timezone", "Europe/Berlin"),
    )
    ctx = _provider.get_context()
    return jsonify({"ok": True, "updated": True, **asdict(ctx)})


# ── Weather Warning endpoints (v5.16.0) ──────────────────────────────────


@regional_bp.route("/warnings", methods=["GET"])
@require_token
def get_warnings():
    """Get all active weather warnings with impact assessment."""
    if not _warning_manager:
        return jsonify({"error": "Warning manager not initialized"}), 503
    overview = _warning_manager.get_overview()
    return jsonify({"ok": True, **asdict(overview)})


@regional_bp.route("/warnings/pv", methods=["GET"])
@require_token
def get_pv_warnings():
    """Get warnings that affect PV production."""
    if not _warning_manager:
        return jsonify({"error": "Warning manager not initialized"}), 503
    pv_warnings = _warning_manager.get_pv_warnings()
    return jsonify({"ok": True, "warnings": pv_warnings, "total": len(pv_warnings)})


@regional_bp.route("/warnings/grid", methods=["GET"])
@require_token
def get_grid_warnings():
    """Get warnings that affect grid stability."""
    if not _warning_manager:
        return jsonify({"error": "Warning manager not initialized"}), 503
    grid_warnings = _warning_manager.get_grid_warnings()
    return jsonify({"ok": True, "warnings": grid_warnings, "total": len(grid_warnings)})


@regional_bp.route("/warnings/summary", methods=["GET"])
@require_token
def get_warning_summary():
    """Get human-readable warning summary."""
    if not _warning_manager:
        return jsonify({"error": "Warning manager not initialized"}), 503
    lang = request.args.get("lang", "de")
    summary = _warning_manager.get_summary_text(language=lang)
    return jsonify({
        "ok": True,
        "summary": summary,
        "active_count": _warning_manager.warning_count,
        "language": lang,
    })


@regional_bp.route("/warnings/ingest", methods=["POST"])
@require_token
def ingest_warnings():
    """Ingest weather warnings from DWD or generic format.

    JSON body: {"source": "dwd"|"generic", "data": {...}}
    """
    if not _warning_manager:
        return jsonify({"error": "Warning manager not initialized"}), 503

    body = request.get_json(silent=True) or {}
    source = body.get("source", "generic")
    data = body.get("data", {})

    try:
        if source == "dwd":
            warnings = _warning_manager.process_dwd_warnings(data)
        else:
            warnings_list = data if isinstance(data, list) else data.get("warnings", [])
            warnings = _warning_manager.process_generic_warnings(
                warnings_list, source=source
            )

        logger.info("Ingested %d warnings from %s", len(warnings), source)
        overview = _warning_manager.get_overview()
        return jsonify({"ok": True, "ingested": len(warnings), **asdict(overview)})
    except Exception as exc:
        logger.error("Warning ingestion failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── Fuel Price endpoints (v5.17.0) ───────────────────────────────────────


@regional_bp.route("/fuel/prices", methods=["GET"])
@require_token
def get_fuel_prices():
    """Get current fuel prices summary."""
    if not _fuel_tracker:
        return jsonify({"error": "Fuel tracker not initialized"}), 503
    prices = _fuel_tracker.get_prices()
    if not prices:
        return jsonify({"ok": True, "prices": None, "message": "No price data yet"})
    return jsonify({"ok": True, **asdict(prices)})


@regional_bp.route("/fuel/compare", methods=["GET"])
@require_token
def get_fuel_compare():
    """Get cost-per-100km comparison (Strom vs Diesel vs Benzin vs E10)."""
    if not _fuel_tracker:
        return jsonify({"error": "Fuel tracker not initialized"}), 503
    cost = _fuel_tracker.get_cost_per_100km()
    if not cost:
        return jsonify({"ok": True, "comparison": None, "message": "No price data yet"})
    return jsonify({"ok": True, **asdict(cost)})


@regional_bp.route("/fuel/dashboard", methods=["GET"])
@require_token
def get_fuel_dashboard():
    """Get dashboard-ready fuel data with all comparisons and history."""
    if not _fuel_tracker:
        return jsonify({"error": "Fuel tracker not initialized"}), 503
    dashboard = _fuel_tracker.get_dashboard_data()
    return jsonify({"ok": True, **asdict(dashboard)})


@regional_bp.route("/fuel/stations", methods=["GET"])
@require_token
def get_fuel_stations():
    """Get nearby fuel stations with current prices."""
    if not _fuel_tracker:
        return jsonify({"error": "Fuel tracker not initialized"}), 503
    stations = [s for s in _fuel_tracker._stations if s.is_open]
    return jsonify({
        "ok": True,
        "stations": [asdict(s) for s in sorted(stations, key=lambda x: x.dist)[:20]],
        "total": len(stations),
    })


@regional_bp.route("/fuel/ingest", methods=["POST"])
@require_token
def ingest_fuel_prices():
    """Ingest fuel prices from Tankerkoenig or manual input.

    JSON body: {"source": "tankerkoenig"|"manual", "data": {...}}
    For manual: {"source": "manual", "data": {"diesel": 1.45, "e5": 1.65, "e10": 1.59}}
    """
    if not _fuel_tracker:
        return jsonify({"error": "Fuel tracker not initialized"}), 503

    body = request.get_json(silent=True) or {}
    source = body.get("source", "manual")
    data = body.get("data", {})

    try:
        if source == "tankerkoenig":
            stations = _fuel_tracker.process_tankerkoenig_response(data)
        else:
            stations = _fuel_tracker.process_manual_prices(
                diesel=data.get("diesel"),
                e5=data.get("e5"),
                e10=data.get("e10"),
            )

        logger.info("Ingested fuel prices from %s: %d stations", source, len(stations))
        prices = _fuel_tracker.get_prices()
        return jsonify({
            "ok": True,
            "source": source,
            "station_count": len(stations),
            "prices": asdict(prices) if prices else None,
        })
    except Exception as exc:
        logger.error("Fuel price ingestion failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@regional_bp.route("/fuel/config", methods=["POST"])
@require_token
def configure_fuel():
    """Configure fuel tracker (API key, consumption values).

    JSON body: {
        "api_key": "...",
        "ev_kwh_per_100km": 18.0,
        "diesel_l_per_100km": 6.0,
        "benzin_l_per_100km": 7.5,
        "radius_km": 10.0
    }
    """
    if not _fuel_tracker:
        return jsonify({"error": "Fuel tracker not initialized"}), 503

    body = request.get_json(silent=True) or {}

    if "api_key" in body:
        _fuel_tracker.set_api_key(body["api_key"])
    if "radius_km" in body:
        _fuel_tracker.update_location(
            _fuel_tracker._lat, _fuel_tracker._lon, float(body["radius_km"])
        )
    _fuel_tracker.update_consumption(
        ev_kwh=body.get("ev_kwh_per_100km"),
        diesel_l=body.get("diesel_l_per_100km"),
        benzin_l=body.get("benzin_l_per_100km"),
        e10_l=body.get("e10_l_per_100km"),
    )
    if "grid_price_eur_kwh" in body:
        _fuel_tracker.update_grid_price(float(body["grid_price_eur_kwh"]))

    return jsonify({"ok": True, "configured": True, "has_api_key": _fuel_tracker.has_api_key})


# ── Tariff Engine endpoints (v5.18.0) ────────────────────────────────────


@regional_bp.route("/tariff/summary", methods=["GET"])
@require_token
def get_tariff_summary():
    """Get electricity tariff summary with current price and stats."""
    if not _tariff_engine:
        return jsonify({"error": "Tariff engine not initialized"}), 503
    summary = _tariff_engine.get_summary()
    return jsonify({"ok": True, **asdict(summary)})


@regional_bp.route("/tariff/prices", methods=["GET"])
@require_token
def get_tariff_prices():
    """Get hourly electricity prices."""
    if not _tariff_engine:
        return jsonify({"error": "Tariff engine not initialized"}), 503
    prices = _tariff_engine.get_hourly_prices()
    return jsonify({
        "ok": True,
        "prices": [asdict(p) for p in prices],
        "total": len(prices),
        "tariff_type": _tariff_engine.tariff_type,
    })


@regional_bp.route("/tariff/optimal", methods=["GET"])
@require_token
def get_optimal_window():
    """Find cheapest time window for consumption.

    Query param: ?hours=3 (default 3)
    """
    if not _tariff_engine:
        return jsonify({"error": "Tariff engine not initialized"}), 503
    hours = int(request.args.get("hours", 3))
    window = _tariff_engine.find_optimal_window(duration_hours=hours)
    if not window:
        return jsonify({"ok": True, "window": None, "message": "Not enough data"})
    return jsonify({"ok": True, **asdict(window)})


@regional_bp.route("/tariff/recommendation", methods=["GET"])
@require_token
def get_tariff_recommendation():
    """Get tariff-based energy recommendation."""
    if not _tariff_engine:
        return jsonify({"error": "Tariff engine not initialized"}), 503
    rec = _tariff_engine.get_recommendation()
    return jsonify({"ok": True, **asdict(rec)})


@regional_bp.route("/tariff/ingest", methods=["POST"])
@require_token
def ingest_tariff_prices():
    """Ingest electricity prices from aWATTar or manual input.

    JSON body: {"source": "awattar"|"manual", "data": {...}}
    """
    if not _tariff_engine:
        return jsonify({"error": "Tariff engine not initialized"}), 503

    body = request.get_json(silent=True) or {}
    source = body.get("source", "manual")
    data = body.get("data", {})

    try:
        if source in ("awattar", "awattar_de", "awattar_at"):
            prices = _tariff_engine.process_awattar_response(data)
        else:
            prices_list = data if isinstance(data, list) else data.get("prices", [])
            prices = _tariff_engine.process_manual_prices(prices_list)

        summary = _tariff_engine.get_summary()
        return jsonify({
            "ok": True,
            "source": source,
            "hours_ingested": len(prices),
            **asdict(summary),
        })
    except Exception as exc:
        logger.error("Tariff ingestion failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@regional_bp.route("/tariff/config", methods=["POST"])
@require_token
def configure_tariff():
    """Configure tariff engine.

    JSON body: {
        "country": "DE",
        "tariff_type": "dynamic"|"time_of_use"|"fixed",
        "fixed_rate_eur_kwh": 0.30,
        "feed_in_eur_kwh": 0.082
    }
    """
    if not _tariff_engine:
        return jsonify({"error": "Tariff engine not initialized"}), 503

    body = request.get_json(silent=True) or {}
    _tariff_engine.update_config(
        country=body.get("country"),
        tariff_type=body.get("tariff_type"),
        fixed_rate=body.get("fixed_rate_eur_kwh"),
        feed_in=body.get("feed_in_eur_kwh"),
    )
    return jsonify({"ok": True, "configured": True, "tariff_type": _tariff_engine.tariff_type})


# ── Proactive Alert endpoints (v5.19.0) ──────────────────────────────────


@regional_bp.route("/alerts", methods=["GET"])
@require_token
def get_alerts():
    """Get all active proactive alerts."""
    if not _alert_engine:
        return jsonify({"error": "Alert engine not initialized"}), 503
    summary = _alert_engine.get_summary()
    return jsonify({"ok": True, **asdict(summary)})


@regional_bp.route("/alerts/evaluate", methods=["POST"])
@require_token
def evaluate_alerts():
    """Trigger alert evaluation with current data from all services."""
    if not _alert_engine:
        return jsonify({"error": "Alert engine not initialized"}), 503

    # Gather data from available services
    warning_data = None
    tariff_data = None
    pv_factor = 0.0
    solar_data = None

    if _warning_manager:
        overview = _warning_manager.get_overview()
        warning_data = asdict(overview)

    if _tariff_engine:
        summary = _tariff_engine.get_summary()
        tariff_data = asdict(summary)

    if _provider:
        pv_factor = _provider.get_pv_factor()
        solar = _provider.get_solar_position()
        solar_data = asdict(solar)

    new_alerts = _alert_engine.evaluate_combined(
        warning_overview=warning_data,
        tariff_summary=tariff_data,
        pv_factor=pv_factor,
        solar_data=solar_data,
    )

    summary = _alert_engine.get_summary()
    return jsonify({
        "ok": True,
        "new_alerts": len(new_alerts),
        **asdict(summary),
    })


@regional_bp.route("/alerts/dismiss", methods=["POST"])
@require_token
def dismiss_alert():
    """Dismiss/acknowledge an alert.

    JSON body: {"alert_id": "alert-1"}
    """
    if not _alert_engine:
        return jsonify({"error": "Alert engine not initialized"}), 503

    body = request.get_json(silent=True) or {}
    alert_id = body.get("alert_id", "")

    result = _alert_engine.dismiss_alert(alert_id)
    return jsonify({"ok": True, "dismissed": result, "alert_id": alert_id})


@regional_bp.route("/alerts/config", methods=["POST"])
@require_token
def configure_alerts():
    """Configure alert thresholds.

    JSON body: {
        "price_spike_ct": 35.0,
        "price_low_ct": 20.0,
        "pv_drop_pct": 50.0
    }
    """
    if not _alert_engine:
        return jsonify({"error": "Alert engine not initialized"}), 503

    body = request.get_json(silent=True) or {}
    _alert_engine.configure(
        price_spike_ct=body.get("price_spike_ct"),
        price_low_ct=body.get("price_low_ct"),
        pv_drop_pct=body.get("pv_drop_pct"),
    )
    return jsonify({"ok": True, "configured": True})


# ── Energy Forecast endpoints (v5.20.0) ──────────────────────────────────


@regional_bp.route("/forecast/dashboard", methods=["GET"])
@require_token
def get_forecast_dashboard():
    """Get complete 48h energy forecast dashboard."""
    if not _forecast_engine:
        return jsonify({"error": "Forecast engine not initialized"}), 503
    dashboard = _forecast_engine.generate_dashboard()
    return jsonify({"ok": True, **asdict(dashboard)})


@regional_bp.route("/forecast/hours", methods=["GET"])
@require_token
def get_forecast_hours():
    """Get hourly 48h forecast data."""
    if not _forecast_engine:
        return jsonify({"error": "Forecast engine not initialized"}), 503
    forecast = _forecast_engine.generate_forecast()
    return jsonify({
        "ok": True,
        "hours": [asdict(h) for h in forecast],
        "total": len(forecast),
    })


@regional_bp.route("/forecast/summary", methods=["GET"])
@require_token
def get_forecast_summary():
    """Get 48h forecast summary statistics."""
    if not _forecast_engine:
        return jsonify({"error": "Forecast engine not initialized"}), 503
    summary = _forecast_engine.generate_summary()
    return jsonify({"ok": True, **asdict(summary)})


@regional_bp.route("/forecast/cards", methods=["GET"])
@require_token
def get_forecast_cards():
    """Get dashboard cards for Lovelace integration."""
    if not _forecast_engine:
        return jsonify({"error": "Forecast engine not initialized"}), 503
    cards = _forecast_engine.generate_dashboard_cards()
    return jsonify({
        "ok": True,
        "cards": [asdict(c) for c in cards],
        "total": len(cards),
    })


@regional_bp.route("/forecast/ingest", methods=["POST"])
@require_token
def ingest_forecast_data():
    """Ingest external data for forecast enrichment.

    JSON body: {
        "tariff_prices": [...],  // from tariff engine
        "warning_impacts": [...]  // from warning manager
    }
    """
    if not _forecast_engine:
        return jsonify({"error": "Forecast engine not initialized"}), 503

    body = request.get_json(silent=True) or {}

    try:
        imported = {}
        if "tariff_prices" in body:
            _forecast_engine.import_tariff_data(body["tariff_prices"])
            imported["tariff_hours"] = len(body["tariff_prices"])
        if "warning_impacts" in body:
            _forecast_engine.import_warning_data(body["warning_impacts"])
            imported["warning_impacts"] = len(body["warning_impacts"])

        return jsonify({"ok": True, "imported": imported})
    except Exception as exc:
        logger.error("Forecast data ingestion failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@regional_bp.route("/forecast/config", methods=["POST"])
@require_token
def configure_forecast():
    """Configure forecast engine.

    JSON body: {
        "pv_peak_kw": 10.0,
        "latitude": 52.52,
        "longitude": 13.405,
        "grid_price_ct": 30.0
    }
    """
    if not _forecast_engine:
        return jsonify({"error": "Forecast engine not initialized"}), 503

    body = request.get_json(silent=True) or {}
    if "pv_peak_kw" in body:
        _forecast_engine.set_pv_peak(float(body["pv_peak_kw"]))
    if "latitude" in body and "longitude" in body:
        _forecast_engine.update_location(
            float(body["latitude"]), float(body["longitude"])
        )
    if "grid_price_ct" in body:
        _forecast_engine._default_price = float(body["grid_price_ct"])

    return jsonify({"ok": True, "configured": True})


# ── Battery Optimizer endpoints (v5.23.0) ────────────────────────────────


@regional_bp.route("/battery/schedule", methods=["GET"])
@require_token
def get_battery_schedule():
    """Get optimized battery charge/discharge schedule."""
    if not _battery_optimizer:
        return jsonify({"error": "Battery optimizer not initialized"}), 503
    hours = int(request.args.get("hours", 48))
    schedule = _battery_optimizer.optimize(horizon_hours=hours)
    return jsonify({"ok": True, **asdict(schedule)})


@regional_bp.route("/battery/status", methods=["GET"])
@require_token
def get_battery_status():
    """Get current battery status."""
    if not _battery_optimizer:
        return jsonify({"error": "Battery optimizer not initialized"}), 503
    status = _battery_optimizer.get_status()
    return jsonify({"ok": True, **asdict(status)})


@regional_bp.route("/battery/soc", methods=["POST"])
@require_token
def update_battery_soc():
    """Update battery state of charge.

    JSON body: {"soc_pct": 65.0}
    """
    if not _battery_optimizer:
        return jsonify({"error": "Battery optimizer not initialized"}), 503

    body = request.get_json(silent=True) or {}
    soc = body.get("soc_pct")
    if soc is None:
        return jsonify({"ok": False, "error": "soc_pct required"}), 400

    _battery_optimizer.set_soc(float(soc))
    return jsonify({"ok": True, "soc_pct": _battery_optimizer.config.current_soc_pct})


@regional_bp.route("/battery/config", methods=["POST"])
@require_token
def configure_battery():
    """Configure battery system.

    JSON body: {
        "capacity_kwh": 10.0,
        "max_charge_kw": 5.0,
        "max_discharge_kw": 5.0,
        "min_soc_pct": 10.0,
        "max_soc_pct": 95.0,
        "round_trip_efficiency": 0.92
    }
    """
    if not _battery_optimizer:
        return jsonify({"error": "Battery optimizer not initialized"}), 503

    body = request.get_json(silent=True) or {}
    _battery_optimizer.update_config(**body)
    return jsonify({"ok": True, "configured": True, "config": asdict(_battery_optimizer.config)})


@regional_bp.route("/battery/ingest", methods=["POST"])
@require_token
def ingest_battery_data():
    """Ingest forecast data for battery optimization.

    JSON body: {"forecast_hours": [...]}
    """
    if not _battery_optimizer:
        return jsonify({"error": "Battery optimizer not initialized"}), 503

    body = request.get_json(silent=True) or {}

    try:
        if "forecast_hours" in body:
            _battery_optimizer.import_forecast_data(body["forecast_hours"])
        if "prices" in body:
            _battery_optimizer.set_prices(
                {int(k): float(v) for k, v in body["prices"].items()}
            )
        if "pv_forecast" in body:
            _battery_optimizer.set_pv_forecast(
                {int(k): float(v) for k, v in body["pv_forecast"].items()}
            )
        return jsonify({"ok": True, "ingested": True})
    except Exception as exc:
        logger.error("Battery data ingestion failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── Heat Pump Controller endpoints (v5.24.0) ─────────────────────────────


@regional_bp.route("/heatpump/schedule", methods=["GET"])
@require_token
def get_heatpump_schedule():
    """Get COP-optimized heat pump schedule."""
    if not _heat_pump_controller:
        return jsonify({"error": "Heat pump controller not initialized"}), 503
    hours = int(request.args.get("hours", 48))
    schedule = _heat_pump_controller.optimize(horizon_hours=hours)
    return jsonify({"ok": True, **asdict(schedule)})


@regional_bp.route("/heatpump/status", methods=["GET"])
@require_token
def get_heatpump_status():
    """Get current heat pump status."""
    if not _heat_pump_controller:
        return jsonify({"error": "Heat pump controller not initialized"}), 503
    status = _heat_pump_controller.get_status()
    return jsonify({"ok": True, **asdict(status)})


@regional_bp.route("/heatpump/room-temp", methods=["POST"])
@require_token
def update_room_temp():
    """Update current room temperature.

    JSON body: {"temp_c": 20.5}
    """
    if not _heat_pump_controller:
        return jsonify({"error": "Heat pump controller not initialized"}), 503

    body = request.get_json(silent=True) or {}
    temp = body.get("temp_c")
    if temp is None:
        return jsonify({"ok": False, "error": "temp_c required"}), 400

    _heat_pump_controller.set_room_temp(float(temp))
    return jsonify({"ok": True, "room_temp_c": _heat_pump_controller.config.current_room_temp_c})


@regional_bp.route("/heatpump/hot-water-temp", methods=["POST"])
@require_token
def update_hot_water_temp():
    """Update current hot water temperature.

    JSON body: {"temp_c": 48.0}
    """
    if not _heat_pump_controller:
        return jsonify({"error": "Heat pump controller not initialized"}), 503

    body = request.get_json(silent=True) or {}
    temp = body.get("temp_c")
    if temp is None:
        return jsonify({"ok": False, "error": "temp_c required"}), 400

    _heat_pump_controller.set_hot_water_temp(float(temp))
    return jsonify({"ok": True, "hot_water_temp_c": _heat_pump_controller.config.current_hot_water_temp_c})


@regional_bp.route("/heatpump/config", methods=["POST"])
@require_token
def configure_heatpump():
    """Configure heat pump system.

    JSON body: {
        "pump_type": "air_water"|"ground_water"|"air_air",
        "nominal_power_kw": 8.0,
        "max_flow_temp_c": 55.0,
        "target_room_temp_c": 21.0,
        "building_thermal_mass_kwh_per_k": 2.5,
        "hot_water_tank_l": 300.0,
        "hot_water_target_c": 55.0
    }
    """
    if not _heat_pump_controller:
        return jsonify({"error": "Heat pump controller not initialized"}), 503

    body = request.get_json(silent=True) or {}
    _heat_pump_controller.update_config(**body)
    return jsonify({"ok": True, "configured": True, "config": asdict(_heat_pump_controller.config)})


@regional_bp.route("/heatpump/strategy", methods=["POST"])
@require_token
def set_heatpump_strategy():
    """Set heat pump scheduling strategy.

    JSON body: {"strategy": "cop_optimized"|"price_optimized"|"comfort_first"|"solar_boost"}
    """
    if not _heat_pump_controller:
        return jsonify({"error": "Heat pump controller not initialized"}), 503

    body = request.get_json(silent=True) or {}
    strategy = body.get("strategy", "")
    if strategy not in _heat_pump_controller.STRATEGIES:
        return jsonify({
            "ok": False,
            "error": f"Invalid strategy. Choose from: {', '.join(_heat_pump_controller.STRATEGIES)}",
        }), 400

    _heat_pump_controller.set_strategy(strategy)
    return jsonify({"ok": True, "strategy": strategy})


@regional_bp.route("/heatpump/ingest", methods=["POST"])
@require_token
def ingest_heatpump_data():
    """Ingest weather/tariff/PV data for heat pump optimization.

    JSON body: {
        "weather": [{"hour": 0, "temperature_c": -2.0}, ...],
        "tariff": [{"hour": 0, "price_ct": 25.0}, ...],
        "pv_forecast": {"10": 3.0, "11": 5.0, ...}
    }
    """
    if not _heat_pump_controller:
        return jsonify({"error": "Heat pump controller not initialized"}), 503

    body = request.get_json(silent=True) or {}

    try:
        imported = {}
        if "weather" in body:
            _heat_pump_controller.import_weather_data(body["weather"])
            imported["weather_hours"] = len(body["weather"])
        if "tariff" in body:
            _heat_pump_controller.import_tariff_data(body["tariff"])
            imported["tariff_hours"] = len(body["tariff"])
        if "pv_forecast" in body:
            _heat_pump_controller.set_pv_forecast(
                {int(k): float(v) for k, v in body["pv_forecast"].items()}
            )
            imported["pv_hours"] = len(body["pv_forecast"])
        return jsonify({"ok": True, "imported": imported})
    except Exception as exc:
        logger.error("Heat pump data ingestion failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── EV Charging Planner endpoints (v5.25.0) ──────────────────────────────


@regional_bp.route("/ev/schedule", methods=["GET"])
@require_token
def get_ev_schedule():
    """Get optimized EV charging schedule."""
    if not _ev_charging_planner:
        return jsonify({"error": "EV charging planner not initialized"}), 503
    hours = int(request.args.get("hours", 48))
    schedule = _ev_charging_planner.optimize(horizon_hours=hours)
    return jsonify({"ok": True, **asdict(schedule)})


@regional_bp.route("/ev/status", methods=["GET"])
@require_token
def get_ev_status():
    """Get current EV charging status."""
    if not _ev_charging_planner:
        return jsonify({"error": "EV charging planner not initialized"}), 503
    status = _ev_charging_planner.get_status()
    return jsonify({"ok": True, **asdict(status)})


@regional_bp.route("/ev/soc", methods=["POST"])
@require_token
def update_ev_soc():
    """Update EV state of charge.

    JSON body: {"soc_pct": 45.0}
    """
    if not _ev_charging_planner:
        return jsonify({"error": "EV charging planner not initialized"}), 503

    body = request.get_json(silent=True) or {}
    soc = body.get("soc_pct")
    if soc is None:
        return jsonify({"ok": False, "error": "soc_pct required"}), 400

    _ev_charging_planner.set_soc(float(soc))
    return jsonify({"ok": True, "soc_pct": _ev_charging_planner.config.current_soc_pct})


@regional_bp.route("/ev/departure", methods=["POST"])
@require_token
def set_ev_departure():
    """Set departure schedule.

    JSON body: {
        "departure_time": "2026-02-22T07:30:00+01:00",
        "departure_soc_pct": 80.0,
        "recurrence": "weekdays"
    }
    """
    if not _ev_charging_planner:
        return jsonify({"error": "EV charging planner not initialized"}), 503

    body = request.get_json(silent=True) or {}
    dep_time = body.get("departure_time", "")
    dep_soc = float(body.get("departure_soc_pct", 80.0))
    recurrence = body.get("recurrence", "none")

    _ev_charging_planner.set_departure(dep_time, dep_soc, recurrence)
    return jsonify({"ok": True, "departure_time": dep_time, "departure_soc_pct": dep_soc})


@regional_bp.route("/ev/config", methods=["POST"])
@require_token
def configure_ev():
    """Configure EV and charger.

    JSON body: {
        "battery_capacity_kwh": 60.0,
        "max_charge_rate_kw": 11.0,
        "charger_efficiency": 0.92,
        "connector_type": "type2",
        "vehicle_name": "VW ID.4",
        "target_soc_pct": 80.0
    }
    """
    if not _ev_charging_planner:
        return jsonify({"error": "EV charging planner not initialized"}), 503

    body = request.get_json(silent=True) or {}
    _ev_charging_planner.update_config(**body)
    return jsonify({"ok": True, "configured": True, "config": asdict(_ev_charging_planner.config)})


@regional_bp.route("/ev/strategy", methods=["POST"])
@require_token
def set_ev_strategy():
    """Set EV charging strategy.

    JSON body: {"strategy": "cost_optimized"|"solar_first"|"fastest"|"balanced"}
    """
    if not _ev_charging_planner:
        return jsonify({"error": "EV charging planner not initialized"}), 503

    body = request.get_json(silent=True) or {}
    strategy = body.get("strategy", "")
    if strategy not in _ev_charging_planner.STRATEGIES:
        return jsonify({
            "ok": False,
            "error": f"Invalid strategy. Choose from: {', '.join(_ev_charging_planner.STRATEGIES)}",
        }), 400

    _ev_charging_planner.set_strategy(strategy)
    return jsonify({"ok": True, "strategy": strategy})


@regional_bp.route("/ev/ingest", methods=["POST"])
@require_token
def ingest_ev_data():
    """Ingest tariff/PV data for EV charging optimization.

    JSON body: {
        "tariff": [{"hour": 0, "price_ct": 25.0}, ...],
        "pv_forecast": {"10": 3.0, "11": 5.0, ...}
    }
    """
    if not _ev_charging_planner:
        return jsonify({"error": "EV charging planner not initialized"}), 503

    body = request.get_json(silent=True) or {}

    try:
        imported = {}
        if "tariff" in body:
            _ev_charging_planner.import_tariff_data(body["tariff"])
            imported["tariff_hours"] = len(body["tariff"])
        if "pv_forecast" in body:
            _ev_charging_planner.set_pv_forecast(
                {int(k): float(v) for k, v in body["pv_forecast"].items()}
            )
            imported["pv_hours"] = len(body["pv_forecast"])
        if "prices" in body:
            _ev_charging_planner.set_prices(
                {int(k): float(v) for k, v in body["prices"].items()}
            )
            imported["price_hours"] = len(body["prices"])
        return jsonify({"ok": True, "imported": imported})
    except Exception as exc:
        logger.error("EV data ingestion failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── Gas Meter endpoints (v6.3.0) ───────────────────────────────────────────


@regional_bp.route("/gas", methods=["GET"])
@require_token
def get_gas_dashboard():
    """Get complete gas meter dashboard."""
    if not _gas_meter:
        return jsonify({"error": "Gas meter not initialized"}), 503
    dashboard = _gas_meter.get_dashboard()
    return jsonify({"ok": True, **asdict(dashboard)})


@regional_bp.route("/gas/impulse", methods=["POST"])
@require_token
def record_gas_impulse():
    """Record gas impulse(s).

    JSON body (optional): {"count": 1}
    """
    if not _gas_meter:
        return jsonify({"error": "Gas meter not initialized"}), 503
    body = request.get_json(silent=True) or {}
    count = int(body.get("count", 1))
    if count == 1:
        meter = _gas_meter.record_impulse()
    else:
        meter = _gas_meter.record_impulses(count)
    return jsonify({"ok": True, "meter_m3": round(meter, 3), "impulses": count})


@regional_bp.route("/gas/reading", methods=["POST"])
@require_token
def record_gas_reading():
    """Record direct meter reading.

    JSON body: {"meter_m3": 1234.56}
    """
    if not _gas_meter:
        return jsonify({"error": "Gas meter not initialized"}), 503
    body = request.get_json(silent=True) or {}
    meter_m3 = float(body.get("meter_m3", 0))
    delta = _gas_meter.record_meter_reading(meter_m3)
    return jsonify({"ok": True, "meter_m3": meter_m3, "delta_m3": round(delta, 3)})


@regional_bp.route("/gas/stats/<period>", methods=["GET"])
@require_token
def get_gas_stats(period):
    """Get gas statistics for a period (today/yesterday/week/month/year)."""
    if not _gas_meter:
        return jsonify({"error": "Gas meter not initialized"}), 503
    stats = _gas_meter.get_period_stats(period)
    return jsonify({"ok": True, **asdict(stats)})


@regional_bp.route("/gas/forecast/<period>", methods=["GET"])
@require_token
def get_gas_forecast(period):
    """Get gas consumption forecast (month/year)."""
    if not _gas_meter:
        return jsonify({"error": "Gas meter not initialized"}), 503
    forecast = _gas_meter.get_forecast(period)
    return jsonify({"ok": True, **asdict(forecast)})


@regional_bp.route("/gas/config", methods=["POST"])
@require_token
def configure_gas_meter():
    """Update gas meter configuration.

    JSON body: {"gas_price_ct_kwh": 9.5, "impulse_factor_m3": 0.01, "region": "sued", ...}
    """
    if not _gas_meter:
        return jsonify({"error": "Gas meter not initialized"}), 503
    body = request.get_json(silent=True) or {}
    config = _gas_meter.update_config(**body)
    return jsonify({"ok": True, "config": asdict(config)})


@regional_bp.route("/gas/initial", methods=["POST"])
@require_token
def set_gas_initial_reading():
    """Set initial meter reading.

    JSON body: {"meter_m3": 12345.67}
    """
    if not _gas_meter:
        return jsonify({"error": "Gas meter not initialized"}), 503
    body = request.get_json(silent=True) or {}
    meter_m3 = float(body.get("meter_m3", 0))
    _gas_meter.set_initial_reading(meter_m3)
    return jsonify({"ok": True, "initial_meter_m3": meter_m3})
