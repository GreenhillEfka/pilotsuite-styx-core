"""Blueprint Registry Admin Panel — Flask Blueprint.

Provides admin-level data endpoints for managing the blueprint registry and
viewing drift alerts from the Backend UI / Styx Dashboard.

Registered under ``/api/v1/admin/blueprints``.
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

bp = Blueprint("blueprints_admin", __name__, url_prefix="/api/v1/admin/blueprints")


def _store() -> BlueprintRegistryStore:
    return get_blueprint_registry()


def _detector() -> DriftDetector:
    return get_drift_detector()


# ---------------------------------------------------------------------------
# Dashboard overview
# ---------------------------------------------------------------------------

@bp.route("/dashboard", methods=["GET"])
def admin_dashboard():
    """High-level dashboard data for the admin panel.

    Returns counts, drift summary, and a list of critical/critical+warning
    blueprints that need attention.
    """
    store = _store()
    detector = _detector()

    stats = store.get_stats()
    drift_summary = detector.get_drift_summary()

    # Top-drifted blueprints (top 10 by drift_count)
    all_entries = store.list_all(active_only=False, limit=1000)
    top_drifted = sorted(
        [e for e in all_entries if e.drift_count > 0],
        key=lambda e: e.drift_count,
        reverse=True,
    )[:10]

    # Recent registrations
    recent = sorted(all_entries, key=lambda e: e.updated_at or "", reverse=True)[:10]

    return jsonify({
        "ok": True,
        "stats": stats,
        "drift_summary": drift_summary,
        "top_drifted": [_entry_dict(e) for e in top_drifted],
        "recent": [_entry_dict(e) for e in recent],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Blueprint management
# ---------------------------------------------------------------------------

@bp.route("/blueprints", methods=["GET"])
def admin_list():
    """List all blueprints with full metadata (admin view).

    Query params:
        domain (str), active (0|1), limit (int), offset (int),
        sort (field), order (asc|desc)
    """
    domain = request.args.get("domain")
    active_only = request.args.get("active", "1") != "0"
    try:
        limit = int(request.args.get("limit", "100"))
        offset = int(request.args.get("offset", "0"))
    except ValueError:
        limit, offset = 100, 0

    sort_field = request.args.get("sort", "updated_at")
    sort_order = request.args.get("order", "desc")

    store = _store()
    entries = store.list_all(domain=domain, active_only=active_only, limit=limit + offset)

    # Simple in-memory sort (fine for admin panel scale)
    valid_sort = {"blueprint_id", "name", "hash", "drift_count", "updated_at", "domain"}
    if sort_field in valid_sort:
        entries = sorted(
            entries,
            key=lambda e: getattr(e, sort_field) or "",
            reverse=(sort_order == "desc"),
        )

    entries = entries[offset:offset + limit]

    return jsonify({
        "ok": True,
        "blueprints": [_entry_dict(e) for e in entries],
        "count": len(entries),
        "offset": offset,
        "limit": limit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@bp.route("/blueprints/<blueprint_id>", methods=["GET"])
def admin_get(blueprint_id: str):
    """Get detailed view of a single blueprint."""
    entry = _store().get(blueprint_id)
    if not entry:
        return jsonify({"ok": False, "error": "Blueprint not found"}), 404

    # Run live drift check
    detector = _detector()
    file_path = None
    current_hash = entry.hash
    live_alert = None

    if entry.file_path:
        import os
        if os.path.isabs(entry.file_path) and os.path.exists(entry.file_path):
            file_path = entry.file_path
        else:
            test = os.path.join("/data", entry.file_path)
            if os.path.exists(test):
                file_path = test

    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                yaml_content = fh.read()
            live_alert = detector.check_blueprint(
                blueprint_id, current_yaml=yaml_content
            )
            current_hash = live_alert.current_hash
        except Exception as exc:
            _LOGGER.warning("Could not read live blueprint %s: %s", file_path, exc)

    return jsonify({
        "ok": True,
        "blueprint": _entry_dict(entry),
        "current_hash": current_hash,
        "live_alert": live_alert.to_dict() if live_alert else None,
        "file_path": file_path,
    })


@bp.route("/blueprints/<blueprint_id>/rehash", methods=["POST"])
def admin_rehash(blueprint_id: str):
    """Force-recompute and update the stored hash for a blueprint.

    Use this when the blueprint was intentionally changed and the new
    version should become the canonical reference.

    Body (JSON):
        yaml (str, optional): raw YAML to hash; if omitted the file on disk is used
    """
    entry = _store().get(blueprint_id)
    if not entry:
        return jsonify({"ok": False, "error": "Blueprint not found"}), 404

    data = request.get_json() or {}
    yaml_content = data.get("yaml")

    if not yaml_content and entry.file_path:
        import os
        path = entry.file_path
        if not os.path.isabs(path):
            path = os.path.join("/data", path)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                yaml_content = fh.read()

    if not yaml_content:
        return jsonify({"ok": False, "error": "No yaml content available"}), 400

    from copilot_core.registry.hash_calculator import compute_yaml_hash
    new_hash = compute_yaml_hash(yaml_content)

    # Update entry with new hash, reset drift counters
    entry.hash = new_hash
    entry.drift_count = 0
    entry.last_drift_at = None
    _store().upsert(entry)

    _LOGGER.info("Re-hashed blueprint %s → %s...", blueprint_id, new_hash[:12])
    return jsonify({
        "ok": True,
        "blueprint_id": blueprint_id,
        "new_hash": new_hash,
    })


@bp.route("/blueprints/<blueprint_id>/deactivate", methods=["POST"])
def admin_deactivate(blueprint_id: str):
    """Deactivate (soft-delete) a blueprint from the registry."""
    deactivated = _store().deactivate(blueprint_id)
    if not deactivated:
        return jsonify({"ok": False, "error": "Blueprint not found"}), 404
    _LOGGER.info("Admin deactivated blueprint: %s", blueprint_id)
    return jsonify({"ok": True, "blueprint_id": blueprint_id})


@bp.route("/blueprints/<blueprint_id>", methods=["DELETE"])
def admin_delete(blueprint_id: str):
    """Hard-delete a blueprint from the registry."""
    deleted = _store().delete(blueprint_id)
    if not deleted:
        return jsonify({"ok": False, "error": "Blueprint not found"}), 404
    _LOGGER.info("Admin deleted blueprint: %s", blueprint_id)
    return jsonify({"ok": True, "deleted": blueprint_id})


# ---------------------------------------------------------------------------
# Drift alerts
# ---------------------------------------------------------------------------

@bp.route("/drift/alerts", methods=["GET"])
def admin_drift_alerts():
    """Get all drift alerts across all blueprints.

    Query params:
        severity (str): info | warning | critical
        status   (str): clean | drifted | new | missing | error
        limit    (int)
    """
    detector = _detector()
    all_alerts = detector.check_all()

    severity = request.args.get("severity")
    if severity:
        all_alerts = [a for a in all_alerts if a.severity == severity]

    status = request.args.get("status")
    if status:
        all_alerts = [a for a in all_alerts if a.status.value == status]

    try:
        limit = int(request.args.get("limit", "200"))
    except ValueError:
        limit = 200

    all_alerts = all_alerts[:limit]
    summary = detector.get_drift_summary()

    return jsonify({
        "ok": True,
        "alerts": [a.to_dict() for a in all_alerts],
        "count": len(all_alerts),
        "summary": summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@bp.route("/drift/critical", methods=["GET"])
def admin_critical_drifts():
    """Get only critical drift alerts (3+ drifts without resolution)."""
    detector = _detector()
    summary = detector.get_drift_summary()
    return jsonify({
        "ok": True,
        "critical_drifts": summary.get("critical_drifts", []),
        "count": len(summary.get("critical_drifts", [])),
        "checked_at": summary.get("checked_at"),
    })


@bp.route("/drift/scan", methods=["POST"])
def admin_drift_scan():
    """Trigger a full drift scan and return results.

    Body (JSON, optional):
        domain (str): restrict scan to a specific domain

    Returns per-blueprint drift status.
    """
    data = request.get_json() or {}
    domain = data.get("domain")

    store = _store()
    detector = _detector()

    entries = store.list_all(domain=domain, active_only=True)
    alerts: List[Dict[str, Any]] = []

    for entry in entries:
        import os
        file_path = entry.file_path
        if file_path and not os.path.isabs(file_path):
            file_path = os.path.join("/data", file_path)

        if not file_path or not os.path.exists(file_path):
            alerts.append(DriftAlert(
                blueprint_id=entry.blueprint_id,
                name=entry.name,
                status=DriftStatus.MISSING,
                stored_hash=entry.hash,
                message=f"File not found: {file_path or entry.file_path}",
                severity="warning",
            ).to_dict())
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                yaml_content = fh.read()
            alert = detector.check_blueprint(entry.blueprint_id, current_yaml=yaml_content)
            alerts.append(alert.to_dict())
        except Exception as exc:
            alerts.append(DriftAlert(
                blueprint_id=entry.blueprint_id,
                name=entry.name,
                status=DriftStatus.ERROR,
                message=str(exc),
                severity="warning",
            ).to_dict())

    by_severity: Dict[str, int] = {}
    for a in alerts:
        s = a.get("severity", "info")
        by_severity[s] = by_severity.get(s, 0) + 1

    return jsonify({
        "ok": True,
        "alerts": alerts,
        "count": len(alerts),
        "by_severity": by_severity,
        "domain": domain,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------

@bp.route("/blueprints/bulk-register", methods=["POST"])
def admin_bulk_register():
    """Bulk-register multiple blueprints at once.

    Body (JSON):
        blueprints: list of {blueprint_id, domain, name, yaml, version?, source?, file_path?, metadata?}

    Returns list of results per blueprint.
    """
    data = request.get_json() or {}
    items = data.get("blueprints", [])

    if not isinstance(items, list):
        return jsonify({"ok": False, "error": "'blueprints' must be a list"}), 400

    from copilot_core.registry.hash_calculator import compute_yaml_hash

    results: List[Dict[str, Any]] = []
    store = _store()

    for item in items:
        bid = item.get("blueprint_id")
        domain = item.get("domain")
        name = item.get("name")
        yaml_content = item.get("yaml")

        if not bid or not domain or not name:
            results.append({"ok": False, "blueprint_id": bid, "error": "Missing required fields"})
            continue

        try:
            if yaml_content:
                h = compute_yaml_hash(yaml_content)
            else:
                results.append({"ok": False, "blueprint_id": bid, "error": "No yaml provided"})
                continue

            entry = BlueprintEntry(
                blueprint_id=bid,
                domain=domain,
                name=name,
                hash=h,
                version=item.get("version", ""),
                source=item.get("source", ""),
                file_path=item.get("file_path", ""),
                metadata=item.get("metadata", {}),
            )
            store.upsert(entry)
            results.append({"ok": True, "blueprint_id": bid, "hash": h})
        except Exception as exc:
            _LOGGER.warning("Bulk register failed for %s: %s", bid, exc)
            results.append({"ok": False, "blueprint_id": bid, "error": str(exc)})

    ok_count = sum(1 for r in results if r.get("ok"))
    return jsonify({
        "ok": True,
        "total": len(results),
        "registered": ok_count,
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@bp.route("/blueprints/reset-drift", methods=["POST"])
def admin_reset_drift():
    """Reset drift counters for one or more blueprints.

    Body (JSON):
        blueprint_ids: list[str] — blueprints to reset; if empty resets all

    Returns number of blueprints reset.
    """
    data = request.get_json() or {}
    ids = data.get("blueprint_ids", [])

    store = _store()

    if not ids:
        # Reset all
        entries = store.list_all(active_only=False, limit=10000)
        ids = [e.blueprint_id for e in entries]

    count = 0
    for bid in ids:
        entry = store.get(bid)
        if entry:
            entry.drift_count = 0
            entry.last_drift_at = None
            store.upsert(entry)
            count += 1

    _LOGGER.info("Admin reset drift for %d blueprints", count)
    return jsonify({"ok": True, "reset_count": count})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _entry_dict(e: BlueprintEntry) -> Dict[str, Any]:
    return e.to_dict()
