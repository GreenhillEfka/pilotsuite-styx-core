"""Blueprint Registry API — /api/v1/registry/blueprints.

REST endpoints for managing the hash-based blueprint registry and drift detection.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.registry.blueprint_registry import (
    BlueprintEntry,
    BlueprintRegistryStore,
    get_blueprint_registry,
)
from copilot_core.registry.drift_detector import (
    DriftAlert,
    DriftDetector,
    DriftStatus,
    get_drift_detector,
)

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("registry_blueprints", __name__, url_prefix="/api/v1/registry")


# ---------------------------------------------------------------------------
# Store accessors (allow injection for testing)
# ---------------------------------------------------------------------------

def _store() -> BlueprintRegistryStore:
    return get_blueprint_registry()


def _detector() -> DriftDetector:
    return get_drift_detector()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry_to_dict(e: BlueprintEntry) -> Dict[str, Any]:
    return e.to_dict()


# ---------------------------------------------------------------------------
# GET /api/v1/registry/blueprints — List all registered blueprints
# ---------------------------------------------------------------------------

@bp.route("/blueprints", methods=["GET"])
def list_blueprints():
    """List registered blueprints.

    Query params:
        domain (str, optional): filter by domain (e.g. automation)
        active (0|1, optional): include inactive entries (default 1=active only)
        limit (int, optional): max results, default 500
    """
    domain = request.args.get("domain")
    active_only = request.args.get("active", "1") != "0"
    try:
        limit = int(request.args.get("limit", "500"))
    except ValueError:
        limit = 500

    store = _store()
    entries = store.list_all(domain=domain, active_only=active_only, limit=limit)
    stats = store.get_stats()

    return jsonify({
        "ok": True,
        "blueprints": [_entry_to_dict(e) for e in entries],
        "count": len(entries),
        "stats": stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# POST /api/v1/registry/blueprints — Register / upsert a blueprint
# ---------------------------------------------------------------------------

@bp.route("/blueprints", methods=["POST"])
def register_blueprint():
    """Register (or update) a blueprint entry.

    Body (JSON):
        blueprint_id  (str, required): stable identifier
        domain       (str, required): automation | script | etc.
        name         (str, required): human-readable name
        yaml         (str, optional): raw YAML content (hash computed automatically)
        dict         (dict, optional): already-parsed blueprint dict
        version      (str, optional)
        source       (str, optional)
        file_path    (str, optional)
        metadata     (dict, optional)

    Returns the created/updated entry.
    """
    data = request.get_json() or {}
    blueprint_id = data.get("blueprint_id")
    domain = data.get("domain")
    name = data.get("name")

    if not blueprint_id or not domain or not name:
        return jsonify({
            "ok": False,
            "error": "blueprint_id, domain, and name are required",
        }), 400

    # Compute hash from YAML or dict
    yaml_content = data.get("yaml")
    dict_content = data.get("dict")
    if yaml_content:
        from copilot_core.registry.hash_calculator import compute_yaml_hash
        blueprint_hash = compute_yaml_hash(yaml_content)
        # Try to also store the parsed dict for reference
        try:
            import yaml as _yaml
            dict_content = _yaml.safe_load(yaml_content)
        except Exception:
            dict_content = None
    elif dict_content:
        from copilot_core.registry.hash_calculator import compute_blueprint_hash
        blueprint_hash = compute_blueprint_hash(dict_content)
    else:
        return jsonify({
            "ok": False,
            "error": "Either 'yaml' or 'dict' must be provided",
        }), 400

    entry = BlueprintEntry(
        blueprint_id=blueprint_id,
        domain=domain,
        name=name,
        hash=blueprint_hash,
        version=data.get("version", ""),
        source=data.get("source", ""),
        file_path=data.get("file_path", ""),
        metadata=data.get("metadata", {}),
    )
    _store().upsert(entry)

    _LOGGER.info("Registered blueprint: %s (hash=%s...)", blueprint_id, blueprint_hash[:12])
    return jsonify({
        "ok": True,
        "blueprint": _entry_to_dict(entry),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 201


# ---------------------------------------------------------------------------
# GET /api/v1/registry/blueprints/<blueprint_id> — Get a single blueprint
# ---------------------------------------------------------------------------

@bp.route("/blueprints/<blueprint_id>", methods=["GET"])
def get_blueprint(blueprint_id: str):
    """Fetch a single blueprint entry by id."""
    entry = _store().get(blueprint_id)
    if not entry:
        return jsonify({"ok": False, "error": "Blueprint not found"}), 404
    return jsonify({"ok": True, "blueprint": _entry_to_dict(entry)})


# ---------------------------------------------------------------------------
# DELETE /api/v1/registry/blueprints/<blueprint_id> — Remove a blueprint
# ---------------------------------------------------------------------------

@bp.route("/blueprints/<blueprint_id>", methods=["DELETE"])
def delete_blueprint(blueprint_id: str):
    """Hard-delete a blueprint entry from the registry."""
    deleted = _store().delete(blueprint_id)
    if not deleted:
        return jsonify({"ok": False, "error": "Blueprint not found"}), 404
    _LOGGER.info("Deleted blueprint from registry: %s", blueprint_id)
    return jsonify({"ok": True, "deleted": blueprint_id})


# ---------------------------------------------------------------------------
# PATCH /api/v1/registry/blueprints/<blueprint_id> — Deactivate
# ---------------------------------------------------------------------------

@bp.route("/blueprints/<blueprint_id>/deactivate", methods=["PATCH"])
def deactivate_blueprint(blueprint_id: str):
    """Soft-delete (deactivate) a blueprint entry."""
    deactivated = _store().deactivate(blueprint_id)
    if not deactivated:
        return jsonify({"ok": False, "error": "Blueprint not found"}), 404
    _LOGGER.info("Deactivated blueprint: %s", blueprint_id)
    return jsonify({"ok": True, "blueprint_id": blueprint_id})


# ---------------------------------------------------------------------------
# POST /api/v1/registry/blueprints/drift — Check drift for a blueprint
# ---------------------------------------------------------------------------

@bp.route("/blueprints/drift", methods=["POST"])
def check_drift():
    """Check one or more blueprints for hash drift.

    Body (JSON):
        blueprint_id  (str, optional): check single blueprint
        yaml          (str, optional): raw YAML to compare
        dict          (dict, optional): parsed blueprint dict to compare
        batch         (list[dict], optional): list of {blueprint_id, yaml?, dict?}
            — if provided, blueprint_id/yaml/dict are ignored and batch is used

    Returns a DriftAlert (or list of alerts for batch).
    """
    data = request.get_json() or {}
    batch = data.get("batch")

    if batch:
        # Batch mode: [{blueprint_id, yaml?, dict?}, ...]
        blueprints: Dict[str, Dict[str, Any]] = {}
        for item in batch:
            bid = item.get("blueprint_id")
            if not bid:
                continue
            if item.get("dict"):
                blueprints[bid] = item["dict"]
            elif item.get("yaml"):
                import yaml as _yaml
                try:
                    blueprints[bid] = _yaml.safe_load(item["yaml"]) or {}
                except Exception:
                    blueprints[bid] = {}

        detector = _detector()
        alerts = detector.check_batch(blueprints)
        return jsonify({
            "ok": True,
            "alerts": [a.to_dict() for a in alerts],
            "count": len(alerts),
            "summary": _build_summary(alerts),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Single mode
    blueprint_id = data.get("blueprint_id")
    if not blueprint_id:
        return jsonify({"ok": False, "error": "blueprint_id required"}), 400

    alert = _detector().check_blueprint(
        blueprint_id,
        current_yaml=data.get("yaml"),
        current_dict=data.get("dict"),
    )
    return jsonify({"ok": True, "alert": alert.to_dict()})


# ---------------------------------------------------------------------------
# GET /api/v1/registry/blueprints/drift/all — Check all registered blueprints
# ---------------------------------------------------------------------------

@bp.route("/blueprints/drift/all", methods=["GET"])
def check_all_drift():
    """Run drift detection across all registered blueprints."""
    summary = _detector().get_drift_summary()
    return jsonify({"ok": True, **summary})


# ---------------------------------------------------------------------------
# GET /api/v1/registry/blueprints/drift — List currently drifted blueprints
# ---------------------------------------------------------------------------

@bp.route("/blueprints/drift", methods=["GET"])
def list_drifted():
    """List blueprints with recorded drift.

    Query params:
        since (str, optional): ISO timestamp — only blueprints that drifted after this time
        min_count (int, optional): minimum drift count (default 1)
    """
    since = request.args.get("since")
    try:
        min_count = int(request.args.get("min_count", "1"))
    except ValueError:
        min_count = 1

    entries = _store().get_drifted(since_iso=since, min_drift_count=min_count)
    return jsonify({
        "ok": True,
        "blueprints": [_entry_to_dict(e) for e in entries],
        "count": len(entries),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# GET /api/v1/registry/stats — Registry statistics
# ---------------------------------------------------------------------------

@bp.route("/stats", methods=["GET"])
def registry_stats():
    """Return aggregate registry statistics."""
    stats = _store().get_stats()
    return jsonify({"ok": True, "stats": stats})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_summary(alerts: List[DriftAlert]) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    for a in alerts:
        by_status[a.status.value] = by_status.get(a.status.value, 0) + 1
        by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
    critical = [a.to_dict() for a in alerts if a.severity == "critical"]
    return {
        "total": len(alerts),
        "by_status": by_status,
        "by_severity": by_severity,
        "critical_drifts": critical,
    }
