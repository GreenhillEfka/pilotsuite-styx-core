"""Multi-Home Sync API Endpoints.

REST API for managing cross-home synchronization between PilotSuite instances.
Supports home registration, sync operations, conflict resolution, and status.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token, require_token
from copilot_core.sync.multi_home_sync import MultiHomeSync, SyncMode, SyncScope
from copilot_core.sync.homes_registry import HomeType, HomeStatus
from copilot_core.sync.conflict_resolver import ConflictStrategy

logger = logging.getLogger(__name__)

bp = Blueprint("sync", __name__, url_prefix="/api/v1/sync")

# Global sync instance (initialized lazily)
_sync_instance: MultiHomeSync | None = None


def _get_sync() -> MultiHomeSync:
    """Get or create the global sync instance."""
    global _sync_instance
    if _sync_instance is None:
        import os
        from copilot_core.sync.multi_home_sync import MultiHomeSync

        home_id = os.environ.get("PILOTSUITE_HOME_ID", "primary-home")
        shared_secret = os.environ.get("MULTIHOME_SHARED_SECRET", "change-me-in-production")
        data_dir = os.environ.get("MULTIHOME_DATA_DIR", "/data/multihome")

        _sync_instance = MultiHomeSync(
            home_id=home_id,
            shared_secret=shared_secret,
            data_dir=data_dir,
        )
    return _sync_instance


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Authentication
# =============================================================================


@bp.before_request
def _require_auth():
    """Require authentication for all sync endpoints."""
    if not validate_token(request):
        return jsonify({
            "ok": False,
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required",
        }), 401


# =============================================================================
# Home Registration Endpoints
# =============================================================================


@bp.get("/homes")
@require_token
def list_homes():
    """List all registered home instances.

    Returns:
    - Array of home registrations
    - Primary home indicator
    - Sync status for each home
    """
    sync = _get_sync()
    homes = sync.list_homes()

    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "homes": [h.to_dict() for h in homes],
        "count": len(homes),
        "primary_home_id": sync.primary_home.home_id if sync.primary_home else None,
    })


@bp.get("/homes/<home_id>")
@require_token
def get_home(home_id: str):
    """Get details for a specific registered home.

    Path params:
    - home_id: Home instance identifier
    """
    sync = _get_sync()
    home = sync.get_home(home_id)

    if not home:
        return jsonify({
            "ok": False,
            "error": "Home not found",
            "home_id": home_id,
            "time": _now_iso(),
        }), 404

    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "home": home.to_dict(),
    })


@bp.post("/homes")
@require_token
def register_home():
    """Register a new home instance for synchronization.

    Request body:
    - home_id: Unique identifier (required)
    - name: Human-readable name (required)
    - home_type: primary|vacation|office|secondary (required)
    - base_url: Base URL for API access (required)
    - auth_token: Authentication token (optional)
    - is_primary: Boolean (default: false)
    - sync_interval_seconds: Sync interval in seconds (default: 300)
    """
    sync = _get_sync()

    try:
        data = request.get_json() or {}

        required = ["home_id", "name", "home_type", "base_url"]
        for field in required:
            if field not in data:
                return jsonify({
                    "ok": False,
                    "error": f"Missing required field: {field}",
                    "time": _now_iso(),
                }), 400

        # Validate home_type
        try:
            home_type = HomeType(data["home_type"])
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid home_type. Must be one of: {[t.value for t in HomeType]}",
                "time": _now_iso(),
            }), 400

        home = sync.register_home(
            home_id=data["home_id"],
            name=data["name"],
            home_type=home_type,
            base_url=data["base_url"],
            auth_token=data.get("auth_token", ""),
            is_primary=data.get("is_primary", False),
            sync_interval_seconds=data.get("sync_interval_seconds", 300),
        )

        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "home": home.to_dict(),
            "message": f"Home '{home.name}' registered successfully",
        }), 201

    except Exception as e:
        logger.exception("Failed to register home")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso(),
        }), 500


@bp.delete("/homes/<home_id>")
@require_token
def unregister_home(home_id: str):
    """Unregister a home instance.

    Path params:
    - home_id: Home instance identifier
    """
    sync = _get_sync()

    if not sync.get_home(home_id):
        return jsonify({
            "ok": False,
            "error": "Home not found",
            "home_id": home_id,
            "time": _now_iso(),
        }), 404

    sync.unregister_home(home_id)

    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "message": f"Home '{home_id}' unregistered successfully",
    })


@bp.post("/homes/<home_id>/status")
@require_token
def update_home_status(home_id: str):
    """Update the status of a registered home.

    Path params:
    - home_id: Home instance identifier

    Request body:
    - status: online|offline|syncing|unreachable
    """
    sync = _get_sync()
    home = sync.get_home(home_id)

    if not home:
        return jsonify({
            "ok": False,
            "error": "Home not found",
            "home_id": home_id,
            "time": _now_iso(),
        }), 404

    try:
        data = request.get_json() or {}
        status_str = data.get("status", "online")

        try:
            status = HomeStatus(status_str)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid status. Must be one of: {[s.value for s in HomeStatus]}",
                "time": _now_iso(),
            }), 400

        sync._registry.update_status(home_id, status)

        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "home_id": home_id,
            "status": status.value,
        }), 200

    except Exception as e:
        logger.exception("Failed to update home status")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso(),
        }), 500


# =============================================================================
# Synchronization Endpoints
# =============================================================================


@bp.post("/sync/to/<target_home_id>")
@require_token
def sync_to(target_home_id: str):
    """Push synchronization to a target home.

    Path params:
    - target_home_id: Target home identifier

    Request body (optional):
    - mode: full|incremental|selective|config_only|state_only (default: incremental)
    - scope: config|state|automations|all (default: all)
    - entity_ids: Optional list of specific entity IDs to sync
    """
    sync = _get_sync()

    if not sync.get_home(target_home_id):
        return jsonify({
            "ok": False,
            "error": "Target home not found",
            "target_home_id": target_home_id,
            "time": _now_iso(),
        }), 404

    try:
        data = request.get_json() or {}

        mode_str = data.get("mode", "incremental")
        scope_str = data.get("scope", "all")

        try:
            mode = SyncMode(mode_str)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid mode. Must be one of: {[m.value for m in SyncMode]}",
                "time": _now_iso(),
            }), 400

        try:
            scope = SyncScope(scope_str)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid scope. Must be one of: {[s.value for s in SyncScope]}",
                "time": _now_iso(),
            }), 400

        entity_ids = data.get("entity_ids")

        job = sync.sync_to(
            target_home_id=target_home_id,
            mode=mode,
            scope=scope,
            entity_ids=entity_ids,
        )

        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "job": job.to_dict(),
            "message": f"Sync job {job.id} initiated to {target_home_id}",
        }), 202

    except Exception as e:
        logger.exception("Failed to initiate sync")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso(),
        }), 500


@bp.post("/sync/from/<source_home_id>")
@require_token
def sync_from(source_home_id: str):
    """Pull synchronization from a source home.

    Path params:
    - source_home_id: Source home identifier

    Request body (optional):
    - mode: full|incremental|selective|config_only|state_only (default: incremental)
    - scope: config|state|automations|all (default: all)
    - entity_ids: Optional list of specific entity IDs to sync
    """
    sync = _get_sync()

    if not sync.get_home(source_home_id):
        return jsonify({
            "ok": False,
            "error": "Source home not found",
            "source_home_id": source_home_id,
            "time": _now_iso(),
        }), 404

    try:
        data = request.get_json() or {}

        mode_str = data.get("mode", "incremental")
        scope_str = data.get("scope", "all")

        try:
            mode = SyncMode(mode_str)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid mode. Must be one of: {[m.value for m in SyncMode]}",
                "time": _now_iso(),
            }), 400

        try:
            scope = SyncScope(scope_str)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid scope. Must be one of: {[s.value for s in SyncScope]}",
                "time": _now_iso(),
            }), 400

        entity_ids = data.get("entity_ids")

        job = sync.sync_from(
            source_home_id=source_home_id,
            mode=mode,
            scope=scope,
            entity_ids=entity_ids,
        )

        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "job": job.to_dict(),
            "message": f"Sync job {job.id} initiated from {source_home_id}",
        }), 202

    except Exception as e:
        logger.exception("Failed to initiate sync")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso(),
        }), 500


@bp.get("/jobs")
@require_token
def list_jobs():
    """List recent synchronization jobs.

    Query params:
    - limit: Maximum number of jobs to return (default: 50)
    - status: Filter by status (pending|running|completed|failed|conflict)
    """
    sync = _get_sync()
    limit = int(request.args.get("limit", 50))
    status_filter = request.args.get("status")

    jobs = sync.list_jobs(limit=limit)

    if status_filter:
        jobs = [j for j in jobs if j.status == status_filter]

    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "jobs": [j.to_dict() for j in jobs],
        "count": len(jobs),
    })


@bp.get("/jobs/<job_id>")
@require_token
def get_job(job_id: str):
    """Get details for a specific sync job.

    Path params:
    - job_id: Job identifier
    """
    sync = _get_sync()
    job = sync.get_job(job_id)

    if not job:
        return jsonify({
            "ok": False,
            "error": "Job not found",
            "job_id": job_id,
            "time": _now_iso(),
        }), 404

    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "job": job.to_dict(),
    })


# =============================================================================
# Conflict Management Endpoints
# =============================================================================


@bp.get("/conflicts")
@require_token
def list_conflicts():
    """List synchronization conflicts.

    Query params:
    - active_only: Boolean (default: true)
    """
    sync = _get_sync()
    active_only = request.args.get("active_only", "true").lower() == "true"

    conflicts = sync.list_conflicts(active_only=active_only)

    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "conflicts": [c.to_dict() for c in conflicts],
        "count": len(conflicts),
    })


@bp.get("/conflicts/<conflict_id>")
@require_token
def get_conflict(conflict_id: str):
    """Get details for a specific conflict.

    Path params:
    - conflict_id: Conflict identifier
    """
    sync = _get_sync()
    conflict = sync._conflict_resolver.get_conflict(conflict_id)

    if not conflict:
        return jsonify({
            "ok": False,
            "error": "Conflict not found",
            "conflict_id": conflict_id,
            "time": _now_iso(),
        }), 404

    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "conflict": conflict.to_dict(),
    })


@bp.post("/conflicts/<conflict_id>/resolve")
@require_token
def resolve_conflict(conflict_id: str):
    """Resolve a synchronization conflict.

    Path params:
    - conflict_id: Conflict identifier

    Request body:
    - resolution: last_write_wins|primary_wins|merge|manual (optional, uses conflict's strategy if omitted)
    - manual_value: Value to use if resolution is 'manual'
    """
    sync = _get_sync()

    if not sync._conflict_resolver.get_conflict(conflict_id):
        return jsonify({
            "ok": False,
            "error": "Conflict not found",
            "conflict_id": conflict_id,
            "time": _now_iso(),
        }), 404

    try:
        data = request.get_json() or {}
        resolution = data.get("resolution")
        manual_value = data.get("manual_value")

        resolved_value = sync.resolve_conflict(
            conflict_id=conflict_id,
            resolution=resolution,
            manual_value=manual_value,
        )

        if resolved_value is None and resolution != "manual":
            return jsonify({
                "ok": False,
                "error": "Failed to resolve conflict",
                "conflict_id": conflict_id,
                "time": _now_iso(),
            }), 500

        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "conflict_id": conflict_id,
            "resolution": resolution,
            "resolved_value": resolved_value,
            "message": "Conflict resolved successfully",
        }), 200

    except Exception as e:
        logger.exception("Failed to resolve conflict")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso(),
        }), 500


@bp.put("/conflicts/strategy")
@require_token
def set_conflict_strategy():
    """Set conflict resolution strategy for an entity type.

    Request body:
    - entity_type: Entity type (e.g., 'automation', 'light', 'climate')
    - strategy: last_write_wins|primary_wins|merge|manual
    """
    sync = _get_sync()

    try:
        data = request.get_json() or {}

        entity_type = data.get("entity_type")
        strategy_str = data.get("strategy")

        if not entity_type or not strategy_str:
            return jsonify({
                "ok": False,
                "error": "entity_type and strategy are required",
                "time": _now_iso(),
            }), 400

        try:
            strategy = ConflictStrategy(strategy_str)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid strategy. Must be one of: {[s.value for s in ConflictStrategy]}",
                "time": _now_iso(),
            }), 400

        sync.set_conflict_strategy(entity_type, strategy)

        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "entity_type": entity_type,
            "strategy": strategy.value,
            "message": f"Conflict strategy for '{entity_type}' set to {strategy.value}",
        }), 200

    except Exception as e:
        logger.exception("Failed to set conflict strategy")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso(),
        }), 500


# =============================================================================
# Status & Health
# =============================================================================


@bp.get("/status")
@require_token
def get_status():
    """Get overall multi-home sync status.

    Returns:
    - Current home ID
    - All registered homes
    - Active sync jobs
    - Active conflicts
    """
    sync = _get_sync()
    status = sync.get_status()

    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "status": status,
    })


@bp.get("/health")
def health_check():
    """Lightweight health check (no auth required)."""
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "service": "multi-home-sync",
    })
