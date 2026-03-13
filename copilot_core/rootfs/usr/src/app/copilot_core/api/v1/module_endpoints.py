"""API endpoints for Licht-, Helligkeit-, Heiz-, Bewegung-, and Praesenzmodul (v1.0.0).

Blueprint: /api/v1/modules/
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

modules_bp = Blueprint("modules", __name__, url_prefix="/api/v1/modules")

_licht_engine = None
_helligkeit_engine = None
_heiz_engine = None
_bewegung_engine = None
_praesenz_engine = None


def init_module_endpoints(
    licht=None, helligkeit=None, heiz=None, bewegung=None, praesenz=None
) -> None:
    """Inject module engines."""
    global _licht_engine, _helligkeit_engine, _heiz_engine, _bewegung_engine, _praesenz_engine
    _licht_engine = licht
    _helligkeit_engine = helligkeit
    _heiz_engine = heiz
    _bewegung_engine = bewegung
    _praesenz_engine = praesenz
    logger.info(
        "Module endpoints initialized (licht=%s, helligkeit=%s, heiz=%s, bewegung=%s, praesenz=%s)",
        licht is not None, helligkeit is not None, heiz is not None,
        bewegung is not None, praesenz is not None,
    )


# ── Lichtmodul ──────────────────────────────────────────────────────────

@modules_bp.route("/licht/dashboard", methods=["GET"])
@require_token
def licht_dashboard():
    """Get Lichtmodul dashboard."""
    if not _licht_engine:
        return jsonify({"error": "Lichtmodul not initialized"}), 503
    return jsonify({"ok": True, **_licht_engine.get_summary()})


@modules_bp.route("/licht/zone/<zone_id>", methods=["GET"])
@require_token
def licht_zone(zone_id):
    """Get light state for a zone."""
    if not _licht_engine:
        return jsonify({"error": "Lichtmodul not initialized"}), 503
    from dataclasses import asdict
    state = _licht_engine.get_zone_state(zone_id)
    return jsonify({"ok": True, **asdict(state)})


@modules_bp.route("/licht/target", methods=["GET"])
@require_token
def licht_target():
    """Get current time-based light target."""
    if not _licht_engine:
        return jsonify({"error": "Lichtmodul not initialized"}), 503
    hour = request.args.get("hour", type=int)
    return jsonify({"ok": True, **_licht_engine.get_target_for_hour(hour)})


# ── Helligkeitsmodul ────────────────────────────────────────────────────

@modules_bp.route("/helligkeit/dashboard", methods=["GET"])
@require_token
def helligkeit_dashboard():
    """Get Helligkeitsmodul dashboard."""
    if not _helligkeit_engine:
        return jsonify({"error": "Helligkeitsmodul not initialized"}), 503
    return jsonify({"ok": True, **_helligkeit_engine.get_summary()})


@modules_bp.route("/helligkeit/zone/<zone_id>", methods=["GET"])
@require_token
def helligkeit_zone(zone_id):
    """Get brightness analysis for a zone."""
    if not _helligkeit_engine:
        return jsonify({"error": "Helligkeitsmodul not initialized"}), 503
    from dataclasses import asdict
    zb = _helligkeit_engine.get_zone_brightness(zone_id)
    return jsonify({"ok": True, **asdict(zb)})


# ── Heizmodul ───────────────────────────────────────────────────────────

@modules_bp.route("/heiz/dashboard", methods=["GET"])
@require_token
def heiz_dashboard():
    """Get Heizmodul dashboard."""
    if not _heiz_engine:
        return jsonify({"error": "Heizmodul not initialized"}), 503
    return jsonify({"ok": True, **_heiz_engine.get_summary()})


@modules_bp.route("/heiz/zone/<zone_id>", methods=["GET"])
@require_token
def heiz_zone(zone_id):
    """Get climate state for a zone."""
    if not _heiz_engine:
        return jsonify({"error": "Heizmodul not initialized"}), 503
    from dataclasses import asdict
    zc = _heiz_engine.get_zone_climate(zone_id)
    return jsonify({"ok": True, **asdict(zc)})


# ── Bewegungsmodul ──────────────────────────────────────────────────────

@modules_bp.route("/bewegung/dashboard", methods=["GET"])
@require_token
def bewegung_dashboard():
    """Get Bewegungsmodul dashboard."""
    if not _bewegung_engine:
        return jsonify({"error": "Bewegungsmodul not initialized"}), 503
    return jsonify({"ok": True, **_bewegung_engine.get_summary()})


@modules_bp.route("/bewegung/zone/<zone_id>", methods=["GET"])
@require_token
def bewegung_zone(zone_id):
    """Get motion state for a zone."""
    if not _bewegung_engine:
        return jsonify({"error": "Bewegungsmodul not initialized"}), 503
    from dataclasses import asdict
    zm = _bewegung_engine.get_zone_motion(zone_id)
    return jsonify({"ok": True, **asdict(zm)})


# ── Praesenzmodul ───────────────────────────────────────────────────────

@modules_bp.route("/praesenz/dashboard", methods=["GET"])
@require_token
def praesenz_dashboard():
    """Get Praesenzmodul dashboard."""
    if not _praesenz_engine:
        return jsonify({"error": "Praesenzmodul not initialized"}), 503
    return jsonify({"ok": True, **_praesenz_engine.get_summary()})


@modules_bp.route("/praesenz/zone/<zone_id>", methods=["GET"])
@require_token
def praesenz_zone(zone_id):
    """Get presence state for a zone."""
    if not _praesenz_engine:
        return jsonify({"error": "Praesenzmodul not initialized"}), 503
    from dataclasses import asdict
    zp = _praesenz_engine.get_zone_presence(zone_id)
    return jsonify({"ok": True, **asdict(zp)})


@modules_bp.route("/praesenz/persons", methods=["GET"])
@require_token
def praesenz_persons():
    """Get all persons currently home."""
    if not _praesenz_engine:
        return jsonify({"error": "Praesenzmodul not initialized"}), 503
    persons = _praesenz_engine.get_all_persons_home()
    return jsonify({"ok": True, "persons": persons, "count": len(persons)})


# ── Aggregated Dashboard ───────────────────────────────────────────────

@modules_bp.route("/dashboard", methods=["GET"])
@require_token
def modules_dashboard():
    """Aggregated dashboard for all 5 smart home modules.

    Returns summaries for licht, helligkeit, heiz, bewegung, praesenz
    in a single call — used by HA coordinator polling.
    """
    result: dict = {"ok": True, "modules": {}}

    if _licht_engine:
        try:
            result["modules"]["licht"] = _licht_engine.get_summary()
        except Exception:
            logger.exception("Lichtmodul summary failed")
            result["modules"]["licht"] = None
    else:
        result["modules"]["licht"] = None

    if _helligkeit_engine:
        try:
            result["modules"]["helligkeit"] = _helligkeit_engine.get_summary()
        except Exception:
            logger.exception("Helligkeitsmodul summary failed")
            result["modules"]["helligkeit"] = None
    else:
        result["modules"]["helligkeit"] = None

    if _heiz_engine:
        try:
            result["modules"]["heiz"] = _heiz_engine.get_summary()
        except Exception:
            logger.exception("Heizmodul summary failed")
            result["modules"]["heiz"] = None
    else:
        result["modules"]["heiz"] = None

    if _bewegung_engine:
        try:
            result["modules"]["bewegung"] = _bewegung_engine.get_summary()
        except Exception:
            logger.exception("Bewegungsmodul summary failed")
            result["modules"]["bewegung"] = None
    else:
        result["modules"]["bewegung"] = None

    if _praesenz_engine:
        try:
            result["modules"]["praesenz"] = _praesenz_engine.get_summary()
        except Exception:
            logger.exception("Praesenzmodul summary failed")
            result["modules"]["praesenz"] = None
    else:
        result["modules"]["praesenz"] = None

    return jsonify(result)


@modules_bp.route("/zones/<zone_id>", methods=["GET"])
@require_token
def modules_zone_detail(zone_id):
    """Aggregated zone detail for all 5 modules — single call per zone.

    Returns per-zone data from each module engine.
    """
    from dataclasses import asdict

    result: dict = {"ok": True, "zone_id": zone_id, "modules": {}}

    if _licht_engine:
        try:
            result["modules"]["licht"] = asdict(_licht_engine.get_zone_state(zone_id))
        except Exception:
            result["modules"]["licht"] = None
    else:
        result["modules"]["licht"] = None

    if _helligkeit_engine:
        try:
            result["modules"]["helligkeit"] = asdict(_helligkeit_engine.get_zone_brightness(zone_id))
        except Exception:
            result["modules"]["helligkeit"] = None
    else:
        result["modules"]["helligkeit"] = None

    if _heiz_engine:
        try:
            result["modules"]["heiz"] = asdict(_heiz_engine.get_zone_climate(zone_id))
        except Exception:
            result["modules"]["heiz"] = None
    else:
        result["modules"]["heiz"] = None

    if _bewegung_engine:
        try:
            result["modules"]["bewegung"] = asdict(_bewegung_engine.get_zone_motion(zone_id))
        except Exception:
            result["modules"]["bewegung"] = None
    else:
        result["modules"]["bewegung"] = None

    if _praesenz_engine:
        try:
            result["modules"]["praesenz"] = asdict(_praesenz_engine.get_zone_presence(zone_id))
        except Exception:
            result["modules"]["praesenz"] = None
    else:
        result["modules"]["praesenz"] = None

    return jsonify(result)
