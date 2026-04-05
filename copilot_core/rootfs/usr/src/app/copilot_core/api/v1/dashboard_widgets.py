"""Dashboard Widgets API — Slice 175 Expansion.

New widgets: floorplan, area_tree, service_actions, entity_grid
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from datetime import datetime, timezone

bp = Blueprint("dashboard_widgets", __name__, url_prefix="/api/v1/dashboard/widgets")


# ── Floorplan Widget ─────────────────────────────────

@bp.get("/floorplan/config")
def widget_floorplan_config():
    """Get floorplan widget configuration."""
    return jsonify({
        "ok": True,
        "widget_type": "floorplan",
        "config": {
            "floorplan_id": None,
            "show_zones": True,
            "show_entities": True,
            "clickable": True,
            "refresh_interval": 5
        }
    })


@bp.get("/floorplan/data")
def widget_floorplan_data():
    """Get floorplan widget data with live entity states."""
    floorplan_id = request.args.get("floorplan_id")
    
    if not floorplan_id:
        return jsonify({"ok": False, "error": "Missing floorplan_id"}), 400
    
    from copilot_core.floorplan.manager import get_floorplan_manager
    
    try:
        manager = get_floorplan_manager()
        data = manager.get_widget_data(floorplan_id=floorplan_id)
    except Exception as e:
        data = {"zones": [], "entities": [], "image_url": None}
    
    return jsonify({
        "ok": True,
        "floorplan_id": floorplan_id,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ── Area Tree Widget ─────────────────────────────────

@bp.get("/area_tree/config")
def widget_area_tree_config():
    """Get area tree widget configuration."""
    return jsonify({
        "ok": True,
        "widget_type": "area_tree",
        "config": {
            "root_area_id": None,
            "show_devices": True,
            "show_entities": True,
            "expand_depth": 2
        }
    })


@bp.get("/area_tree/data")
def widget_area_tree_data():
    """Get hierarchical area tree with counts."""
    root_id = request.args.get("root_area_id")
    
    from copilot_core.areas.manager import get_areas_manager
    
    try:
        manager = get_areas_manager()
        tree = manager.get_widget_tree(root_id=root_id)
    except Exception as e:
        tree = []
    
    return jsonify({
        "ok": True,
        "root_area_id": root_id,
        "tree": tree,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ── Service Actions Widget ─────────────────────────────────

@bp.get("/service_actions/config")
def widget_service_actions_config():
    """Get service quick actions widget config."""
    return jsonify({
        "ok": True,
        "widget_type": "service_actions",
        "config": {
            "buttons": [],
            "layout": "grid",
            "columns": 3
        }
    })


@bp.post("/service_actions/execute")
def widget_service_actions_execute():
    """Execute a service action from widget."""
    data = request.get_json() or {}
    service = data.get("service")
    target = data.get("target")
    
    if not service:
        return jsonify({"ok": False, "error": "Missing service"}), 400
    
    from copilot_core.services.manager import get_services_manager
    
    try:
        manager = get_services_manager()
        result = manager.call_service(service=service, target=target)
        success = result.get("success", False)
    except Exception as e:
        success = False
    
    return jsonify({"ok": success, "service": service})


# ── Entity Grid Widget ─────────────────────────────────

@bp.get("/entity_grid/config")
def widget_entity_grid_config():
    """Get entity grid widget configuration."""
    return jsonify({
        "ok": True,
        "widget_type": "entity_grid",
        "config": {
            "entity_ids": [],
            "columns": 4,
            "show_state": True,
            "show_icon": True
        }
    })


@bp.get("/entity_grid/data")
def widget_entity_grid_data():
    """Get entity grid data with live states."""
    entity_ids = request.args.get("entity_ids", "").split(",")
    entity_ids = [e.strip() for e in entity_ids if e.strip()]
    
    if not entity_ids:
        return jsonify({"ok": False, "error": "Missing entity_ids"}), 400
    
    from copilot_core.entities.manager import get_entities_manager
    
    try:
        manager = get_entities_manager()
        states = manager.get_states(entity_ids=entity_ids)
    except Exception as e:
        states = []
    
    return jsonify({
        "ok": True,
        "entities": states,
        "count": len(states),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
