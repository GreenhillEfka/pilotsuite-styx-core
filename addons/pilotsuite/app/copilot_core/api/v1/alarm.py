"""Alarm/Wecker REST API Blueprint.

Prefix: /api/v1/alarm
17 Endpoints: Dashboard, CRUD, Trigger/Snooze/Cancel, Presets, Zone, Curves
"""

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.api.rate_limit import rate_limit

_LOGGER = logging.getLogger(__name__)

alarm_bp = Blueprint("alarm", __name__, url_prefix="/api/v1/alarm")

_engine: Optional[Any] = None


def init_alarm_api(engine) -> None:
    """Wire AlarmEngine into API blueprint."""
    global _engine
    _engine = engine


def _require_engine():
    if _engine is None:
        return None, (jsonify({"ok": False, "error": "Alarm engine not initialized"}), 503)
    return _engine, None


# ── Dashboard ──────────────────────────────────────────────────────────────

@alarm_bp.route("/dashboard", methods=["GET"])
@require_token
def alarm_dashboard():
    """Dashboard-Daten: alle Alarme, Presets, Kurventypen."""
    engine, err = _require_engine()
    if err:
        return err
    return jsonify({"ok": True, **engine.get_dashboard()})


# ── CRUD ───────────────────────────────────────────────────────────────────

@alarm_bp.route("/alarms", methods=["GET"])
@require_token
def alarm_list():
    """Alle Alarme auflisten."""
    engine, err = _require_engine()
    if err:
        return err
    return jsonify({"ok": True, "alarms": engine.list_alarms()})


@alarm_bp.route("/alarms", methods=["POST"])
@require_token
@rate_limit(requests=10)
def alarm_create():
    """Neuen Alarm erstellen."""
    engine, err = _require_engine()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    config = engine.create_alarm(data)
    return jsonify({"ok": True, "alarm": config.to_dict()}), 201


@alarm_bp.route("/alarms/<alarm_id>", methods=["GET"])
@require_token
def alarm_get(alarm_id: str):
    """Einzelnen Alarm abrufen."""
    engine, err = _require_engine()
    if err:
        return err
    alarm = engine.get_alarm(alarm_id)
    if not alarm:
        return jsonify({"ok": False, "error": "Alarm not found"}), 404
    return jsonify({"ok": True, "alarm": alarm})


@alarm_bp.route("/alarms/<alarm_id>", methods=["PUT"])
@require_token
def alarm_update(alarm_id: str):
    """Alarm aktualisieren."""
    engine, err = _require_engine()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    config = engine.update_alarm(alarm_id, data)
    if not config:
        return jsonify({"ok": False, "error": "Alarm not found"}), 404
    return jsonify({"ok": True, "alarm": config.to_dict()})


@alarm_bp.route("/alarms/<alarm_id>", methods=["DELETE"])
@require_token
def alarm_delete(alarm_id: str):
    """Alarm loeschen."""
    engine, err = _require_engine()
    if err:
        return err
    if not engine.delete_alarm(alarm_id):
        return jsonify({"ok": False, "error": "Alarm not found"}), 404
    return jsonify({"ok": True, "deleted": alarm_id})


# ── Trigger / Snooze / Cancel ──────────────────────────────────────────────

@alarm_bp.route("/alarms/<alarm_id>/trigger", methods=["POST"])
@require_token
def alarm_trigger(alarm_id: str):
    """Alarm manuell ausloesen."""
    engine, err = _require_engine()
    if err:
        return err
    result = engine.trigger_alarm(alarm_id)
    if not result:
        return jsonify({"ok": False, "error": "Alarm not found"}), 404
    return jsonify({"ok": True, **result})


@alarm_bp.route("/alarms/<alarm_id>/snooze", methods=["POST"])
@require_token
def alarm_snooze(alarm_id: str):
    """Alarm snoozen."""
    engine, err = _require_engine()
    if err:
        return err
    result = engine.snooze_alarm(alarm_id)
    if not result:
        return jsonify({"ok": False, "error": "Alarm not found"}), 404
    return jsonify({"ok": True, **result})


@alarm_bp.route("/alarms/<alarm_id>/cancel", methods=["POST"])
@require_token
def alarm_cancel(alarm_id: str):
    """Alarm abbrechen."""
    engine, err = _require_engine()
    if err:
        return err
    result = engine.cancel_alarm(alarm_id)
    if not result:
        return jsonify({"ok": False, "error": "Alarm not found"}), 404
    return jsonify({"ok": True, **result})


# ── Zone Alarms ────────────────────────────────────────────────────────────

@alarm_bp.route("/zones/<zone_id>/alarms", methods=["GET"])
@require_token
def alarm_zone_list(zone_id: str):
    """Alarme fuer eine Zone auflisten."""
    engine, err = _require_engine()
    if err:
        return err
    alarms = engine.get_alarms_for_zone(zone_id)
    return jsonify({"ok": True, "zone_id": zone_id, "alarms": alarms})


# ── Presets ────────────────────────────────────────────────────────────────

@alarm_bp.route("/presets", methods=["GET"])
@require_token
def alarm_presets_list():
    """Alle Presets auflisten."""
    engine, err = _require_engine()
    if err:
        return err
    return jsonify({"ok": True, "presets": engine.list_presets()})


@alarm_bp.route("/presets/<preset_id>", methods=["GET"])
@require_token
def alarm_preset_get(preset_id: str):
    """Einzelnes Preset abrufen."""
    engine, err = _require_engine()
    if err:
        return err
    preset = engine.get_preset(preset_id)
    if not preset:
        return jsonify({"ok": False, "error": "Preset not found"}), 404
    return jsonify({"ok": True, "preset": preset})


@alarm_bp.route("/presets/<preset_id>", methods=["DELETE"])
@require_token
def alarm_preset_delete(preset_id: str):
    """Preset loeschen."""
    engine, err = _require_engine()
    if err:
        return err
    if not engine.delete_preset(preset_id):
        return jsonify({"ok": False, "error": "Preset not found"}), 404
    return jsonify({"ok": True, "deleted": preset_id})


@alarm_bp.route("/presets/<preset_id>/create-alarm", methods=["POST"])
@require_token
@rate_limit(requests=10)
def alarm_create_from_preset(preset_id: str):
    """Alarm aus Preset erstellen."""
    engine, err = _require_engine()
    if err:
        return err
    overrides = request.get_json(silent=True) or {}
    config = engine.create_from_preset(preset_id, overrides)
    if not config:
        return jsonify({"ok": False, "error": "Preset not found"}), 404
    return jsonify({"ok": True, "alarm": config.to_dict()}), 201


# ── Curves ─────────────────────────────────────────────────────────────────

@alarm_bp.route("/curves", methods=["GET"])
@require_token
def alarm_curves():
    """Alle verfuegbaren Kurventypen mit Samples."""
    from copilot_core.alarm.curves import get_all_curves
    return jsonify({"ok": True, "curves": get_all_curves()})
