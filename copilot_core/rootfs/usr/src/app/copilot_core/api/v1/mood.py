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
        from copilot_core.api.v1.events_ingest import get_store as events_store_factory

        return events_store_factory()
    except Exception:
        return None


@bp.get("/")
def mood_root():
    """Root route — returns zone mood data for HA integration.

    HA mood_context_module expects: {"moods": {zone_name: {...}, ...}}
    """
    try:
        store = _event_store_if_available()
        events = store.list(limit=200) if store else []
        score = _scorer().score_from_events(events)
        mood_dict = score.to_dict()

        # Build moods dict keyed by zone — HA expects {"moods": {...}}
        moods = {"global": mood_dict}

        # If zone orchestrator is available, add zone data
        try:
            from copilot_core.mood.orchestrator import MoodOrchestrator, create_default_config
            config = create_default_config()
            orchestrator = MoodOrchestrator(
                mood_config=config,
                get_sensor_data=lambda entities: {},
                execute_service_calls=lambda calls: True,
            )
            zone_statuses = orchestrator.get_all_zones_status()
            for z in zone_statuses:
                if isinstance(z, dict) and "zone_name" in z:
                    moods[z["zone_name"]] = z
        except Exception:
            pass

        return jsonify({"ok": True, "moods": moods, "mood": mood_dict})
    except Exception as e:
        _LOGGER = current_app.logger
        _LOGGER.exception("Mood root failed")
        return jsonify({"ok": False, "error": str(e)}), 500


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
    """Get current mood state with presence and weather context."""
    try:
        store = _event_store_if_available()
        events = store.list(limit=200) if store else []
        score = _scorer().score_from_events(events)
        result = {"ok": True, "mood": score.to_dict()}

        # Enrich with cross-service context
        services = current_app.config.get("COPILOT_SERVICES", {})
        context = {}

        # Presence context
        presence = services.get("hub_presence")
        if presence and hasattr(presence, "get_summary"):
            try:
                context["presence"] = presence.get_summary()
            except Exception:
                pass

        # Weather context
        weather = services.get("weather_service")
        if weather and hasattr(weather, "_cache") and weather._cache:
            try:
                w = weather._cache
                context["weather"] = {
                    "condition": w.get("condition"),
                    "temperature_c": w.get("temperature_c"),
                    "cloud_cover_percent": w.get("cloud_cover_percent"),
                }
            except Exception:
                pass

        if context:
            result["context"] = context

        return jsonify(result)
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
    import re
    if not re.match(r'^[\w-]+$', zone_name) or len(zone_name) > 64:
        return jsonify({"ok": False, "error": "Invalid zone name"}), 400
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
        
        # Create orchestrator with HA service call execution via Supervisor API
        import os, requests as _requests
        _SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
        _SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

        def get_sensor_data(entities):
            data = {}
            if not _SUPERVISOR_TOKEN:
                return data
            headers = {"Authorization": f"Bearer {_SUPERVISOR_TOKEN}", "Content-Type": "application/json"}
            for entity_id in entities:
                try:
                    resp = _requests.get(f"{_SUPERVISOR_API}/states/{entity_id}", headers=headers, timeout=5)
                    if resp.ok:
                        state = resp.json()
                        data[entity_id] = {
                            "state": state.get("state"),
                            "attributes": state.get("attributes", {})
                        }
                except Exception:
                    pass
            return data

        def execute_service_calls(calls):
            if not _SUPERVISOR_TOKEN:
                current_app.logger.warning("No SUPERVISOR_TOKEN — cannot execute service calls")
                return False
            headers = {"Authorization": f"Bearer {_SUPERVISOR_TOKEN}", "Content-Type": "application/json"}
            try:
                for call in calls:
                    domain = call.get("domain")
                    service = call.get("service")
                    service_data = call.get("service_data", {})
                    resp = _requests.post(
                        f"{_SUPERVISOR_API}/services/{domain}/{service}",
                        json=service_data, headers=headers, timeout=10
                    )
                    if resp.status_code >= 400:
                        current_app.logger.warning("HA service %s/%s failed: %d", domain, service, resp.status_code)
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
        if not mood_state or not isinstance(mood_state, str):
            return jsonify({"ok": False, "error": "Missing or invalid 'mood' field"}), 400
        duration_minutes = payload.get("duration_minutes")
        if duration_minutes is not None:
            try:
                duration_minutes = int(duration_minutes)
                if duration_minutes < 1 or duration_minutes > 1440:
                    return jsonify({"ok": False, "error": "duration_minutes must be 1..1440"}), 400
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "duration_minutes must be an integer"}), 400
        
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


@bp.get("/aggregated")
def aggregated():
    """Get aggregated mood data across all zones.
    
    Returns overall mood score, zone breakdown, and trends.
    """
    try:
        from copilot_core.mood.orchestrator import MoodOrchestrator, create_default_config
        
        config = create_default_config()
        orchestrator = MoodOrchestrator(
            mood_config=config,
            get_sensor_data=lambda entities: {},
            execute_service_calls=lambda calls: True
        )
        
        # Get all zones status
        zone_statuses = orchestrator.get_all_zones_status()
        
        # Calculate aggregated score
        scores = [z.get("mood_score", 0.5) for z in zone_statuses if isinstance(z, dict)]
        avg_score = sum(scores) / len(scores) if scores else 0.5
        
        # Determine overall mood state
        if avg_score >= 0.7:
            overall_state = "positive"
        elif avg_score >= 0.4:
            overall_state = "neutral"
        else:
            overall_state = "negative"
        
        return jsonify({
            "ok": True,
            "aggregated": {
                "overall_score": avg_score,
                "overall_state": overall_state,
                "zone_count": len(zone_statuses),
                "zones": zone_statuses
            }
        })
    except Exception as e:
        _LOGGER = current_app.logger
        _LOGGER.exception("Aggregated mood failed")
        return jsonify({"ok": False, "error": str(e)}), 500
