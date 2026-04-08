"""Energy Neuron API endpoints."""

from flask import Blueprint, Response, jsonify, request

from .sankey import SankeyRenderer, build_sankey_from_energy
from .service import EnergyService
from ..api.security import require_api_key

energy_bp = Blueprint("energy", __name__)

# Global service instance (initialized in core_setup.py)
_energy_service: EnergyService = None


def init_energy_api(service: EnergyService):
    """Initialize energy service with global instance (consistent with other modules)."""
    global _energy_service
    _energy_service = service


def get_energy_service() -> EnergyService:
    """Get the energy service instance."""
    return _energy_service


@energy_bp.route("/api/v1/energy", methods=["GET"])
@require_api_key
def get_energy():
    """Get complete energy snapshot."""
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503
    
    snapshot = _energy_service.get_energy_snapshot()
    return jsonify({
        "timestamp": snapshot.timestamp,
        "total_consumption_today_kwh": snapshot.total_consumption_today,
        "total_production_today_kwh": snapshot.total_production_today,
        "current_power_watts": snapshot.current_power,
        "peak_power_today_watts": snapshot.peak_power_today,
        "anomalies_detected": snapshot.anomalies_detected,
        "shifting_opportunities": snapshot.shifting_opportunities,
        "baselines": snapshot.baselines
    })


@energy_bp.route("/api/v1/energy/anomalies", methods=["GET"])
@require_api_key
def get_anomalies():
    """Get detected energy anomalies."""
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503
    
    anomalies = _energy_service.detect_anomalies()
    return jsonify({
        "timestamp": _energy_service._get_timestamp(),
        "count": len(anomalies),
        "anomalies": [
            {
                "id": a.id,
                "timestamp": a.timestamp,
                "device_id": a.device_id,
                "device_type": a.device_type,
                "expected_value": a.expected_value,
                "actual_value": a.actual_value,
                "deviation_percent": a.deviation_percent,
                "severity": a.severity,
                "description": a.description
            }
            for a in anomalies
        ]
    })


@energy_bp.route("/api/v1/energy/shifting", methods=["GET"])
@require_api_key
def get_shifting():
    """Get load shifting opportunities."""
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503
    
    opportunities = _energy_service.detect_shifting_opportunities()
    return jsonify({
        "timestamp": _energy_service._get_timestamp(),
        "count": len(opportunities),
        "opportunities": [
            {
                "id": o.id,
                "timestamp": o.timestamp,
                "device_type": o.device_type,
                "reason": o.reason,
                "current_cost_eur": o.current_cost,
                "optimal_cost_eur": o.optimal_cost,
                "savings_estimate_eur": o.savings_estimate,
                "suggested_window_start": o.suggested_time_window[0],
                "suggested_window_end": o.suggested_time_window[1],
                "confidence": o.confidence
            }
            for o in opportunities
        ]
    })


@energy_bp.route("/api/v1/energy/explain/<suggestion_id>", methods=["GET"])
@require_api_key
def explain_suggestion(suggestion_id: str):
    """Get explanation for an energy suggestion."""
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503
    
    explanation = _energy_service.explain_suggestion(suggestion_id)
    return jsonify(explanation)


@energy_bp.route("/api/v1/energy/baselines", methods=["GET"])
@require_api_key
def get_baselines():
    """Get energy consumption baselines."""
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503
    
    return jsonify({
        "timestamp": _energy_service._get_timestamp(),
        "baselines": _energy_service._get_baselines()
    })


@energy_bp.route("/api/v1/energy/suppress", methods=["GET"])
@require_api_key
def get_suppress():
    """Check if energy suggestions should be suppressed."""
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503
    
    status = _energy_service.get_suppression_status()
    return jsonify(status)


@energy_bp.route("/api/v1/energy/health", methods=["GET"])
@require_api_key
def get_health():
    """Get energy service health status."""
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503
    
    return jsonify(_energy_service.get_health())


# ═══════════════════════════════════════════════════════════════════════════
# v5.1.0 — Zone Energy API
# ═══════════════════════════════════════════════════════════════════════════

@energy_bp.route("/api/v1/energy/zone/<zone_id>", methods=["POST"])
@require_api_key
def register_zone_energy(zone_id: str):
    """Register energy entities for a zone.

    Body: {"entity_ids": ["sensor.kitchen_power", ...], "zone_name": "Kitchen"}
    """
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503

    body = request.get_json(silent=True) or {}
    entity_ids = body.get("entity_ids", [])
    zone_name = body.get("zone_name", zone_id)

    if not isinstance(entity_ids, list):
        return jsonify({"ok": False, "error": "entity_ids must be a list"}), 400

    # Store zone energy mapping
    if not hasattr(_energy_service, "_zone_energy_map"):
        _energy_service._zone_energy_map = {}

    _energy_service._zone_energy_map[zone_id] = {
        "zone_name": zone_name,
        "entity_ids": entity_ids,
        "registered_at": _energy_service._get_timestamp(),
    }

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "entity_count": len(entity_ids),
    }), 201


@energy_bp.route("/api/v1/energy/zone/<zone_id>", methods=["GET"])
@require_api_key
def get_zone_energy(zone_id: str):
    """Get energy data for a specific zone."""
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503

    zone_map = getattr(_energy_service, "_zone_energy_map", {})
    zone_config = zone_map.get(zone_id)

    if not zone_config:
        return jsonify({
            "ok": False,
            "error": f"No energy entities registered for zone '{zone_id}'",
        }), 404

    # Aggregate zone energy from HA entities
    entity_ids = zone_config["entity_ids"]
    total_power = 0.0
    breakdown = []

    for eid in entity_ids:
        value = _energy_service._find_single_entity_value(eid)
        if value is not None:
            total_power += value
            breakdown.append({"entity_id": eid, "value": round(value, 2), "status": "ok"})
        else:
            breakdown.append({"entity_id": eid, "value": None, "status": "unavailable"})

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "zone_name": zone_config["zone_name"],
        "total_power_watts": round(total_power, 2),
        "entity_count": len(entity_ids),
        "active_count": sum(1 for b in breakdown if b["status"] == "ok"),
        "breakdown": breakdown,
        "timestamp": _energy_service._get_timestamp(),
    })


@energy_bp.route("/api/v1/energy/zones", methods=["GET"])
@require_api_key
def get_all_zone_energy():
    """Get energy overview for all registered zones."""
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503

    zone_map = getattr(_energy_service, "_zone_energy_map", {})
    zones = []

    for zone_id, config in zone_map.items():
        total_power = 0.0
        active = 0
        for eid in config["entity_ids"]:
            value = _energy_service._find_single_entity_value(eid)
            if value is not None:
                total_power += value
                active += 1

        zones.append({
            "zone_id": zone_id,
            "zone_name": config["zone_name"],
            "total_power_watts": round(total_power, 2),
            "entity_count": len(config["entity_ids"]),
            "active_count": active,
        })

    # Sort by power descending (highest consuming zone first)
    zones.sort(key=lambda z: z["total_power_watts"], reverse=True)

    return jsonify({
        "ok": True,
        "zones": zones,
        "total_zones": len(zones),
        "global_power_watts": round(sum(z["total_power_watts"] for z in zones), 2),
        "timestamp": _energy_service._get_timestamp(),
    })


# ═══════════════════════════════════════════════════════════════════════════
# v5.2.0 — Sankey Energy Flow Diagrams
# ═══════════════════════════════════════════════════════════════════════════

@energy_bp.route("/api/v1/energy/sankey", methods=["GET"])
@require_api_key
def get_sankey_data():
    """Get Sankey flow data as JSON.

    Query params:
        zone: Optional zone_id to filter (default: global)
    """
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503

    zone_id = request.args.get("zone")
    snapshot = _energy_service.get_energy_snapshot()

    # Build zone data if zones registered
    zone_data = None
    if zone_id:
        zone_map = getattr(_energy_service, "_zone_energy_map", {})
        zone_config = zone_map.get(zone_id)
        if zone_config:
            total = 0.0
            for eid in zone_config["entity_ids"]:
                val = _energy_service._find_single_entity_value(eid)
                if val is not None:
                    total += val
            zone_data = {zone_config["zone_name"]: total}
            title = f"Energiefluss — {zone_config['zone_name']}"
        else:
            return jsonify({"ok": False, "error": f"Zone '{zone_id}' not found"}), 404
    else:
        # Global: use all registered zones or baselines
        zone_map = getattr(_energy_service, "_zone_energy_map", {})
        if zone_map:
            zone_data = {}
            for zid, config in zone_map.items():
                total = 0.0
                for eid in config["entity_ids"]:
                    val = _energy_service._find_single_entity_value(eid)
                    if val is not None:
                        total += val
                zone_data[config["zone_name"]] = total
        title = "Energiefluss — Gesamt"

    sankey = build_sankey_from_energy(
        consumption=snapshot.total_consumption_today,
        production=snapshot.total_production_today,
        baselines=snapshot.baselines,
        zone_data=zone_data,
        title=title,
    )

    return jsonify({
        "ok": True,
        "title": sankey.title,
        "unit": sankey.unit,
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "value": n.value,
                "color": n.color,
                "category": n.category,
            }
            for n in sankey.nodes
        ],
        "flows": [
            {
                "source": f.source,
                "target": f.target,
                "value": f.value,
            }
            for f in sankey.flows
        ],
        "summary": {
            "total_consumption_kwh": snapshot.total_consumption_today,
            "total_production_kwh": snapshot.total_production_today,
            "grid_kwh": max(snapshot.total_consumption_today - snapshot.total_production_today, 0),
        },
        "timestamp": _energy_service._get_timestamp(),
    })


@energy_bp.route("/api/v1/energy/sankey.svg", methods=["GET"])
@require_api_key
def get_sankey_svg():
    """Get Sankey diagram as SVG image.

    Query params:
        zone: Optional zone_id (default: global)
        width: SVG width in px (default: 700)
        height: SVG height in px (default: 400)
        theme: dark or light (default: dark)
    """
    if not _energy_service:
        return Response(
            '<svg xmlns="http://www.w3.org/2000/svg"><text y="20">Service unavailable</text></svg>',
            mimetype="image/svg+xml",
            status=503,
        )

    zone_id = request.args.get("zone")
    width = min(int(request.args.get("width", 700)), 2000)
    height = min(int(request.args.get("height", 400)), 1200)
    theme = request.args.get("theme", "dark")

    snapshot = _energy_service.get_energy_snapshot()

    # Build zone data
    zone_data = None
    title = "Energiefluss — Gesamt"
    if zone_id:
        zone_map = getattr(_energy_service, "_zone_energy_map", {})
        zone_config = zone_map.get(zone_id)
        if zone_config:
            total = 0.0
            for eid in zone_config["entity_ids"]:
                val = _energy_service._find_single_entity_value(eid)
                if val is not None:
                    total += val
            zone_data = {zone_config["zone_name"]: total}
            title = f"Energiefluss — {zone_config['zone_name']}"
    else:
        zone_map = getattr(_energy_service, "_zone_energy_map", {})
        if zone_map:
            zone_data = {}
            for zid, config in zone_map.items():
                total = 0.0
                for eid in config["entity_ids"]:
                    val = _energy_service._find_single_entity_value(eid)
                    if val is not None:
                        total += val
                zone_data[config["zone_name"]] = total

    sankey = build_sankey_from_energy(
        consumption=snapshot.total_consumption_today,
        production=snapshot.total_production_today,
        baselines=snapshot.baselines,
        zone_data=zone_data,
        title=title,
    )

    renderer = SankeyRenderer(width=width, height=height, theme=theme)
    svg = renderer.render(sankey)

    return Response(
        svg,
        mimetype="image/svg+xml",
        headers={"Cache-Control": "public, max-age=30"},
    )


# ═══════════════════════════════════════════════════════════════════════════
# v5.6.0 — Dashboard Card Configuration
# ═══════════════════════════════════════════════════════════════════════════

@energy_bp.route("/api/v1/energy/dashboard-config", methods=["GET"])
@require_api_key
def get_dashboard_config():
    """Get dashboard card configuration data for Lovelace generation.

    Returns all data needed by the HA card generator: zones, endpoints,
    and current energy state.
    """
    if not _energy_service:
        return jsonify({"error": "Energy service not initialized"}), 503

    zone_map = getattr(_energy_service, "_zone_energy_map", {})
    zones = [
        {
            "zone_id": zid,
            "zone_name": config["zone_name"],
            "entity_count": len(config["entity_ids"]),
        }
        for zid, config in zone_map.items()
    ]

    snapshot = _energy_service.get_energy_snapshot()

    return jsonify({
        "ok": True,
        "zones": zones,
        "endpoints": {
            "energy": "/api/v1/energy",
            "anomalies": "/api/v1/energy/anomalies",
            "sankey_svg": "/api/v1/energy/sankey.svg",
            "sankey_json": "/api/v1/energy/sankey",
            "schedule": "/api/v1/predict/schedule/daily",
            "zones": "/api/v1/energy/zones",
        },
        "current_state": {
            "consumption_kwh": snapshot.total_consumption_today,
            "production_kwh": snapshot.total_production_today,
            "current_power_watts": snapshot.current_power,
            "anomalies": snapshot.anomalies_detected,
        },
        "timestamp": _energy_service._get_timestamp(),
    })


# ═══════════════════════════════════════════════════════════════════════════
# v5.10.0 — Energy Cost Tracking
# ═══════════════════════════════════════════════════════════════════════════

_cost_tracker = None


def init_cost_tracker(tracker):
    """Initialize cost tracker instance."""
    global _cost_tracker
    _cost_tracker = tracker


@energy_bp.route("/api/v1/energy/costs", methods=["GET"])
@require_api_key
def get_cost_history():
    """Get daily cost history.

    Query params:
        days: Number of days (default 30, max 365)
    """
    if not _cost_tracker:
        return jsonify({"error": "Cost tracker not initialized"}), 503

    days = min(365, request.args.get("days", 30, type=int))
    history = _cost_tracker.get_daily_history(days=days)
    return jsonify({"ok": True, "days": len(history), "history": history})


@energy_bp.route("/api/v1/energy/costs/summary", methods=["GET"])
@require_api_key
def get_cost_summary():
    """Get cost summary.

    Query params:
        period: daily, weekly, monthly (default weekly)
    """
    if not _cost_tracker:
        return jsonify({"error": "Cost tracker not initialized"}), 503

    period = request.args.get("period", "weekly")
    if period not in ("daily", "weekly", "monthly"):
        return jsonify({"ok": False, "error": "Invalid period"}), 400

    summary = _cost_tracker.get_summary(period=period)
    return jsonify({
        "ok": True,
        "period": summary.period,
        "start_date": summary.start_date,
        "end_date": summary.end_date,
        "total_cost_eur": summary.total_cost_eur,
        "total_consumption_kwh": summary.total_consumption_kwh,
        "total_production_kwh": summary.total_production_kwh,
        "total_savings_eur": summary.total_savings_eur,
        "avg_daily_cost_eur": summary.avg_daily_cost_eur,
        "days_count": summary.days_count,
    })


@energy_bp.route("/api/v1/energy/costs/budget", methods=["GET"])
@require_api_key
def get_budget_status():
    """Get monthly budget tracking."""
    if not _cost_tracker:
        return jsonify({"error": "Cost tracker not initialized"}), 503

    status = _cost_tracker.get_budget_status()
    return jsonify({
        "ok": True,
        "month": status.month,
        "budget_eur": status.budget_eur,
        "spent_eur": status.spent_eur,
        "remaining_eur": status.remaining_eur,
        "percent_used": status.percent_used,
        "projected_total_eur": status.projected_total_eur,
        "on_track": status.on_track,
    })


@energy_bp.route("/api/v1/energy/costs/compare", methods=["GET"])
@require_api_key
def get_cost_comparison():
    """Compare current vs previous period.

    Query params:
        days: Period length (default 7)
    """
    if not _cost_tracker:
        return jsonify({"error": "Cost tracker not initialized"}), 503

    days = request.args.get("days", 7, type=int)
    comparison = _cost_tracker.compare_periods(current_days=days, offset_days=days)
    return jsonify({"ok": True, **comparison})


# ═══════════════════════════════════════════════════════════════════════════
# v5.12.0 — Appliance Fingerprinting
# ═══════════════════════════════════════════════════════════════════════════

_fingerprinter = None


def init_fingerprinter(fingerprinter=None):
    """Initialize the fingerprinter singleton."""
    global _fingerprinter
    if fingerprinter is None:
        from .fingerprint import ApplianceFingerprinter
        fingerprinter = ApplianceFingerprinter()
    _fingerprinter = fingerprinter


@energy_bp.route("/api/v1/energy/fingerprints", methods=["GET"])
@require_api_key
def get_fingerprints():
    """Get all known appliance fingerprints."""
    if not _fingerprinter:
        return jsonify({"error": "Fingerprinter not initialized"}), 503

    fps = _fingerprinter.get_all_fingerprints()
    return jsonify({"ok": True, "fingerprints": fps, "count": len(fps)})


@energy_bp.route("/api/v1/energy/fingerprints/<device_id>", methods=["GET"])
@require_api_key
def get_fingerprint(device_id: str):
    """Get fingerprint for a specific device."""
    if not _fingerprinter:
        return jsonify({"error": "Fingerprinter not initialized"}), 503

    from dataclasses import asdict
    fp = _fingerprinter.get_fingerprint(device_id)
    if not fp:
        return jsonify({"ok": False, "error": "Device not found"}), 404
    return jsonify({"ok": True, **asdict(fp)})


@energy_bp.route("/api/v1/energy/fingerprints/record", methods=["POST"])
@require_api_key
def record_fingerprint():
    """Record a power signature for fingerprint learning.

    JSON body:
        device_id, device_name, device_type, samples: [{timestamp, watts}]
    """
    if not _fingerprinter:
        return jsonify({"error": "Fingerprinter not initialized"}), 503

    body = request.get_json(silent=True) or {}
    device_id = body.get("device_id")
    device_name = body.get("device_name", "")
    device_type = body.get("device_type", "unknown")
    samples = body.get("samples", [])

    if not device_id or not samples:
        return jsonify({"ok": False, "error": "device_id and samples required"}), 400

    from dataclasses import asdict
    fp = _fingerprinter.record_signature(device_id, device_name, device_type, samples)
    return jsonify({"ok": True, "fingerprint": asdict(fp)}), 201


@energy_bp.route("/api/v1/energy/fingerprints/identify", methods=["POST"])
@require_api_key
def identify_appliance():
    """Identify running appliance from current power reading.

    JSON body: {watts: float}
    """
    if not _fingerprinter:
        return jsonify({"error": "Fingerprinter not initialized"}), 503

    body = request.get_json(silent=True) or {}
    watts = body.get("watts")
    if watts is None:
        return jsonify({"ok": False, "error": "watts required"}), 400

    from dataclasses import asdict
    matches = _fingerprinter.identify(float(watts))
    return jsonify({
        "ok": True,
        "matches": [asdict(m) for m in matches],
        "count": len(matches),
    })


@energy_bp.route("/api/v1/energy/fingerprints/usage", methods=["GET"])
@require_api_key
def get_usage_stats():
    """Get usage statistics for all fingerprinted devices."""
    if not _fingerprinter:
        return jsonify({"error": "Fingerprinter not initialized"}), 503

    stats = _fingerprinter.get_all_usage_stats()
    return jsonify({"ok": True, "devices": stats, "count": len(stats)})


# ═══════════════════════════════════════════════════════════════════════════
# v5.13.0 — Energy Report Generator
# ═══════════════════════════════════════════════════════════════════════════

_report_generator = None


def init_report_generator(generator=None):
    """Initialize the report generator singleton."""
    global _report_generator
    if generator is None:
        from .report_generator import EnergyReportGenerator
        generator = EnergyReportGenerator()
    _report_generator = generator


@energy_bp.route("/api/v1/energy/reports/generate", methods=["POST"])
@require_api_key
def generate_report():
    """Generate an energy report.

    JSON body: {report_type: "daily"|"weekly"|"monthly", end_date: "YYYY-MM-DD"}
    """
    if not _report_generator:
        return jsonify({"error": "Report generator not initialized"}), 503

    from dataclasses import asdict
    from datetime import date as date_cls

    body = request.get_json(silent=True) or {}
    report_type = body.get("report_type", "weekly")
    end_str = body.get("end_date")

    end_date = None
    if end_str:
        try:
            end_date = date_cls.fromisoformat(end_str)
        except ValueError:
            return jsonify({"ok": False, "error": "Invalid date format"}), 400

    report = _report_generator.generate_report(report_type=report_type, end_date=end_date)
    return jsonify({"ok": True, "report": asdict(report)})


@energy_bp.route("/api/v1/energy/reports/coverage", methods=["GET"])
@require_api_key
def report_coverage():
    """Get data coverage for report generation."""
    if not _report_generator:
        return jsonify({"error": "Report generator not initialized"}), 503

    coverage = _report_generator.get_data_coverage()
    return jsonify({"ok": True, **coverage})


@energy_bp.route("/api/v1/energy/reports/data", methods=["POST"])
@require_api_key
def add_report_data():
    """Add daily energy data for reports.

    JSON body: {date, consumption_kwh, production_kwh, avg_price_eur_kwh, devices}
    """
    if not _report_generator:
        return jsonify({"error": "Report generator not initialized"}), 503

    from datetime import date as date_cls

    body = request.get_json(silent=True) or {}
    date_str = body.get("date")
    consumption = body.get("consumption_kwh")
    production = body.get("production_kwh", 0)

    if not date_str or consumption is None:
        return jsonify({"ok": False, "error": "date and consumption_kwh required"}), 400

    try:
        day = date_cls.fromisoformat(date_str)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid date format"}), 400

    _report_generator.add_daily_data(
        day=day,
        consumption_kwh=float(consumption),
        production_kwh=float(production),
        avg_price_eur_kwh=body.get("avg_price_eur_kwh"),
        devices=body.get("devices"),
    )
    return jsonify({"ok": True, "date": date_str}), 201


# ═══════════════════════════════════════════════════════════════════════════
# v5.14.0 — Demand Response Manager
# ═══════════════════════════════════════════════════════════════════════════

_demand_response = None


def init_demand_response(manager=None):
    """Initialize the demand response manager singleton."""
    global _demand_response
    if manager is None:
        from .demand_response import DemandResponseManager
        manager = DemandResponseManager()
    _demand_response = manager


@energy_bp.route("/api/v1/energy/demand-response/status", methods=["GET"])
@require_api_key
def dr_status():
    """Get demand response system status."""
    if not _demand_response:
        return jsonify({"error": "Demand response not initialized"}), 503
    from dataclasses import asdict
    status = _demand_response.get_status()
    return jsonify({"ok": True, **asdict(status)})


@energy_bp.route("/api/v1/energy/demand-response/signal", methods=["POST"])
@require_api_key
def dr_receive_signal():
    """Receive a grid signal.

    JSON body: {level, source, reason, target_reduction_watts, duration_minutes}
    """
    if not _demand_response:
        return jsonify({"error": "Demand response not initialized"}), 503

    body = request.get_json(silent=True) or {}
    level = body.get("level", 1)
    from dataclasses import asdict
    signal = _demand_response.receive_signal(
        level=int(level),
        source=body.get("source", "manual"),
        reason=body.get("reason", ""),
        target_reduction_watts=float(body.get("target_reduction_watts", 0)),
        duration_minutes=int(body.get("duration_minutes", 60)),
    )
    return jsonify({"ok": True, "signal": asdict(signal)}), 201


@energy_bp.route("/api/v1/energy/demand-response/signals", methods=["GET"])
@require_api_key
def dr_active_signals():
    """Get active grid signals."""
    if not _demand_response:
        return jsonify({"error": "Demand response not initialized"}), 503
    signals = _demand_response.get_active_signals()
    return jsonify({"ok": True, "signals": signals, "count": len(signals)})


@energy_bp.route("/api/v1/energy/demand-response/devices", methods=["GET"])
@require_api_key
def dr_devices():
    """Get all managed devices."""
    if not _demand_response:
        return jsonify({"error": "Demand response not initialized"}), 503
    devices = _demand_response.get_devices()
    return jsonify({"ok": True, "devices": devices, "count": len(devices)})


@energy_bp.route("/api/v1/energy/demand-response/devices", methods=["POST"])
@require_api_key
def dr_register_device():
    """Register a device for demand response.

    JSON body: {device_id, device_name, priority, max_watts, auto_restore_minutes}
    """
    if not _demand_response:
        return jsonify({"error": "Demand response not initialized"}), 503

    body = request.get_json(silent=True) or {}
    device_id = body.get("device_id")
    if not device_id:
        return jsonify({"ok": False, "error": "device_id required"}), 400

    from dataclasses import asdict
    dev = _demand_response.register_device(
        device_id=device_id,
        device_name=body.get("device_name", device_id),
        priority=int(body.get("priority", 2)),
        max_watts=float(body.get("max_watts", 1000)),
        auto_restore_minutes=int(body.get("auto_restore_minutes", 60)),
    )
    return jsonify({"ok": True, "device": asdict(dev)}), 201


@energy_bp.route("/api/v1/energy/demand-response/curtail/<device_id>", methods=["POST"])
@require_api_key
def dr_curtail(device_id: str):
    """Manually curtail a device."""
    if not _demand_response:
        return jsonify({"error": "Demand response not initialized"}), 503

    from dataclasses import asdict
    action = _demand_response.curtail_device(device_id)
    if not action:
        return jsonify({"ok": False, "error": "Device not found or already curtailed"}), 404
    return jsonify({"ok": True, "action": asdict(action)})


@energy_bp.route("/api/v1/energy/demand-response/restore/<device_id>", methods=["POST"])
@require_api_key
def dr_restore(device_id: str):
    """Restore a curtailed device."""
    if not _demand_response:
        return jsonify({"error": "Demand response not initialized"}), 503

    from dataclasses import asdict
    action = _demand_response.restore_device(device_id)
    if not action:
        return jsonify({"ok": False, "error": "Device not found or not curtailed"}), 404
    return jsonify({"ok": True, "action": asdict(action)})


@energy_bp.route("/api/v1/energy/demand-response/history", methods=["GET"])
@require_api_key
def dr_history():
    """Get curtailment action history."""
    if not _demand_response:
        return jsonify({"error": "Demand response not initialized"}), 503

    limit = request.args.get("limit", 50, type=int)
    history = _demand_response.get_action_history(limit=limit)
    return jsonify({"ok": True, "actions": history, "count": len(history)})


@energy_bp.route("/api/v1/energy/demand-response/metrics", methods=["GET"])
@require_api_key
def dr_metrics():
    """Get demand response performance metrics."""
    if not _demand_response:
        return jsonify({"error": "Demand response not initialized"}), 503
    metrics = _demand_response.get_metrics()
    return jsonify({"ok": True, **metrics})
