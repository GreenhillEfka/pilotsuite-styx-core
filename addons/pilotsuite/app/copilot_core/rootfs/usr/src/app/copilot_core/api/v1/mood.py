from flask import Blueprint, current_app, jsonify, request

from copilot_core.mood.scoring import MoodScorer
from copilot_core.storage.events import EventStore

bp = Blueprint("mood", __name__, url_prefix="/mood")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


_SCORER: MoodScorer | None = None


def _scorer() -> MoodScorer:
    global _SCORER
    if _SCORER is not None:
        return _SCORER
    cfg = current_app.config.get("COPILOT_CFG")
    _SCORER = MoodScorer(window_seconds=int(getattr(cfg, "mood_window_seconds", 3600)))
    return _SCORER


def _event_store_if_available() -> EventStore | None:
    # Import-time singletons can vary; we keep mood module decoupled.
    try:
        from copilot_core.api.v1.events import _store as events_store_factory

        return events_store_factory()
    except Exception:
        return None


@bp.post("/score")
def score():
    """Return a mood score.

    Inputs:
    - Optional body {events:[...]} for stateless scoring.
    - If omitted, uses recent ingested events from event store.
    """
    try:
        payload = request.get_json(silent=True) or {}

        events = None
        if isinstance(payload, dict) and isinstance(payload.get("events"), list):
            events = [e for e in payload["events"] if isinstance(e, dict)]

        if events is None:
            store = _event_store_if_available()
            if store is None:
                events = []
            else:
                # use current cache tail
                events = store.list(limit=200)

        score = _scorer().score_from_events(events)
        return jsonify({"ok": True, "mood": score.to_dict()})
    except Exception as e:
        _LOGGER = current_app.logger
        _LOGGER.exception("Mood score failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/state")
def state():
    """Get current mood state from stored events."""
    try:
        store = _event_store_if_available()
        events = store.list(limit=200) if store else []
        score = _scorer().score_from_events(events)
        return jsonify({"ok": True, "mood": score.to_dict()})
    except Exception as e:
        _LOGGER = current_app.logger
        _LOGGER.exception("Mood state failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/zones/<zone_name>/orchestrate")
def orchestrate_zone(zone_name):
    """Orchestrate mood inference and actions for a zone.
    
    Body:
    - sensor_data: Optional dict of sensor states
    - dry_run: bool (default False)
    - force_actions: bool (default False)
    """
    try:
        from copilot_core.mood.orchestrator import MoodOrchestrator, create_default_config
        
        payload = request.get_json(silent=True) or {}
        sensor_data = payload.get("sensor_data", {})
        dry_run = payload.get("dry_run", False)
        force_actions = payload.get("force_actions", False)
        
        config = create_default_config()
        
        # Get sensor data from HA if not provided
        if not sensor_data:
            store = _event_store_if_available()
            if store:
                # Use recent events to infer sensor data
                events = store.list(limit=50)
                sensor_data = {"events_count": len(events)}
        
        # Create orchestrator with HA service call execution
        def get_sensor_data(entities):
            data = {}
            for entity_id in entities:
                try:
                    state = current_app.hass.states.get(entity_id)
                    if state:
                        data[entity_id] = {
                            "state": state.state,
                            "attributes": dict(state.attributes)
                        }
                except Exception:
                    pass
            return data
        
        def execute_service_calls(calls):
            try:
                for call in calls:
                    domain = call.get("domain")
                    service = call.get("service")
                    service_data = call.get("service_data", {})
                    current_app.hass.services.call(domain, service, service_data, blocking=True)
                return True
            except Exception as e:
                current_app.logger.error("Service call execution failed: %s", e)
                return False
        
        orchestrator = MoodOrchestrator(
            mood_config=config,
            get_sensor_data=get_sensor_data,
            execute_service_calls=execute_service_calls
        )
        
        result = orchestrator.orchestrate_zone(
            zone_name=zone_name,
            dry_run=dry_run,
            force_actions=force_actions
        )
        
        return jsonify({"ok": True, "result": result.to_dict()})
    except Exception as e:
        _LOGGER = current_app.logger
        _LOGGER.exception("Mood orchestration failed for zone %s", zone_name)
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/zones/<zone_name>/force_mood")
def force_mood(zone_name):
    """Force a specific mood for a zone (admin override)."""
    try:
        from copilot_core.mood.orchestrator import MoodOrchestrator, create_default_config
        
        payload = request.get_json(silent=True) or {}
        mood_state = payload.get("mood")
        duration_minutes = payload.get("duration_minutes")
        
        config = create_default_config()
        
        orchestrator = MoodOrchestrator(
            mood_config=config,
            get_sensor_data=lambda entities: {},
            execute_service_calls=lambda calls: True
        )
        
        success = orchestrator.force_mood(
            zone_name=zone_name,
            mood_state=mood_state,
            duration_minutes=duration_minutes
        )
        
        if success:
            return jsonify({"ok": True, "message": f"Mood {mood_state} forced for zone {zone_name}"})
        else:
            return jsonify({"ok": False, "error": "Failed to force mood"}), 500
    except Exception as e:
        _LOGGER = current_app.logger
        _LOGGER.exception("Force mood failed for zone %s", zone_name)
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/zones/<zone_name>/status")
def zone_status(zone_name):
    """Get current status for a zone."""
    try:
        from copilot_core.mood.orchestrator import MoodOrchestrator, create_default_config
        
        config = create_default_config()
        orchestrator = MoodOrchestrator(
            mood_config=config,
            get_sensor_data=lambda entities: {},
            execute_service_calls=lambda calls: True
        )
        
        status = orchestrator.get_zone_status(zone_name)
        
        if status:
            return jsonify({"ok": True, "status": status})
        else:
            return jsonify({"ok": False, "error": "Zone not found"}), 404
    except Exception as e:
        _LOGGER = current_app.logger
        _LOGGER.exception("Zone status failed for %s", zone_name)
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/zones/status")
def all_zones_status():
    """Get status for all zones."""
    try:
        from copilot_core.mood.orchestrator import MoodOrchestrator, create_default_config
        
        config = create_default_config()
        orchestrator = MoodOrchestrator(
            mood_config=config,
            get_sensor_data=lambda entities: {},
            execute_service_calls=lambda calls: True
        )
        
        statuses = orchestrator.get_all_zones_status()
        return jsonify({"ok": True, "zones": statuses})
    except Exception as e:
        _LOGGER = current_app.logger
        _LOGGER.exception("All zones status failed")
        return jsonify({"ok": False, "error": str(e)}), 500
