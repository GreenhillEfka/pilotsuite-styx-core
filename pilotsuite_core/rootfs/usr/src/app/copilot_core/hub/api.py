"""Hub API endpoints for PilotSuite (v7.6.0)."""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from dataclasses import asdict

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

hub_bp = Blueprint("hub", __name__, url_prefix="/api/v1/hub")

_dashboard: object | None = None
_plugin_manager: object | None = None
_multi_home: object | None = None
_maintenance_engine: object | None = None
_anomaly_engine: object | None = None
_zone_engine: object | None = None
_light_engine: object | None = None
_mode_engine: object | None = None
_media_engine: object | None = None
_energy_advisor: object | None = None
_template_engine: object | None = None
_scene_engine: object | None = None
_presence_engine: object | None = None
_notification_engine: object | None = None
_integration_hub: object | None = None
_brain_architecture: object | None = None
_brain_activity: object | None = None


def init_hub_api(dashboard=None, plugin_manager=None, multi_home=None,
                 maintenance_engine=None, anomaly_engine=None,
                 zone_engine=None, light_engine=None,
                 mode_engine=None, media_engine=None,
                 energy_advisor=None, template_engine=None,
                 scene_engine=None, presence_engine=None,
                 notification_engine=None, integration_hub=None,
                 brain_architecture=None, brain_activity=None) -> None:
    """Initialize hub services."""
    global _dashboard, _plugin_manager, _multi_home, _maintenance_engine, _anomaly_engine, _zone_engine, _light_engine, _mode_engine, _media_engine, _energy_advisor, _template_engine, _scene_engine, _presence_engine, _notification_engine, _integration_hub, _brain_architecture, _brain_activity
    _dashboard = dashboard
    _plugin_manager = plugin_manager
    _multi_home = multi_home
    _maintenance_engine = maintenance_engine
    _anomaly_engine = anomaly_engine
    _zone_engine = zone_engine
    _light_engine = light_engine
    _mode_engine = mode_engine
    _media_engine = media_engine
    _energy_advisor = energy_advisor
    _template_engine = template_engine
    _scene_engine = scene_engine
    _presence_engine = presence_engine
    _notification_engine = notification_engine
    _integration_hub = integration_hub
    _brain_architecture = brain_architecture
    _brain_activity = brain_activity
    logger.info(
        "Hub API initialized (dashboard: %s, plugins: %s, multi_home: %s, anomaly: %s, zones: %s, light: %s, modes: %s, media: %s, energy: %s, templates: %s, scenes: %s, presence: %s, notifications: %s, integration: %s, brain: %s, activity: %s)",
        dashboard is not None,
        plugin_manager is not None,
        multi_home is not None,
        anomaly_engine is not None,
        zone_engine is not None,
        light_engine is not None,
        mode_engine is not None,
        media_engine is not None,
        energy_advisor is not None,
        template_engine is not None,
        scene_engine is not None,
        presence_engine is not None,
        notification_engine is not None,
        integration_hub is not None,
        brain_architecture is not None,
        brain_activity is not None,
    )


# ── Dashboard endpoints ──────────────────────────────────────────────────


@hub_bp.route("/dashboard", methods=["GET"])
@require_token
def get_dashboard():
    """Get complete dashboard overview."""
    if not _dashboard:
        return jsonify({"error": "Dashboard not initialized"}), 503
    overview = _dashboard.get_overview()
    return jsonify({"ok": True, **asdict(overview)})


@hub_bp.route("/dashboard/widget/<widget_type>", methods=["GET"])
@require_token
def get_widget(widget_type):
    """Get a single widget's data."""
    if not _dashboard:
        return jsonify({"error": "Dashboard not initialized"}), 503
    widget = _dashboard.get_widget(widget_type)
    if not widget:
        return jsonify({"ok": False, "error": "Widget not found"}), 404
    return jsonify({"ok": True, **widget})


@hub_bp.route("/dashboard/layout", methods=["POST"])
@require_token
def set_layout():
    """Set dashboard layout.

    JSON body: {"name": "custom", "columns": 3, "theme": "dark", "language": "de"}
    """
    if not _dashboard:
        return jsonify({"error": "Dashboard not initialized"}), 503
    body = request.get_json(silent=True) or {}
    _dashboard.set_layout(
        name=body.get("name", "default"),
        columns=body.get("columns", 3),
        theme=body.get("theme", "auto"),
        language=body.get("language", "de"),
    )
    return jsonify({"ok": True, "layout": body})


@hub_bp.route("/dashboard/widget", methods=["POST"])
@require_token
def add_widget():
    """Add a widget.

    JSON body: {"widget_type": "...", "title": "...", "icon": "...", "size": "medium"}
    """
    if not _dashboard:
        return jsonify({"error": "Dashboard not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _dashboard.add_widget(
        body.get("widget_type", ""),
        body.get("title", "Widget"),
        body.get("icon", "mdi:puzzle"),
        body.get("size", "medium"),
    )
    return jsonify({"ok": result})


@hub_bp.route("/dashboard/widget/<widget_type>", methods=["DELETE"])
@require_token
def remove_widget(widget_type):
    """Remove a widget."""
    if not _dashboard:
        return jsonify({"error": "Dashboard not initialized"}), 503
    result = _dashboard.remove_widget(widget_type)
    return jsonify({"ok": result})


# ── Plugin endpoints ─────────────────────────────────────────────────────


@hub_bp.route("/plugins", methods=["GET"])
@require_token
def get_plugins():
    """Get plugin registry summary."""
    if not _plugin_manager:
        return jsonify({"error": "Plugin manager not initialized"}), 503
    summary = _plugin_manager.get_summary()
    return jsonify({"ok": True, **asdict(summary)})


@hub_bp.route("/plugins/<plugin_id>", methods=["GET"])
@require_token
def get_plugin(plugin_id):
    """Get plugin details."""
    if not _plugin_manager:
        return jsonify({"error": "Plugin manager not initialized"}), 503
    info = _plugin_manager.get_plugin(plugin_id)
    if not info:
        return jsonify({"ok": False, "error": "Plugin not found"}), 404
    return jsonify({"ok": True, **info})


@hub_bp.route("/plugins/<plugin_id>/activate", methods=["POST"])
@require_token
def activate_plugin(plugin_id):
    """Activate a plugin."""
    if not _plugin_manager:
        return jsonify({"error": "Plugin manager not initialized"}), 503
    result = _plugin_manager.activate_plugin(plugin_id)
    return jsonify({"ok": result, "plugin_id": plugin_id, "action": "activate"})


@hub_bp.route("/plugins/<plugin_id>/disable", methods=["POST"])
@require_token
def disable_plugin(plugin_id):
    """Disable a plugin."""
    if not _plugin_manager:
        return jsonify({"error": "Plugin manager not initialized"}), 503
    result = _plugin_manager.disable_plugin(plugin_id)
    return jsonify({"ok": result, "plugin_id": plugin_id, "action": "disable"})


@hub_bp.route("/plugins/<plugin_id>/config", methods=["POST"])
@require_token
def configure_plugin(plugin_id):
    """Configure a plugin.

    JSON body: {"key": "value", ...}
    """
    if not _plugin_manager:
        return jsonify({"error": "Plugin manager not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _plugin_manager.configure_plugin(plugin_id, body)
    return jsonify({"ok": result, "plugin_id": plugin_id})


# ── Multi-Home endpoints ─────────────────────────────────────────────────


@hub_bp.route("/homes", methods=["GET"])
@require_token
def get_homes():
    """Get multi-home summary."""
    if not _multi_home:
        return jsonify({"error": "Multi-home manager not initialized"}), 503
    summary = _multi_home.get_summary()
    return jsonify({"ok": True, **asdict(summary)})


@hub_bp.route("/homes/<home_id>", methods=["GET"])
@require_token
def get_home(home_id):
    """Get home details."""
    if not _multi_home:
        return jsonify({"error": "Multi-home manager not initialized"}), 503
    info = _multi_home.get_home(home_id)
    if not info:
        return jsonify({"ok": False, "error": "Home not found"}), 404
    return jsonify({"ok": True, **info})


@hub_bp.route("/homes", methods=["POST"])
@require_token
def add_home():
    """Add a home.

    JSON body: {"home_id": "...", "name": "...", "address": "...", "core_url": "...", "token": "..."}
    """
    if not _multi_home:
        return jsonify({"error": "Multi-home manager not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _multi_home.add_home(
        home_id=body.get("home_id", ""),
        name=body.get("name", "Home"),
        address=body.get("address", ""),
        latitude=float(body.get("latitude", 0)),
        longitude=float(body.get("longitude", 0)),
        core_url=body.get("core_url", ""),
        token=body.get("token", ""),
        icon=body.get("icon", "mdi:home"),
    )
    return jsonify({"ok": result})


@hub_bp.route("/homes/<home_id>", methods=["DELETE"])
@require_token
def remove_home(home_id):
    """Remove a home."""
    if not _multi_home:
        return jsonify({"error": "Multi-home manager not initialized"}), 503
    result = _multi_home.remove_home(home_id)
    return jsonify({"ok": result})


@hub_bp.route("/homes/<home_id>/activate", methods=["POST"])
@require_token
def set_active_home(home_id):
    """Switch active home."""
    if not _multi_home:
        return jsonify({"error": "Multi-home manager not initialized"}), 503
    result = _multi_home.set_active_home(home_id)
    return jsonify({"ok": result, "active_home_id": home_id})


@hub_bp.route("/homes/<home_id>/status", methods=["POST"])
@require_token
def update_home_status(home_id):
    """Update home status.

    JSON body: {"status": "online", "device_count": 42, "energy_kwh": 15.3, "cost_eur": 4.59}
    """
    if not _multi_home:
        return jsonify({"error": "Multi-home manager not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _multi_home.update_home_status(
        home_id=home_id,
        status=body.get("status", "online"),
        device_count=body.get("device_count"),
        energy_kwh=body.get("energy_kwh"),
        cost_eur=body.get("cost_eur"),
    )
    return jsonify({"ok": result})


# ── Predictive Maintenance endpoints (v6.1.0) ────────────────────────────


@hub_bp.route("/maintenance", methods=["GET"])
@require_token
def get_maintenance_summary():
    """Get predictive maintenance summary."""
    if not _maintenance_engine:
        return jsonify({"error": "Maintenance engine not initialized"}), 503
    summary = _maintenance_engine.get_summary()
    return jsonify({"ok": True, **asdict(summary)})


@hub_bp.route("/maintenance/device/<device_id>", methods=["GET"])
@require_token
def get_device_health(device_id):
    """Get device health details."""
    if not _maintenance_engine:
        return jsonify({"error": "Maintenance engine not initialized"}), 503
    info = _maintenance_engine.get_device(device_id)
    if not info:
        return jsonify({"ok": False, "error": "Device not found"}), 404
    return jsonify({"ok": True, **info})


@hub_bp.route("/maintenance/register", methods=["POST"])
@require_token
def register_device():
    """Register a device for monitoring.

    JSON body: {"device_id": "...", "name": "...", "device_type": "sensor"}
    """
    if not _maintenance_engine:
        return jsonify({"error": "Maintenance engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    _maintenance_engine.register_device(
        body.get("device_id", ""),
        body.get("name", "Device"),
        body.get("device_type", "sensor"),
    )
    return jsonify({"ok": True, "device_id": body.get("device_id", "")})


@hub_bp.route("/maintenance/ingest", methods=["POST"])
@require_token
def ingest_device_metrics():
    """Ingest device metrics.

    JSON body: {"metrics": [{"device_id": "...", "metric": "...", "value": ...}, ...]}
    """
    if not _maintenance_engine:
        return jsonify({"error": "Maintenance engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    metrics = body.get("metrics", [])
    count = _maintenance_engine.ingest_metrics_batch(metrics)
    return jsonify({"ok": True, "ingested": count})


@hub_bp.route("/maintenance/evaluate", methods=["POST"])
@require_token
def evaluate_devices():
    """Trigger health evaluation for all devices."""
    if not _maintenance_engine:
        return jsonify({"error": "Maintenance engine not initialized"}), 503
    results = _maintenance_engine.evaluate_all()
    summary = _maintenance_engine.get_summary()
    return jsonify({"ok": True, "evaluated": len(results), **asdict(summary)})


# ── Anomaly Detection v2 endpoints (v6.2.0) ────────────────────────────


@hub_bp.route("/anomalies", methods=["GET"])
@require_token
def get_anomaly_summary():
    """Get anomaly detection summary."""
    if not _anomaly_engine:
        return jsonify({"error": "Anomaly engine not initialized"}), 503
    summary = _anomaly_engine.get_summary()
    return jsonify({"ok": True, **asdict(summary)})


@hub_bp.route("/anomalies/list", methods=["GET"])
@require_token
def get_anomalies():
    """Get anomalies with optional filters.

    Query params: entity_id, severity, type, limit
    """
    if not _anomaly_engine:
        return jsonify({"error": "Anomaly engine not initialized"}), 503
    entity_id = request.args.get("entity_id")
    severity = request.args.get("severity")
    atype = request.args.get("type")
    limit = int(request.args.get("limit", 50))
    anomalies = _anomaly_engine.get_anomalies(entity_id, severity, atype, limit)
    return jsonify({
        "ok": True,
        "count": len(anomalies),
        "anomalies": [asdict(a) for a in anomalies],
    })


@hub_bp.route("/anomalies/ingest", methods=["POST"])
@require_token
def ingest_anomaly_data():
    """Ingest sensor data for anomaly detection.

    JSON body: {"points": [{"entity_id": "...", "value": ..., "timestamp"?: "..."}, ...]}
    """
    if not _anomaly_engine:
        return jsonify({"error": "Anomaly engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    points = body.get("points", [])
    count = _anomaly_engine.ingest_batch(points)
    return jsonify({"ok": True, "ingested": count})


@hub_bp.route("/anomalies/detect", methods=["POST"])
@require_token
def run_anomaly_detection():
    """Run anomaly detection.

    JSON body (optional): {"entity_id": "..."} to detect for specific entity.
    """
    if not _anomaly_engine:
        return jsonify({"error": "Anomaly engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    entity_id = body.get("entity_id")
    _anomaly_engine.learn_patterns(entity_id)
    anomalies = _anomaly_engine.detect(entity_id)
    return jsonify({
        "ok": True,
        "new_anomalies": len(anomalies),
        "anomalies": [asdict(a) for a in anomalies],
    })


@hub_bp.route("/anomalies/correlations", methods=["GET"])
@require_token
def get_correlations():
    """Get learned entity correlations."""
    if not _anomaly_engine:
        return jsonify({"error": "Anomaly engine not initialized"}), 503
    corrs = _anomaly_engine.get_correlations()
    return jsonify({"ok": True, "correlations": corrs})


@hub_bp.route("/anomalies/learn", methods=["POST"])
@require_token
def learn_patterns():
    """Trigger pattern learning and correlation discovery."""
    if not _anomaly_engine:
        return jsonify({"error": "Anomaly engine not initialized"}), 503
    profiles = _anomaly_engine.learn_patterns()
    correlations = _anomaly_engine.learn_correlations()
    return jsonify({
        "ok": True,
        "profiles_updated": profiles,
        "correlations_learned": correlations,
    })


@hub_bp.route("/anomalies/clear", methods=["POST"])
@require_token
def clear_anomalies():
    """Clear anomalies.

    JSON body (optional): {"entity_id": "..."} to clear for specific entity.
    """
    if not _anomaly_engine:
        return jsonify({"error": "Anomaly engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    entity_id = body.get("entity_id")
    cleared = _anomaly_engine.clear_anomalies(entity_id)
    return jsonify({"ok": True, "cleared": cleared})


# ── Habitus-Zonen endpoints (v6.4.0) ───────────────────────────────────────


@hub_bp.route("/zones", methods=["GET"])
@require_token
def get_zones_overview():
    """Get Habitus-Zonen overview."""
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    overview = _zone_engine.get_overview()
    return jsonify({"ok": True, **asdict(overview)})


@hub_bp.route("/zones/<zone_id>", methods=["GET"])
@require_token
def get_zone_detail(zone_id):
    """Get zone details."""
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    zone = _zone_engine.get_zone(zone_id)
    if not zone:
        return jsonify({"ok": False, "error": "Zone not found"}), 404
    return jsonify({"ok": True, **zone})


@hub_bp.route("/zones", methods=["POST"])
@require_token
def create_zone():
    """Create a Habitus Zone.

    JSON body: {"zone_id": "...", "name": "...", "room_ids": [...], "icon": "...", "priority": 0}
    """
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    zone = _zone_engine.create_zone(
        zone_id=body.get("zone_id", ""),
        name=body.get("name", "Zone"),
        room_ids=body.get("room_ids", []),
        icon=body.get("icon", "mdi:home-floor-1"),
        priority=body.get("priority", 0),
    )
    return jsonify({"ok": True, "zone_id": zone.zone_id, "entity_count": len(zone.entities)})


@hub_bp.route("/zones/<zone_id>", methods=["DELETE"])
@require_token
def delete_zone_endpoint(zone_id):
    """Delete a zone."""
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    result = _zone_engine.delete_zone(zone_id)
    return jsonify({"ok": result})


@hub_bp.route("/zones/<zone_id>/mode", methods=["POST"])
@require_token
def set_zone_mode_endpoint(zone_id):
    """Set zone mode.

    JSON body: {"mode": "party"} — active/idle/sleeping/party/away/custom
    """
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _zone_engine.set_zone_mode(zone_id, body.get("mode", "active"))
    return jsonify({"ok": result, "zone_id": zone_id, "mode": body.get("mode", "active")})


@hub_bp.route("/zones/<zone_id>/room", methods=["POST"])
@require_token
def add_room_to_zone_endpoint(zone_id):
    """Add a room to a zone.

    JSON body: {"room_id": "..."}
    """
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _zone_engine.add_room_to_zone(zone_id, body.get("room_id", ""))
    return jsonify({"ok": result})


@hub_bp.route("/zones/<zone_id>/room/<room_id>", methods=["DELETE"])
@require_token
def remove_room_from_zone_endpoint(zone_id, room_id):
    """Remove a room from a zone."""
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    result = _zone_engine.remove_room_from_zone(zone_id, room_id)
    return jsonify({"ok": result})


@hub_bp.route("/zones/rooms", methods=["GET"])
@require_token
def get_rooms():
    """Get all registered rooms."""
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    rooms = _zone_engine.get_rooms()
    return jsonify({"ok": True, "rooms": rooms})


@hub_bp.route("/zones/rooms", methods=["POST"])
@require_token
def register_room_endpoint():
    """Register a room.

    JSON body: {"room_id": "...", "name": "...", "area_id": "...", "entities": [...]}
    """
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    room = _zone_engine.register_room(
        room_id=body.get("room_id", ""),
        name=body.get("name", "Room"),
        area_id=body.get("area_id", ""),
        entities=body.get("entities", []),
        floor=body.get("floor", ""),
        icon=body.get("icon", "mdi:door"),
    )
    return jsonify({"ok": True, "room_id": room.room_id, "entities": len(room.entities)})


@hub_bp.route("/zones/templates", methods=["GET"])
@require_token
def get_zone_templates():
    """Get available zone templates."""
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    return jsonify({"ok": True, "templates": _zone_engine.get_templates()})


@hub_bp.route("/zones/template/<template_id>", methods=["POST"])
@require_token
def create_zone_from_template_endpoint(template_id):
    """Create a zone from a template."""
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    zone = _zone_engine.create_zone_from_template(template_id)
    if not zone:
        return jsonify({"ok": False, "error": "Template not found"}), 404
    return jsonify({"ok": True, "zone_id": zone.zone_id, "rooms": zone.rooms})


@hub_bp.route("/zones/modes", methods=["GET"])
@require_token
def get_zone_modes():
    """Get available zone modes."""
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    return jsonify({"ok": True, "modes": _zone_engine.get_modes()})


# ── Light Intelligence endpoints (v6.5.0) ──────────────────────────────────


@hub_bp.route("/light", methods=["GET"])
@require_token
def get_light_dashboard():
    """Get light intelligence dashboard."""
    if not _light_engine:
        return jsonify({"error": "Light engine not initialized"}), 503
    dashboard = _light_engine.get_dashboard()
    return jsonify({"ok": True, **asdict(dashboard)})


@hub_bp.route("/light/sun", methods=["POST"])
@require_token
def update_sun():
    """Update sun position.

    JSON body: {"elevation": 45.0, "azimuth": 180.0}
    """
    if not _light_engine:
        return jsonify({"error": "Light engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    sun = _light_engine.update_sun(
        float(body.get("elevation", 0)),
        float(body.get("azimuth", 0)),
    )
    return jsonify({"ok": True, **asdict(sun)})


@hub_bp.route("/light/brightness", methods=["POST"])
@require_token
def update_light_brightness():
    """Update brightness readings.

    JSON body: {"readings": [{"entity_id": "...", "lux": ...}, ...]}
    """
    if not _light_engine:
        return jsonify({"error": "Light engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    count = _light_engine.update_brightness_batch(body.get("readings", []))
    return jsonify({"ok": True, "updated": count})


@hub_bp.route("/light/zone/<zone_id>", methods=["GET"])
@require_token
def get_zone_light(zone_id):
    """Get zone brightness analysis."""
    if not _light_engine:
        return jsonify({"error": "Light engine not initialized"}), 503
    zb = _light_engine.get_zone_brightness(zone_id)
    return jsonify({"ok": True, **asdict(zb)})


@hub_bp.route("/light/scenes", methods=["GET"])
@require_token
def get_light_scenes():
    """Get available mood scenes."""
    if not _light_engine:
        return jsonify({"error": "Light engine not initialized"}), 503
    return jsonify({"ok": True, "scenes": _light_engine.get_scenes()})


@hub_bp.route("/light/scene", methods=["POST"])
@require_token
def set_light_scene():
    """Set active scene.

    JSON body: {"scene_id": "relax", "zone_id"?: "..."}
    """
    if not _light_engine:
        return jsonify({"error": "Light engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _light_engine.set_active_scene(
        body.get("scene_id", ""),
        body.get("zone_id"),
    )
    return jsonify({"ok": result})


@hub_bp.route("/light/suggest", methods=["GET"])
@require_token
def suggest_light_scene():
    """Get scene suggestion based on current conditions."""
    if not _light_engine:
        return jsonify({"error": "Light engine not initialized"}), 503
    scene = _light_engine.suggest_scene()
    if not scene:
        return jsonify({"ok": True, "suggestion": None})
    return jsonify({
        "ok": True,
        "suggestion": {
            "scene_id": scene.scene_id,
            "name_de": scene.name_de,
            "brightness_pct": scene.brightness_pct,
            "color_temp_k": scene.color_temp_k,
        },
    })


# ── Zone Modes endpoints (v6.6.0) ──────────────────────────────────────────


@hub_bp.route("/modes", methods=["GET"])
@require_token
def get_mode_overview():
    """Get zone modes overview."""
    if not _mode_engine:
        return jsonify({"error": "Mode engine not initialized"}), 503
    overview = _mode_engine.get_overview()
    return jsonify({"ok": True, **asdict(overview)})


@hub_bp.route("/modes/available", methods=["GET"])
@require_token
def get_available_modes():
    """Get all available mode definitions."""
    if not _mode_engine:
        return jsonify({"error": "Mode engine not initialized"}), 503
    modes = _mode_engine.get_available_modes()
    return jsonify({"ok": True, "modes": modes})


@hub_bp.route("/modes/zone/<zone_id>", methods=["GET"])
@require_token
def get_zone_mode_status(zone_id):
    """Get current mode status for a zone."""
    if not _mode_engine:
        return jsonify({"error": "Mode engine not initialized"}), 503
    status = _mode_engine.get_zone_status(zone_id)
    return jsonify({"ok": True, **asdict(status)})


@hub_bp.route("/modes/activate", methods=["POST"])
@require_token
def activate_zone_mode():
    """Activate a mode on a zone.

    JSON body: {"zone_id": "...", "mode_id": "...", "duration_min"?: ..., "activated_by"?: "user"}
    """
    if not _mode_engine:
        return jsonify({"error": "Mode engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _mode_engine.activate_mode(
        zone_id=body.get("zone_id", ""),
        mode_id=body.get("mode_id", ""),
        duration_min=body.get("duration_min"),
        activated_by=body.get("activated_by", "user"),
    )
    return jsonify({"ok": result, "zone_id": body.get("zone_id"), "mode_id": body.get("mode_id")})


@hub_bp.route("/modes/deactivate", methods=["POST"])
@require_token
def deactivate_zone_mode():
    """Deactivate the current mode on a zone.

    JSON body: {"zone_id": "..."}
    """
    if not _mode_engine:
        return jsonify({"error": "Mode engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _mode_engine.deactivate_mode(body.get("zone_id", ""))
    return jsonify({"ok": result, "zone_id": body.get("zone_id")})


@hub_bp.route("/modes/expire", methods=["POST"])
@require_token
def check_mode_expirations():
    """Check and expire timed-out modes."""
    if not _mode_engine:
        return jsonify({"error": "Mode engine not initialized"}), 503
    expired = _mode_engine.check_expirations()
    return jsonify({"ok": True, "expired_zones": expired})


@hub_bp.route("/modes/custom", methods=["POST"])
@require_token
def register_custom_mode():
    """Register a custom mode.

    JSON body: {"mode_id": "...", "name_de": "...", "name_en"?: "...", "icon"?: "...",
                "suppress_automations"?: false, "suppress_lights"?: false, ...}
    """
    if not _mode_engine:
        return jsonify({"error": "Mode engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    mode_id = body.pop("mode_id", "")
    name_de = body.pop("name_de", "")
    name_en = body.pop("name_en", "")
    icon = body.pop("icon", "mdi:cog")
    result = _mode_engine.register_custom_mode(mode_id, name_de, name_en, icon, **body)
    return jsonify({"ok": result, "mode_id": mode_id})


# ── Media Follow / Musikwolke endpoints (v6.7.0) ───────────────────────────


@hub_bp.route("/media", methods=["GET"])
@require_token
def get_media_dashboard():
    """Get media cloud dashboard overview."""
    if not _media_engine:
        return jsonify({"error": "Media engine not initialized"}), 503
    dashboard = _media_engine.get_dashboard()
    return jsonify({"ok": True, **asdict(dashboard)})


@hub_bp.route("/media/sources", methods=["GET"])
@require_token
def get_media_sources():
    """Get all registered media sources."""
    if not _media_engine:
        return jsonify({"error": "Media engine not initialized"}), 503
    return jsonify({"ok": True, "sources": _media_engine.get_sources()})


@hub_bp.route("/media/sources", methods=["POST"])
@require_token
def register_media_source():
    """Register a media source.

    JSON body: {"entity_id": "...", "name": "...", "zone_id": "...", "media_type"?: "music"}
    """
    if not _media_engine:
        return jsonify({"error": "Media engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    source = _media_engine.register_source(
        entity_id=body.get("entity_id", ""),
        name=body.get("name", ""),
        zone_id=body.get("zone_id", ""),
        media_type=body.get("media_type", "music"),
    )
    return jsonify({"ok": True, "entity_id": source.entity_id, "zone_id": source.zone_id})


@hub_bp.route("/media/sources/<path:entity_id>", methods=["DELETE"])
@require_token
def unregister_media_source(entity_id):
    """Unregister a media source."""
    if not _media_engine:
        return jsonify({"error": "Media engine not initialized"}), 503
    result = _media_engine.unregister_source(entity_id)
    return jsonify({"ok": result})


@hub_bp.route("/media/playback", methods=["POST"])
@require_token
def update_media_playback():
    """Update playback state.

    JSON body: {"entity_id": "...", "state": "playing", "title"?: "...", "artist"?: "...",
                "album"?: "...", "volume_pct"?: 50}
    """
    if not _media_engine:
        return jsonify({"error": "Media engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    session = _media_engine.update_playback(
        entity_id=body.get("entity_id", ""),
        state=body.get("state", "idle"),
        title=body.get("title", ""),
        artist=body.get("artist", ""),
        album=body.get("album", ""),
        volume_pct=body.get("volume_pct"),
        media_image_url=body.get("media_image_url", ""),
    )
    if session:
        return jsonify({"ok": True, "session_id": session.session_id, "state": session.state})
    return jsonify({"ok": True, "session_id": None})


@hub_bp.route("/media/sessions", methods=["GET"])
@require_token
def get_media_sessions():
    """Get all active playback sessions."""
    if not _media_engine:
        return jsonify({"error": "Media engine not initialized"}), 503
    return jsonify({"ok": True, "sessions": _media_engine.get_active_sessions()})


@hub_bp.route("/media/zone/<zone_id>", methods=["GET"])
@require_token
def get_zone_media(zone_id):
    """Get media state for a zone."""
    if not _media_engine:
        return jsonify({"error": "Media engine not initialized"}), 503
    zm = _media_engine.get_zone_media(zone_id)
    return jsonify({"ok": True, **asdict(zm)})


@hub_bp.route("/media/follow", methods=["POST"])
@require_token
def set_media_follow():
    """Set follow mode.

    JSON body: {"zone_id"?: "...", "enabled": true, "global"?: false}
    """
    if not _media_engine:
        return jsonify({"error": "Media engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    if body.get("global"):
        _media_engine.set_global_follow(body.get("enabled", False))
    else:
        _media_engine.set_follow_zone(body.get("zone_id", ""), body.get("enabled", False))
    return jsonify({"ok": True})


@hub_bp.route("/media/transfer", methods=["POST"])
@require_token
def transfer_media():
    """Transfer playback to another zone.

    JSON body: {"session_id": "...", "to_zone_id": "...", "trigger"?: "manual"}
    """
    if not _media_engine:
        return jsonify({"error": "Media engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    transfer = _media_engine.transfer_playback(
        body.get("session_id", ""),
        body.get("to_zone_id", ""),
        body.get("trigger", "manual"),
    )
    if transfer:
        return jsonify({"ok": True, "from_zone": transfer.from_zone, "to_zone": transfer.to_zone})
    return jsonify({"ok": False, "error": "Transfer failed"}), 400


@hub_bp.route("/media/zone_enter", methods=["POST"])
@require_token
def on_zone_enter_media():
    """Handle user entering a zone — trigger media follow.

    JSON body: {"zone_id": "..."}
    """
    if not _media_engine:
        return jsonify({"error": "Media engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    transfers = _media_engine.on_zone_enter(body.get("zone_id", ""))
    return jsonify({
        "ok": True,
        "transfers": len(transfers),
        "details": [
            {"from": t.from_zone, "to": t.to_zone, "title": t.title}
            for t in transfers
        ],
    })


# ── Energy Advisor endpoints (v6.8.0) ──────────────────────────────────────


@hub_bp.route("/energy", methods=["GET"])
@require_token
def get_energy_dashboard():
    """Get energy advisor dashboard."""
    if not _energy_advisor:
        return jsonify({"error": "Energy advisor not initialized"}), 503
    dashboard = _energy_advisor.get_dashboard()
    return jsonify({"ok": True, **asdict(dashboard)})


@hub_bp.route("/energy/devices", methods=["POST"])
@require_token
def register_energy_device():
    """Register a device for energy tracking.

    JSON body: {"entity_id": "...", "name": "...", "category"?: "other"}
    """
    if not _energy_advisor:
        return jsonify({"error": "Energy advisor not initialized"}), 503
    body = request.get_json(silent=True) or {}
    device = _energy_advisor.register_device(
        body.get("entity_id", ""),
        body.get("name", ""),
        body.get("category", "other"),
    )
    return jsonify({"ok": True, "entity_id": device.entity_id, "category": device.category})


@hub_bp.route("/energy/consumption", methods=["POST"])
@require_token
def update_energy_consumption():
    """Update daily consumption for a device.

    JSON body: {"entity_id": "...", "daily_kwh": ...}
    """
    if not _energy_advisor:
        return jsonify({"error": "Energy advisor not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _energy_advisor.update_consumption(
        body.get("entity_id", ""),
        float(body.get("daily_kwh", 0)),
    )
    return jsonify({"ok": result})


@hub_bp.route("/energy/breakdown", methods=["GET"])
@require_token
def get_energy_breakdown():
    """Get consumption breakdown by category."""
    if not _energy_advisor:
        return jsonify({"error": "Energy advisor not initialized"}), 503
    breakdown = _energy_advisor.get_breakdown()
    return jsonify({
        "ok": True,
        "breakdown": [asdict(b) for b in breakdown],
    })


@hub_bp.route("/energy/top", methods=["GET"])
@require_token
def get_top_energy_consumers():
    """Get top energy consuming devices."""
    if not _energy_advisor:
        return jsonify({"error": "Energy advisor not initialized"}), 503
    limit = int(request.args.get("limit", 10))
    return jsonify({"ok": True, "consumers": _energy_advisor.get_top_consumers(limit)})


@hub_bp.route("/energy/recommendations", methods=["GET"])
@require_token
def get_energy_recommendations():
    """Get savings recommendations.

    Query params: category, limit
    """
    if not _energy_advisor:
        return jsonify({"error": "Energy advisor not initialized"}), 503
    category = request.args.get("category")
    limit = int(request.args.get("limit", 10))
    recs = _energy_advisor.get_recommendations(category, limit)
    return jsonify({"ok": True, "recommendations": recs})


@hub_bp.route("/energy/recommendations/<rec_id>/apply", methods=["POST"])
@require_token
def apply_energy_recommendation(rec_id):
    """Mark a recommendation as applied."""
    if not _energy_advisor:
        return jsonify({"error": "Energy advisor not initialized"}), 503
    result = _energy_advisor.mark_recommendation_applied(rec_id)
    return jsonify({"ok": result, "rec_id": rec_id})


@hub_bp.route("/energy/eco-score", methods=["GET"])
@require_token
def get_eco_score():
    """Get household eco-score."""
    if not _energy_advisor:
        return jsonify({"error": "Energy advisor not initialized"}), 503
    eco = _energy_advisor.calculate_eco_score()
    return jsonify({"ok": True, **asdict(eco)})


@hub_bp.route("/energy/price", methods=["POST"])
@require_token
def set_energy_price():
    """Set electricity price.

    JSON body: {"ct_kwh": 30.0}
    """
    if not _energy_advisor:
        return jsonify({"error": "Energy advisor not initialized"}), 503
    body = request.get_json(silent=True) or {}
    _energy_advisor.set_electricity_price(float(body.get("ct_kwh", 30.0)))
    return jsonify({"ok": True})


# ── Automation Templates endpoints (v6.9.0) ────────────────────────────────


@hub_bp.route("/templates", methods=["GET"])
@require_token
def get_automation_templates():
    """Get automation templates.

    Query params: category, difficulty, search, limit
    """
    if not _template_engine:
        return jsonify({"error": "Template engine not initialized"}), 503
    category = request.args.get("category")
    difficulty = request.args.get("difficulty")
    search = request.args.get("search")
    limit = int(request.args.get("limit", 50))
    templates = _template_engine.get_templates(category, difficulty, search, limit)
    return jsonify({"ok": True, "templates": templates})


@hub_bp.route("/templates/<template_id>", methods=["GET"])
@require_token
def get_template_detail(template_id):
    """Get full template details."""
    if not _template_engine:
        return jsonify({"error": "Template engine not initialized"}), 503
    detail = _template_engine.get_template_detail(template_id)
    if not detail:
        return jsonify({"ok": False, "error": "Template not found"}), 404
    return jsonify({"ok": True, **detail})


@hub_bp.route("/templates/categories", methods=["GET"])
@require_token
def get_template_categories():
    """Get template categories with counts."""
    if not _template_engine:
        return jsonify({"error": "Template engine not initialized"}), 503
    return jsonify({"ok": True, "categories": _template_engine.get_categories()})


@hub_bp.route("/templates/summary", methods=["GET"])
@require_token
def get_template_summary():
    """Get template summary."""
    if not _template_engine:
        return jsonify({"error": "Template engine not initialized"}), 503
    summary = _template_engine.get_summary()
    return jsonify({"ok": True, **asdict(summary)})


@hub_bp.route("/templates/generate", methods=["POST"])
@require_token
def generate_automation():
    """Generate an automation from a template.

    JSON body: {"template_id": "...", "variables": {"key": "value"}, "name"?: "..."}
    """
    if not _template_engine:
        return jsonify({"error": "Template engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    gen = _template_engine.generate_automation(
        body.get("template_id", ""),
        body.get("variables", {}),
        body.get("name", ""),
    )
    if not gen:
        return jsonify({"ok": False, "error": "Generation failed"}), 400
    return jsonify({
        "ok": True,
        "automation_id": gen.automation_id,
        "name": gen.name,
        "yaml_preview": gen.yaml_preview,
    })


@hub_bp.route("/templates/<template_id>/rate", methods=["POST"])
@require_token
def rate_template(template_id):
    """Rate a template.

    JSON body: {"rating": 4.5}
    """
    if not _template_engine:
        return jsonify({"error": "Template engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _template_engine.rate_template(template_id, float(body.get("rating", 0)))
    return jsonify({"ok": result})


@hub_bp.route("/templates/custom", methods=["POST"])
@require_token
def register_custom_template():
    """Register a custom template.

    JSON body: {"template_id": "...", "name_de": "...", "description_de": "...", ...}
    """
    if not _template_engine:
        return jsonify({"error": "Template engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    template_id = body.pop("template_id", "")
    name_de = body.pop("name_de", "")
    description_de = body.pop("description_de", "")
    category = body.pop("category", "comfort")
    result = _template_engine.register_template(template_id, name_de, description_de, category, **body)
    return jsonify({"ok": result, "template_id": template_id})


# ── Scene Intelligence + PilotSuite Cloud endpoints (v7.0.0) ────────────────


@hub_bp.route("/scenes", methods=["GET"])
@require_token
def get_scene_dashboard():
    """Get scene intelligence dashboard."""
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    dashboard = _scene_engine.get_dashboard()
    return jsonify({"ok": True, **asdict(dashboard)})


@hub_bp.route("/scenes/list", methods=["GET"])
@require_token
def get_scenes_list():
    """Get all scenes with optional category filter.

    Query params: category, limit
    """
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    category = request.args.get("category")
    limit = int(request.args.get("limit", 50))
    scenes = _scene_engine.get_scenes(category, limit)
    return jsonify({"ok": True, "scenes": scenes})


@hub_bp.route("/scenes/active", methods=["GET"])
@require_token
def get_active_scene():
    """Get the currently active scene."""
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    active = _scene_engine.get_active_scene()
    return jsonify({"ok": True, "active_scene": active})


@hub_bp.route("/scenes/activate", methods=["POST"])
@require_token
def activate_scene():
    """Activate a scene.

    JSON body: {"scene_id": "...", "zone_id"?: "..."}
    """
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _scene_engine.activate_scene(
        body.get("scene_id", ""),
        body.get("zone_id", ""),
    )
    return jsonify({"ok": result, "scene_id": body.get("scene_id")})


@hub_bp.route("/scenes/deactivate", methods=["POST"])
@require_token
def deactivate_scene():
    """Deactivate the current scene."""
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    result = _scene_engine.deactivate_scene()
    return jsonify({"ok": result})


@hub_bp.route("/scenes/suggest", methods=["POST"])
@require_token
def suggest_scenes():
    """Get scene suggestions based on context.

    JSON body (optional): {"hour": 20, "is_home": true, "occupancy_count": 2,
                           "outdoor_lux": 50, "indoor_temp_c": 21, "is_weekend": false,
                           "active_zone": "..."}
    """
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    from copilot_core.hub.scene_intelligence import SceneContext
    ctx = None
    if body:
        ctx = SceneContext(
            hour=body.get("hour", 12),
            is_home=body.get("is_home", True),
            occupancy_count=body.get("occupancy_count", 1),
            outdoor_lux=body.get("outdoor_lux", 500.0),
            indoor_temp_c=body.get("indoor_temp_c", 21.0),
            is_weekend=body.get("is_weekend", False),
            active_zone=body.get("active_zone", ""),
        )
    limit = body.get("limit", 3) if body else 3
    suggestions = _scene_engine.suggest_scenes(ctx, limit)
    return jsonify({
        "ok": True,
        "suggestions": [asdict(s) for s in suggestions],
    })


@hub_bp.route("/scenes/learn", methods=["POST"])
@require_token
def learn_scene_patterns():
    """Trigger pattern learning from activation history."""
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    new_patterns = _scene_engine.learn_patterns()
    return jsonify({"ok": True, "new_patterns": new_patterns})


@hub_bp.route("/scenes/cloud", methods=["POST"])
@require_token
def configure_scene_cloud():
    """Configure PilotSuite Cloud connection.

    JSON body: {"cloud_url": "https://...", "sync_interval_min"?: 15}
    """
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    status = _scene_engine.configure_cloud(
        body.get("cloud_url", ""),
        body.get("sync_interval_min", 15),
    )
    return jsonify({"ok": True, **asdict(status)})


@hub_bp.route("/scenes/cloud/status", methods=["GET"])
@require_token
def get_scene_cloud_status():
    """Get PilotSuite Cloud status."""
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    return jsonify({"ok": True, **_scene_engine.get_cloud_status()})


@hub_bp.route("/scenes/cloud/share", methods=["POST"])
@require_token
def share_scene_to_cloud():
    """Share a scene to PilotSuite Cloud.

    JSON body: {"scene_id": "..."}
    """
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _scene_engine.share_scene(body.get("scene_id", ""))
    return jsonify({"ok": result})


@hub_bp.route("/scenes/<scene_id>/rate", methods=["POST"])
@require_token
def rate_scene(scene_id):
    """Rate a scene.

    JSON body: {"rating": 4.5}
    """
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _scene_engine.rate_scene(scene_id, float(body.get("rating", 0)))
    return jsonify({"ok": result})


@hub_bp.route("/scenes/custom", methods=["POST"])
@require_token
def register_custom_scene():
    """Register a custom scene.

    JSON body: {"scene_id": "...", "name_de": "...", "name_en"?: "...", "icon"?: "...", ...}
    """
    if not _scene_engine:
        return jsonify({"error": "Scene engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    scene_id = body.pop("scene_id", "")
    name_de = body.pop("name_de", "")
    name_en = body.pop("name_en", "")
    icon = body.pop("icon", "mdi:palette")
    result = _scene_engine.register_scene(scene_id, name_de, name_en, icon, **body)
    return jsonify({"ok": result, "scene_id": scene_id})


# ── Presence Intelligence endpoints (v7.1.0) ────────────────────────────────


@hub_bp.route("/presence", methods=["GET"])
@require_token
def get_presence_dashboard():
    """Get presence intelligence dashboard."""
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    dashboard = _presence_engine.get_dashboard()
    return jsonify({"ok": True, **asdict(dashboard)})


@hub_bp.route("/presence/persons", methods=["POST"])
@require_token
def register_presence_person():
    """Register a person for presence tracking.

    JSON body: {"person_id": "...", "name": "...", "icon"?: "mdi:account"}
    """
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    person = _presence_engine.register_person(
        body.get("person_id", ""),
        body.get("name", ""),
        body.get("icon", "mdi:account"),
    )
    return jsonify({"ok": True, "person_id": person.person_id, "name": person.name})


@hub_bp.route("/presence/persons/<person_id>", methods=["GET"])
@require_token
def get_presence_person(person_id):
    """Get person presence details."""
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    p = _presence_engine.get_person(person_id)
    if not p:
        return jsonify({"ok": False, "error": "Person not found"}), 404
    return jsonify({"ok": True, **p})


@hub_bp.route("/presence/persons/<person_id>", methods=["DELETE"])
@require_token
def unregister_presence_person(person_id):
    """Unregister a person from tracking."""
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    result = _presence_engine.unregister_person(person_id)
    return jsonify({"ok": result})


@hub_bp.route("/presence/rooms", methods=["GET"])
@require_token
def get_presence_rooms():
    """Get all rooms with occupancy info."""
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    return jsonify({"ok": True, "rooms": _presence_engine.get_rooms()})


@hub_bp.route("/presence/rooms", methods=["POST"])
@require_token
def register_presence_room():
    """Register a room for presence tracking.

    JSON body: {"room_id": "...", "room_name"?: "..."}
    """
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _presence_engine.register_room(
        body.get("room_id", ""),
        body.get("room_name", ""),
    )
    return jsonify({"ok": result})


@hub_bp.route("/presence/update", methods=["POST"])
@require_token
def update_person_presence():
    """Update a person's presence state.

    JSON body: {"person_id": "...", "room_id"?: "...", "zone_id"?: "...", "is_home"?: true}
    """
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _presence_engine.update_presence(
        body.get("person_id", ""),
        body.get("room_id", ""),
        body.get("zone_id", ""),
        body.get("is_home", True),
    )
    return jsonify({"ok": result})


@hub_bp.route("/presence/household", methods=["GET"])
@require_token
def get_household_presence():
    """Get household-level presence status."""
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    return jsonify({"ok": True, **_presence_engine.get_household_status()})


@hub_bp.route("/presence/transitions", methods=["GET"])
@require_token
def get_presence_transitions():
    """Get recent room transitions.

    Query params: limit
    """
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    limit = int(request.args.get("limit", 20))
    return jsonify({"ok": True, "transitions": _presence_engine.get_transitions(limit)})


@hub_bp.route("/presence/room/<room_id>/occupancy", methods=["GET"])
@require_token
def get_room_occupancy(room_id):
    """Get occupancy stats for a room."""
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    occ = _presence_engine.get_room_occupancy(room_id)
    return jsonify({"ok": True, **asdict(occ)})


@hub_bp.route("/presence/heatmap", methods=["GET"])
@require_token
def get_presence_heatmap():
    """Get occupancy heatmap.

    Query params: hours (default 24)
    """
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    hours = int(request.args.get("hours", 24))
    heatmap = _presence_engine.get_heatmap(hours)
    return jsonify({"ok": True, "heatmap": [asdict(h) for h in heatmap]})


@hub_bp.route("/presence/triggers", methods=["GET"])
@require_token
def get_presence_triggers():
    """Get all presence triggers."""
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    return jsonify({"ok": True, "triggers": _presence_engine.get_triggers()})


@hub_bp.route("/presence/triggers", methods=["POST"])
@require_token
def register_presence_trigger():
    """Register a presence trigger.

    JSON body: {"trigger_id": "...", "trigger_type": "arrival|departure|idle|room_enter|room_leave",
                "person_id"?: "...", "room_id"?: "...", "idle_threshold_min"?: 30}
    """
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _presence_engine.register_trigger(
        body.get("trigger_id", ""),
        body.get("trigger_type", ""),
        body.get("person_id", ""),
        body.get("room_id", ""),
        body.get("zone_id", ""),
        body.get("idle_threshold_min", 30),
    )
    return jsonify({"ok": result})


@hub_bp.route("/presence/triggers/<trigger_id>", methods=["DELETE"])
@require_token
def unregister_presence_trigger(trigger_id):
    """Remove a presence trigger."""
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    result = _presence_engine.unregister_trigger(trigger_id)
    return jsonify({"ok": result})


@hub_bp.route("/presence/idle", methods=["POST"])
@require_token
def check_presence_idle():
    """Check idle triggers (call periodically)."""
    if not _presence_engine:
        return jsonify({"error": "Presence engine not initialized"}), 503
    fired = _presence_engine.check_idle_triggers()
    return jsonify({"ok": True, "fired": fired})


# ── Notification Intelligence endpoints (v7.2.0) ────────────────────────────


@hub_bp.route("/notifications", methods=["GET"])
@require_token
def get_notification_dashboard():
    """Get notification intelligence dashboard."""
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    dashboard = _notification_engine.get_dashboard()
    return jsonify({"ok": True, **asdict(dashboard)})


@hub_bp.route("/notifications/send", methods=["POST"])
@require_token
def send_notification():
    """Send a notification.

    JSON body: {"title": "...", "message": "...", "priority"?: "normal",
                "channel"?: "push", "category"?: "general",
                "person_id"?: "...", "zone_id"?: "...", "icon"?: "mdi:bell"}
    """
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    n = _notification_engine.send(
        title=body.get("title", ""),
        message=body.get("message", ""),
        priority=body.get("priority", "normal"),
        channel=body.get("channel", "push"),
        category=body.get("category", "general"),
        person_id=body.get("person_id", ""),
        zone_id=body.get("zone_id", ""),
        icon=body.get("icon", "mdi:bell"),
    )
    return jsonify({
        "ok": True,
        "notification_id": n.notification_id,
        "delivered": n.delivered,
        "suppressed": n.suppressed,
        "batched": n.batched,
    })


@hub_bp.route("/notifications/history", methods=["GET"])
@require_token
def get_notification_history():
    """Get notification history.

    Query params: limit, unread_only, category
    """
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    limit = int(request.args.get("limit", 50))
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    category = request.args.get("category", "")
    history = _notification_engine.get_history(limit, unread_only, category)
    return jsonify({"ok": True, "notifications": history})


@hub_bp.route("/notifications/<notification_id>/read", methods=["POST"])
@require_token
def mark_notification_read(notification_id):
    """Mark a notification as read."""
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    result = _notification_engine.mark_read(notification_id)
    return jsonify({"ok": result})


@hub_bp.route("/notifications/read-all", methods=["POST"])
@require_token
def mark_all_notifications_read():
    """Mark all notifications as read."""
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    count = _notification_engine.mark_all_read()
    return jsonify({"ok": True, "marked": count})


@hub_bp.route("/notifications/dnd", methods=["POST"])
@require_token
def set_notification_dnd():
    """Set Do-Not-Disturb.

    JSON body: {"enabled": true, "person_id"?: "...", "allow_critical"?: true,
                "duration_min"?: 0, "zone_mode"?: "..."}
    """
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    dnd = _notification_engine.set_dnd(
        enabled=body.get("enabled", True),
        person_id=body.get("person_id", ""),
        allow_critical=body.get("allow_critical", True),
        duration_min=body.get("duration_min", 0),
        zone_mode=body.get("zone_mode", ""),
    )
    return jsonify({
        "ok": True,
        "enabled": dnd.enabled,
        "until": dnd.until.isoformat() if dnd.until else None,
    })


@hub_bp.route("/notifications/dnd/status", methods=["GET"])
@require_token
def get_notification_dnd_status():
    """Get DND status."""
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    return jsonify({"ok": True, "dnd": _notification_engine.get_dnd_status()})


@hub_bp.route("/notifications/rules", methods=["GET"])
@require_token
def get_notification_rules():
    """Get notification routing rules."""
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    return jsonify({"ok": True, "rules": _notification_engine.get_rules()})


@hub_bp.route("/notifications/rules", methods=["POST"])
@require_token
def add_notification_rule():
    """Add a notification routing rule.

    JSON body: {"rule_id": "...", "name_de": "...", "category"?: "...",
                "priority_min"?: "low", "channel"?: "push",
                "quiet_hours_start"?: null, "quiet_hours_end"?: null}
    """
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _notification_engine.add_rule(
        body.get("rule_id", ""),
        body.get("name_de", ""),
        body.get("category", ""),
        body.get("priority_min", "low"),
        body.get("channel", "push"),
        body.get("person_id", ""),
        body.get("zone_id", ""),
        body.get("quiet_hours_start"),
        body.get("quiet_hours_end"),
    )
    return jsonify({"ok": result})


@hub_bp.route("/notifications/rules/<rule_id>", methods=["DELETE"])
@require_token
def remove_notification_rule(rule_id):
    """Remove a routing rule."""
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    result = _notification_engine.remove_rule(rule_id)
    return jsonify({"ok": result})


@hub_bp.route("/notifications/batch", methods=["POST"])
@require_token
def configure_notification_batch():
    """Configure notification batching.

    JSON body: {"enabled": true, "interval_min"?: 15, "max_batch_size"?: 10,
                "categories"?: [...]}
    """
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    body = request.get_json(silent=True) or {}
    cfg = _notification_engine.configure_batching(
        enabled=body.get("enabled", False),
        interval_min=body.get("interval_min", 15),
        max_batch_size=body.get("max_batch_size", 10),
        categories=body.get("categories"),
    )
    return jsonify({"ok": True, "enabled": cfg.enabled, "interval_min": cfg.interval_min})


@hub_bp.route("/notifications/batch/flush", methods=["POST"])
@require_token
def flush_notification_batch():
    """Flush batched notifications."""
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    delivered = _notification_engine.flush_batch()
    return jsonify({"ok": True, "delivered": len(delivered)})


@hub_bp.route("/notifications/stats", methods=["GET"])
@require_token
def get_notification_stats():
    """Get notification statistics."""
    if not _notification_engine:
        return jsonify({"error": "Notification engine not initialized"}), 503
    stats = _notification_engine.get_stats()
    return jsonify({"ok": True, **asdict(stats)})


# ── System Integration Hub ────────────────────────────────────────────────


@hub_bp.route("/integration", methods=["GET"])
@require_token
def get_integration_dashboard():
    """Get system integration hub dashboard."""
    if not _integration_hub:
        return jsonify({"error": "Integration hub not initialized"}), 503
    status = _integration_hub.get_status()
    wiring = _integration_hub.get_wiring_diagram()
    return jsonify({
        "ok": True,
        **asdict(status),
        "wiring_diagram": wiring,
    })


@hub_bp.route("/integration/status", methods=["GET"])
@require_token
def get_integration_status():
    """Get integration hub status."""
    if not _integration_hub:
        return jsonify({"error": "Integration hub not initialized"}), 503
    status = _integration_hub.get_status()
    return jsonify({"ok": True, **asdict(status)})


@hub_bp.route("/integration/wiring", methods=["GET"])
@require_token
def get_integration_wiring():
    """Get the wiring diagram (event → subscriber mappings)."""
    if not _integration_hub:
        return jsonify({"error": "Integration hub not initialized"}), 503
    diagram = _integration_hub.get_wiring_diagram()
    return jsonify({"ok": True, "wiring": diagram})


@hub_bp.route("/integration/dispatch", methods=["POST"])
@require_token
def dispatch_integration_event():
    """Dispatch an event through the integration hub.

    JSON body: {"event_type": "...", "source": "...", "data"?: {...}}
    """
    if not _integration_hub:
        return jsonify({"error": "Integration hub not initialized"}), 503
    body = request.get_json(silent=True) or {}
    event_type = body.get("event_type", "")
    source = body.get("source", "api")
    data = body.get("data", {})
    if not event_type:
        return jsonify({"error": "event_type required"}), 400
    event = _integration_hub.dispatch(event_type, source, data)
    return jsonify({
        "ok": True,
        "event_type": event.event_type,
        "handled_by": event.handled_by,
        "timestamp": event.timestamp.isoformat(),
    })


@hub_bp.route("/integration/auto-wire", methods=["POST"])
@require_token
def auto_wire_integration():
    """Re-run auto-wiring for all registered engines."""
    if not _integration_hub:
        return jsonify({"error": "Integration hub not initialized"}), 503
    count = _integration_hub.auto_wire()
    return jsonify({"ok": True, "subscriptions_created": count})


# ── Brain Architecture ─────────────────────────────────────────────────────


@hub_bp.route("/brain", methods=["GET"])
@require_token
def get_brain_dashboard():
    """Get full brain architecture dashboard."""
    if not _brain_architecture:
        return jsonify({"error": "Brain architecture not initialized"}), 503
    return jsonify(_brain_architecture.get_dashboard())


@hub_bp.route("/brain/graph", methods=["GET"])
@require_token
def get_brain_graph():
    """Get brain graph data (nodes + edges) for visualization."""
    if not _brain_architecture:
        return jsonify({"error": "Brain architecture not initialized"}), 503
    return jsonify({"ok": True, **_brain_architecture.get_graph_data()})


@hub_bp.route("/brain/regions", methods=["GET"])
@require_token
def get_brain_regions():
    """Get all brain regions."""
    if not _brain_architecture:
        return jsonify({"error": "Brain architecture not initialized"}), 503
    regions = _brain_architecture.get_all_regions()
    return jsonify({
        "ok": True,
        "regions": [
            {
                "region_id": r.region_id,
                "name_de": r.name_de,
                "name_en": r.name_en,
                "color": r.color,
                "icon": r.icon,
                "role": r.role,
                "engine_key": r.engine_key,
                "active": r.is_active,
                "health": r.health,
            }
            for r in regions
        ],
    })


@hub_bp.route("/brain/regions/<region_id>", methods=["GET"])
@require_token
def get_brain_region(region_id):
    """Get a specific brain region."""
    if not _brain_architecture:
        return jsonify({"error": "Brain architecture not initialized"}), 503
    r = _brain_architecture.get_region(region_id)
    if not r:
        return jsonify({"error": f"Region '{region_id}' not found"}), 404
    neurons = _brain_architecture.get_neurons_for_region(region_id)
    outgoing = _brain_architecture.get_synapses_from(region_id)
    incoming = _brain_architecture.get_synapses_to(region_id)
    return jsonify({
        "ok": True,
        "region_id": r.region_id,
        "name_de": r.name_de,
        "name_en": r.name_en,
        "color": r.color,
        "icon": r.icon,
        "role": r.role,
        "engine_key": r.engine_key,
        "active": r.is_active,
        "health": r.health,
        "description_de": r.description_de,
        "neurons": [{"neuron_id": n.neuron_id, "sensor_class": n.sensor_class, "state": n.state} for n in neurons],
        "outgoing_synapses": [{"synapse_id": s.synapse_id, "target": s.target_region, "event": s.event_type, "state": s.state} for s in outgoing],
        "incoming_synapses": [{"synapse_id": s.synapse_id, "source": s.source_region, "event": s.event_type, "state": s.state} for s in incoming],
    })


@hub_bp.route("/brain/synapses", methods=["GET"])
@require_token
def get_brain_synapses():
    """Get all synapses."""
    if not _brain_architecture:
        return jsonify({"error": "Brain architecture not initialized"}), 503
    synapses = _brain_architecture.get_all_synapses()
    return jsonify({
        "ok": True,
        "synapses": [
            {
                "synapse_id": s.synapse_id,
                "source": s.source_region,
                "target": s.target_region,
                "event_type": s.event_type,
                "state": s.state,
                "strength": s.strength,
                "fire_count": s.fire_count,
                "description_de": s.description_de,
            }
            for s in synapses
        ],
    })


@hub_bp.route("/brain/synapses", methods=["POST"])
@require_token
def add_brain_synapse():
    """Add a custom synapse.

    JSON body: {"source": "region_id", "target": "region_id",
                "event_type": "...", "description_de"?: "..."}
    """
    if not _brain_architecture:
        return jsonify({"error": "Brain architecture not initialized"}), 503
    body = request.get_json(silent=True) or {}
    s = _brain_architecture.add_synapse(
        body.get("source", ""),
        body.get("target", ""),
        body.get("event_type", ""),
        body.get("description_de", ""),
    )
    if not s:
        return jsonify({"error": "Invalid source or target region"}), 400
    return jsonify({"ok": True, "synapse_id": s.synapse_id})


@hub_bp.route("/brain/synapses/<synapse_id>", methods=["DELETE"])
@require_token
def remove_brain_synapse(synapse_id):
    """Remove a synapse."""
    if not _brain_architecture:
        return jsonify({"error": "Brain architecture not initialized"}), 503
    result = _brain_architecture.remove_synapse(synapse_id)
    return jsonify({"ok": result})


@hub_bp.route("/brain/synapses/<synapse_id>/state", methods=["POST"])
@require_token
def set_brain_synapse_state(synapse_id):
    """Set synapse state (active, dormant, pending, blocked).

    JSON body: {"state": "active"}
    """
    if not _brain_architecture:
        return jsonify({"error": "Brain architecture not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = _brain_architecture.set_synapse_state(synapse_id, body.get("state", "active"))
    return jsonify({"ok": result})


@hub_bp.route("/brain/synapses/<synapse_id>/fire", methods=["POST"])
@require_token
def fire_brain_synapse(synapse_id):
    """Fire a synapse (record event dispatch)."""
    if not _brain_architecture:
        return jsonify({"error": "Brain architecture not initialized"}), 503
    result = _brain_architecture.fire_synapse(synapse_id)
    return jsonify({"ok": result})


@hub_bp.route("/brain/sync", methods=["POST"])
@require_token
def sync_brain_with_hub():
    """Sync brain architecture with SystemIntegrationHub."""
    if not _brain_architecture:
        return jsonify({"error": "Brain architecture not initialized"}), 503
    if not _integration_hub:
        return jsonify({"error": "Integration hub not initialized"}), 503
    result = _brain_architecture.sync_with_hub(_integration_hub)
    return jsonify({"ok": True, **result})


# ── Brain Activity ─────────────────────────────────────────────────────────


@hub_bp.route("/brain/activity", methods=["GET"])
@require_token
def get_brain_activity():
    """Get brain activity dashboard (state, pulses, chat)."""
    if not _brain_activity:
        return jsonify({"error": "Brain activity not initialized"}), 503
    return jsonify(_brain_activity.get_dashboard())


@hub_bp.route("/brain/activity/state", methods=["GET"])
@require_token
def get_brain_state():
    """Get current brain state (active/idle/sleeping)."""
    if not _brain_activity:
        return jsonify({"error": "Brain activity not initialized"}), 503
    return jsonify({"ok": True, "state": _brain_activity.state.value})


@hub_bp.route("/brain/activity/wake", methods=["POST"])
@require_token
def wake_brain():
    """Wake the brain from sleep."""
    if not _brain_activity:
        return jsonify({"error": "Brain activity not initialized"}), 503
    state = _brain_activity.wake()
    return jsonify({"ok": True, "state": state})


@hub_bp.route("/brain/activity/sleep", methods=["POST"])
@require_token
def sleep_brain():
    """Put the brain to sleep."""
    if not _brain_activity:
        return jsonify({"error": "Brain activity not initialized"}), 503
    state = _brain_activity.sleep()
    return jsonify({"ok": True, "state": state})


@hub_bp.route("/brain/activity/pulse", methods=["POST"])
@require_token
def start_brain_pulse():
    """Start a brain pulse (mark as active).

    JSON body: {"reason"?: "chat"}
    """
    if not _brain_activity:
        return jsonify({"error": "Brain activity not initialized"}), 503
    body = request.get_json(silent=True) or {}
    pulse = _brain_activity.start_pulse(body.get("reason", "api_request"))
    return jsonify({"ok": True, "pulse_id": pulse.pulse_id, "state": "active"})


@hub_bp.route("/brain/activity/pulse/end", methods=["POST"])
@require_token
def end_brain_pulse():
    """End the current brain pulse (return to idle)."""
    if not _brain_activity:
        return jsonify({"error": "Brain activity not initialized"}), 503
    pulse = _brain_activity.end_pulse()
    if not pulse:
        return jsonify({"ok": False, "error": "No active pulse"})
    return jsonify({"ok": True, "pulse_id": pulse.pulse_id, "duration_ms": pulse.duration_ms})


@hub_bp.route("/brain/activity/chat", methods=["GET"])
@require_token
def get_brain_chat():
    """Get chat history."""
    if not _brain_activity:
        return jsonify({"error": "Brain activity not initialized"}), 503
    limit = request.args.get("limit", 50, type=int)
    messages = _brain_activity.get_chat_history(limit)
    return jsonify({
        "ok": True,
        "messages": [
            {
                "message_id": m.message_id,
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
                "metadata": m.metadata,
            }
            for m in messages
        ],
    })


@hub_bp.route("/brain/activity/chat", methods=["POST"])
@require_token
def add_brain_chat():
    """Add a chat message.

    JSON body: {"role": "user"|"assistant", "content": "...", "metadata"?: {...}}
    """
    if not _brain_activity:
        return jsonify({"error": "Brain activity not initialized"}), 503
    body = request.get_json(silent=True) or {}
    role = body.get("role", "user")
    content = body.get("content", "")
    if not content:
        return jsonify({"error": "content required"}), 400
    msg = _brain_activity.add_chat_message(role, content, body.get("metadata"))
    return jsonify({"ok": True, "message_id": msg.message_id, "state": _brain_activity.state.value})


@hub_bp.route("/brain/activity/chat/clear", methods=["POST"])
@require_token
def clear_brain_chat():
    """Clear chat history."""
    if not _brain_activity:
        return jsonify({"error": "Brain activity not initialized"}), 503
    count = _brain_activity.clear_chat_history()
    return jsonify({"ok": True, "cleared": count})


@hub_bp.route("/brain/activity/config", methods=["POST"])
@require_token
def configure_brain_activity():
    """Configure activity timeouts.

    JSON body: {"idle_timeout"?: 300, "sleep_timeout"?: 1800}
    """
    if not _brain_activity:
        return jsonify({"error": "Brain activity not initialized"}), 503
    body = request.get_json(silent=True) or {}
    result = {}
    if "idle_timeout" in body:
        result["idle_timeout"] = _brain_activity.set_idle_timeout(body["idle_timeout"])
    if "sleep_timeout" in body:
        result["sleep_timeout"] = _brain_activity.set_sleep_timeout(body["sleep_timeout"])
    return jsonify({"ok": True, **result})
