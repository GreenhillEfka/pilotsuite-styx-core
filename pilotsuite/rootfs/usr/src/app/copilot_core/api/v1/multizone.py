"""Multi-zone coordination API endpoints — v15.3.26.

Contract:
- multi-zone scenes and routines are created from explicit zone_action maps,
- proposal/action handoffs remain attached to runtime actions,
- scheduler-bound executions expose real zone/module/service targets.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.multizone.coordination_engine import (
    MultiZoneCoordinationEngine,
    create_multi_zone_coordination_engine,
)

multizone_bp = Blueprint("multizone", __name__, url_prefix="/api/v1/multizone")


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _get_engine() -> MultiZoneCoordinationEngine:
    services = current_app.config.get("COPILOT_SERVICES", {})
    scheduler = None
    if isinstance(services, dict):
        scheduler = services.get("scheduler_engine")
        for key in ("multizone_engine", "multi_zone_coordination_engine"):
            engine = services.get(key)
            if isinstance(engine, MultiZoneCoordinationEngine):
                if scheduler is not None:
                    engine.attach_scheduler(scheduler)
                return engine

    engine = current_app.config.get("COPILOT_MULTIZONE_ENGINE")
    if isinstance(engine, MultiZoneCoordinationEngine):
        if scheduler is not None:
            engine.attach_scheduler(scheduler)
        return engine

    engine = getattr(current_app, "_multizone_engine", None)
    if isinstance(engine, MultiZoneCoordinationEngine):
        if scheduler is not None:
            engine.attach_scheduler(scheduler)
        return engine

    engine = create_multi_zone_coordination_engine(scheduler_engine=scheduler)
    current_app._multizone_engine = engine
    return engine


@multizone_bp.route("/scenes", methods=["GET"])
@require_token
def list_scenes():
    engine = _get_engine()
    active_only = _parse_bool(request.args.get("active_only"))
    scenes = engine.get_scenes()
    if active_only:
        scenes = [scene for scene in scenes if scene.get("is_active")]
    return jsonify({"ok": True, "scenes": scenes, "count": len(scenes)})


@multizone_bp.route("/scenes", methods=["POST"])
@require_token
def create_scene():
    engine = _get_engine()
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    zone_actions = payload.get("zone_actions") if isinstance(payload.get("zone_actions"), dict) else None
    schedule_config = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else None
    proposal_handoff = payload.get("proposal_handoff") if isinstance(payload.get("proposal_handoff"), dict) else None
    action_handoff = payload.get("action_handoff") if isinstance(payload.get("action_handoff"), dict) else None
    if not name or zone_actions is None:
        return jsonify({"ok": False, "error": "name and zone_actions required"}), 400

    scene_id = engine.create_scene(
        name=name,
        description=description,
        zone_actions=zone_actions,
        proposal_handoff=proposal_handoff,
        action_handoff=action_handoff,
        schedule_config=schedule_config,
    )
    scene = next((item for item in engine.get_scenes() if item.get("scene_id") == scene_id), None)
    return jsonify({"ok": True, "scene_id": scene_id, "scene": scene}), 200


@multizone_bp.route("/scenes/<scene_id>/activate", methods=["POST"])
@require_token
def activate_scene(scene_id: str):
    engine = _get_engine()
    payload = request.get_json(silent=True) or {}
    if scene_id not in engine._scenes:
        return jsonify({"ok": False, "error": "scene not found"}), 404

    runtime_source = str(payload.get("runtime_source") or payload.get("source") or "api.manual")
    activated = engine.activate_scene(
        scene_id,
        activated_by=payload.get("activated_by"),
        runtime_source=runtime_source,
        runtime_context=payload,
    )
    status = 200 if activated else 409
    scene = next((item for item in engine.get_scenes() if item.get("scene_id") == scene_id), None)
    return jsonify({
        "ok": activated,
        "scene": scene,
        "pending_actions": engine.get_pending_actions(),
        "conflicts": engine.get_conflicts(unresolved_only=False),
    }), status


@multizone_bp.route("/scenes/<scene_id>/deactivate", methods=["POST"])
@require_token
def deactivate_scene(scene_id: str):
    engine = _get_engine()
    if scene_id not in engine._scenes:
        return jsonify({"ok": False, "error": "scene not found"}), 404
    deactivated = engine.deactivate_scene(scene_id)
    return jsonify({"ok": deactivated, "pending_actions": engine.get_pending_actions()})


@multizone_bp.route("/routines", methods=["GET"])
@require_token
def list_routines():
    engine = _get_engine()
    enabled_only = _parse_bool(request.args.get("enabled_only"))
    routines = engine.get_routines()
    if enabled_only:
        routines = [routine for routine in routines if routine.get("enabled")]
    return jsonify({"ok": True, "routines": routines, "count": len(routines)})


@multizone_bp.route("/routines", methods=["POST"])
@require_token
def create_routine():
    engine = _get_engine()
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    trigger_type = str(payload.get("trigger_type") or "").strip()
    trigger_config = payload.get("trigger_config") if isinstance(payload.get("trigger_config"), dict) else None
    zone_actions = payload.get("zone_actions") if isinstance(payload.get("zone_actions"), dict) else None
    proposal_handoff = payload.get("proposal_handoff") if isinstance(payload.get("proposal_handoff"), dict) else None
    action_handoff = payload.get("action_handoff") if isinstance(payload.get("action_handoff"), dict) else None
    if not name or not trigger_type or trigger_config is None or zone_actions is None:
        return jsonify({"ok": False, "error": "name, trigger_type, trigger_config, and zone_actions required"}), 400

    routine_id = engine.create_routine(
        name=name,
        description=description,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        zone_actions=zone_actions,
        proposal_handoff=proposal_handoff,
        action_handoff=action_handoff,
    )
    routine = next((item for item in engine.get_routines() if item.get("routine_id") == routine_id), None)
    return jsonify({"ok": True, "routine_id": routine_id, "routine": routine}), 200


@multizone_bp.route("/routines/<routine_id>/trigger", methods=["POST"])
@require_token
def trigger_routine(routine_id: str):
    engine = _get_engine()
    payload = request.get_json(silent=True) or {}
    if routine_id not in engine._routines:
        return jsonify({"ok": False, "error": "routine not found"}), 404

    runtime_source = str(payload.get("runtime_source") or payload.get("source") or "api.manual")
    triggered = engine.trigger_routine(
        routine_id,
        runtime_source=runtime_source,
        runtime_context=payload,
    )
    status = 200 if triggered else 409
    routine = next((item for item in engine.get_routines() if item.get("routine_id") == routine_id), None)
    return jsonify({
        "ok": triggered,
        "routine": routine,
        "pending_actions": engine.get_pending_actions(),
        "conflicts": engine.get_conflicts(unresolved_only=False),
    }), status


@multizone_bp.route("/routines/<routine_id>/enable", methods=["POST"])
@require_token
def enable_routine(routine_id: str):
    engine = _get_engine()
    if routine_id not in engine._routines:
        return jsonify({"ok": False, "error": "routine not found"}), 404
    return jsonify({"ok": engine.enable_routine(routine_id)})


@multizone_bp.route("/routines/<routine_id>/disable", methods=["POST"])
@require_token
def disable_routine(routine_id: str):
    engine = _get_engine()
    if routine_id not in engine._routines:
        return jsonify({"ok": False, "error": "routine not found"}), 404
    return jsonify({"ok": engine.disable_routine(routine_id)})


@multizone_bp.route("/pending-actions", methods=["GET"])
@require_token
def get_pending_actions():
    engine = _get_engine()
    zone_id = request.args.get("zone_id")
    module_id = request.args.get("module_id")
    entity_id = request.args.get("entity_id")
    actions = engine.get_pending_actions(zone_id=zone_id, module_id=module_id, entity_id=entity_id)
    return jsonify({"ok": True, "pending_actions": actions, "count": len(actions)})


@multizone_bp.route("/conflicts", methods=["GET"])
@require_token
def get_conflicts():
    engine = _get_engine()
    unresolved_only = not _parse_bool(request.args.get("include_resolved"), default=False)
    conflicts = engine.get_conflicts(unresolved_only=unresolved_only)
    return jsonify({"ok": True, "conflicts": conflicts, "count": len(conflicts)})


@multizone_bp.route("/stats", methods=["GET"])
@require_token
def get_stats():
    engine = _get_engine()
    return jsonify({"ok": True, "stats": engine.get_stats()})
