"""Multi-Home API Endpoints.

Provides REST API for managing multiple home locations and synchronization.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import validate_token, require_token

logger = logging.getLogger(__name__)

bp = Blueprint("multihome", __name__, url_prefix="/api/v1/multihome")


@bp.before_request
def _require_auth():
    """Require authentication for all multihome endpoints."""
    if not validate_token(request):
        return jsonify({
            "ok": False,
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required"
        }), 401


def _now_iso() -> str:
    """Return current timestamp in ISO format."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _get_sync_engine():
    """Get sync engine instance."""
    try:
        from copilot_core.multihome.sync_engine import get_sync_engine
        return get_sync_engine()
    except Exception as e:
        logger.error(f"Failed to get sync engine: {e}")
        return None


def _get_config_sync():
    """Get config sync instance."""
    try:
        from copilot_core.multihome.config_sync import get_config_sync
        return get_config_sync()
    except Exception as e:
        logger.error(f"Failed to get config sync: {e}")
        return None


def _get_state_sync():
    """Get state sync instance."""
    try:
        from copilot_core.multihome.state_sync import get_state_sync
        return get_state_sync()
    except Exception as e:
        logger.error(f"Failed to get state sync: {e}")
        return None


# =============================================================================
# Home Management Endpoints
# =============================================================================

@bp.get("/homes")
@require_token
def list_homes():
    """List all configured home instances.
    
    Returns:
    - Array of home configurations (without sensitive data)
    - Sync status summary
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    status = sync_engine.get_sync_status()
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "homes": status["homes"],
        "summary": {
            "total_homes": len(status["homes"]),
            "primary_home": next((h for h in status["homes"] if h.get("is_primary")), None),
            "pending_operations": status["pending_operations"],
            "active_conflicts": status["active_conflicts"]
        }
    })


@bp.get("/homes/<home_id>")
@require_token
def get_home(home_id: str):
    """Get details for a specific home instance.
    
    Path params:
    - home_id: Home instance identifier
    
    Returns:
    - Home configuration and status
    - Last sync timestamp
    - Sync statistics
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    home = sync_engine.homes.get(home_id)
    
    if not home:
        return jsonify({
            "ok": False,
            "error": "Home not found",
            "home_id": home_id,
            "time": _now_iso()
        }), 404
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "home": home.to_dict()
    })


@bp.post("/homes")
@require_token
def register_home():
    """Register a new home instance.
    
    Request body:
    - id: Unique home identifier
    - name: Human-readable name
    - home_type: primary|vacation|office|secondary
    - base_url: Base URL for API access
    - auth_token: Authentication token for remote API
    - is_primary: Boolean (default: false)
    - sync_interval_seconds: Sync interval (default: 300)
    - metadata: Optional metadata dict
    
    Returns:
    - Registered home configuration
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "ok": False,
                "error": "Invalid request body",
                "time": _now_iso()
            }), 400
        
        # Validate required fields
        required_fields = ["id", "name", "home_type", "base_url"]
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "ok": False,
                    "error": f"Missing required field: {field}",
                    "time": _now_iso()
                }), 400
        
        from copilot_core.multihome.sync_engine import HomeInstance, HomeType
        
        # Check if home_type is valid
        try:
            home_type = HomeType(data["home_type"])
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid home_type. Must be one of: {[t.value for t in HomeType]}",
                "time": _now_iso()
            }), 400
        
        # Create home instance
        home = HomeInstance(
            id=data["id"],
            name=data["name"],
            home_type=home_type,
            base_url=data["base_url"],
            auth_token=data.get("auth_token", ""),
            is_primary=data.get("is_primary", False),
            is_active=data.get("is_active", True),
            sync_interval_seconds=data.get("sync_interval_seconds", 300),
            metadata=data.get("metadata", {})
        )
        
        # If this is marked as primary, unset other primaries
        if home.is_primary:
            for existing_home in sync_engine.homes.values():
                existing_home.is_primary = False
        
        sync_engine.register_home(home)
        
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "home": home.to_dict(),
            "message": f"Home '{home.name}' registered successfully"
        }), 201
        
    except Exception as e:
        logger.error(f"Failed to register home: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso()
        }), 500


@bp.delete("/homes/<home_id>")
@require_token
def unregister_home(home_id: str):
    """Unregister a home instance.
    
    Path params:
    - home_id: Home instance identifier
    
    Returns:
    - Confirmation of unregistration
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    if home_id not in sync_engine.homes:
        return jsonify({
            "ok": False,
            "error": "Home not found",
            "home_id": home_id,
            "time": _now_iso()
        }), 404
    
    sync_engine.unregister_home(home_id)
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "message": f"Home '{home_id}' unregistered successfully"
    })


# =============================================================================
# Configuration Sync Endpoints
# =============================================================================

@bp.get("/config/diff/<source_home_id>/<target_home_id>")
@require_token
def get_config_diff(source_home_id: str, target_home_id: str):
    """Get configuration difference report between two homes.
    
    Path params:
    - source_home_id: Source home identifier
    - target_home_id: Target home identifier
    
    Returns:
    - Configuration differences (added, modified, removed)
    - Version hashes
    """
    config_sync = _get_config_sync()
    
    if not config_sync:
        return jsonify({
            "ok": False,
            "error": "Config sync not available",
            "time": _now_iso()
        }), 503
    
    report = config_sync.get_config_diff_report(source_home_id, target_home_id)
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "report": report
    })


@bp.post("/config/sync")
@require_token
def create_config_sync():
    """Create a configuration synchronization operation.
    
    Request body:
    - source_home_id: Source home identifier
    - target_home_id: Target home identifier
    - sync_mode: full|incremental|selective (default: incremental)
    
    Returns:
    - Sync operation details
    - Changes detected
    """
    config_sync = _get_config_sync()
    
    if not config_sync:
        return jsonify({
            "ok": False,
            "error": "Config sync not available",
            "time": _now_iso()
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "ok": False,
                "error": "Invalid request body",
                "time": _now_iso()
            }), 400
        
        source_home_id = data.get("source_home_id")
        target_home_id = data.get("target_home_id")
        sync_mode = data.get("sync_mode", "incremental")
        
        if not source_home_id or not target_home_id:
            return jsonify({
                "ok": False,
                "error": "source_home_id and target_home_id are required",
                "time": _now_iso()
            }), 400
        
        operation = config_sync.create_config_sync_operation(
            source_home_id=source_home_id,
            target_home_id=target_home_id,
            sync_mode=sync_mode
        )
        
        if not operation:
            return jsonify({
                "ok": True,
                "time": _now_iso(),
                "message": "No configuration changes detected",
                "sync_mode": sync_mode
            }), 200
        
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "operation": operation.to_dict(),
            "message": "Configuration sync operation created"
        }), 201
        
    except Exception as e:
        logger.error(f"Failed to create config sync: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso()
        }), 500


@bp.post("/config/sync/<operation_id>/apply")
@require_token
def apply_config_sync(operation_id: str):
    """Apply a configuration synchronization operation.
    
    Path params:
    - operation_id: Sync operation identifier
    
    Returns:
    - Application result
    - Updated configuration status
    """
    sync_engine = _get_sync_engine()
    config_sync = _get_config_sync()
    
    if not sync_engine or not config_sync:
        return jsonify({
            "ok": False,
            "error": "Sync services not available",
            "time": _now_iso()
        }), 503
    
    # Find operation
    operation = None
    for op in sync_engine.pending_operations:
        if op.id == operation_id:
            operation = op
            break
    
    if not operation:
        return jsonify({
            "ok": False,
            "error": "Operation not found",
            "operation_id": operation_id,
            "time": _now_iso()
        }), 404
    
    success = config_sync.apply_config_sync(operation)
    
    return jsonify({
        "ok": success,
        "time": _now_iso(),
        "operation": operation.to_dict(),
        "message": "Configuration sync applied successfully" if success else "Failed to apply configuration sync"
    })


# =============================================================================
# State Sync Endpoints
# =============================================================================

@bp.get("/state/diff/<home_id_1>/<home_id_2>")
@require_token
def get_state_diff(home_id_1: str, home_id_2: str):
    """Get state difference report between two homes.
    
    Path params:
    - home_id_1: First home identifier
    - home_id_2: Second home identifier
    
    Returns:
    - State differences (synced, different, missing)
    - Entity-level details
    """
    state_sync = _get_state_sync()
    
    if not state_sync:
        return jsonify({
            "ok": False,
            "error": "State sync not available",
            "time": _now_iso()
        }), 503
    
    report = state_sync.get_state_diff_report(home_id_1, home_id_2)
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "report": report
    })


@bp.post("/state/sync")
@require_token
def create_state_sync():
    """Create a state synchronization operation.
    
    Request body:
    - source_home_id: Source home identifier
    - target_home_id: Target home identifier
    - entity_ids: Optional list of specific entities to sync
    - sync_mode: selective|full|domain-specific (default: selective)
    
    Returns:
    - Sync operation details
    """
    state_sync = _get_state_sync()
    
    if not state_sync:
        return jsonify({
            "ok": False,
            "error": "State sync not available",
            "time": _now_iso()
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "ok": False,
                "error": "Invalid request body",
                "time": _now_iso()
            }), 400
        
        source_home_id = data.get("source_home_id")
        target_home_id = data.get("target_home_id")
        entity_ids = data.get("entity_ids")
        sync_mode = data.get("sync_mode", "selective")
        
        if not source_home_id or not target_home_id:
            return jsonify({
                "ok": False,
                "error": "source_home_id and target_home_id are required",
                "time": _now_iso()
            }), 400
        
        operation = state_sync.create_state_sync_operation(
            source_home_id=source_home_id,
            target_home_id=target_home_id,
            entity_ids=entity_ids,
            sync_mode=sync_mode
        )
        
        if not operation:
            return jsonify({
                "ok": True,
                "time": _now_iso(),
                "message": "No states to sync",
                "sync_mode": sync_mode
            }), 200
        
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "operation": operation.to_dict(),
            "message": "State sync operation created"
        }), 201
        
    except Exception as e:
        logger.error(f"Failed to create state sync: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso()
        }), 500


@bp.post("/state/sync/<operation_id>/apply")
@require_token
def apply_state_sync(operation_id: str):
    """Apply a state synchronization operation.
    
    Path params:
    - operation_id: Sync operation identifier
    
    Returns:
    - Application result
    - Conflicts if any
    """
    sync_engine = _get_sync_engine()
    state_sync = _get_state_sync()
    
    if not sync_engine or not state_sync:
        return jsonify({
            "ok": False,
            "error": "Sync services not available",
            "time": _now_iso()
        }), 503
    
    # Find operation
    operation = None
    for op in sync_engine.pending_operations:
        if op.id == operation_id:
            operation = op
            break
    
    if not operation:
        return jsonify({
            "ok": False,
            "error": "Operation not found",
            "operation_id": operation_id,
            "time": _now_iso()
        }), 404
    
    success = state_sync.apply_state_sync(operation)
    
    return jsonify({
        "ok": success,
        "time": _now_iso(),
        "operation": operation.to_dict(),
        "message": "State sync applied successfully" if success else "Failed to apply state sync"
    })


# =============================================================================
# Location-Aware Automation Endpoints
# =============================================================================

@bp.post("/location/sync")
@require_token
def sync_location_aware_automations():
    """Synchronize location-aware automations (e.g., "Ferienhaus vorheizen").
    
    Request body:
    - source_home_id: Source home identifier
    - target_home_id: Target home identifier
    - location_context: Location context (e.g., "vacation_home", "office")
    
    Returns:
    - Merged automation count
    - Location context
    """
    config_sync = _get_config_sync()
    
    if not config_sync:
        return jsonify({
            "ok": False,
            "error": "Config sync not available",
            "time": _now_iso()
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "ok": False,
                "error": "Invalid request body",
                "time": _now_iso()
            }), 400
        
        source_home_id = data.get("source_home_id")
        target_home_id = data.get("target_home_id")
        location_context = data.get("location_context")
        
        if not all([source_home_id, target_home_id, location_context]):
            return jsonify({
                "ok": False,
                "error": "source_home_id, target_home_id, and location_context are required",
                "time": _now_iso()
            }), 400
        
        result = config_sync.sync_location_aware_automations(
            source_home_id=source_home_id,
            target_home_id=target_home_id,
            location_context=location_context
        )
        
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "result": result,
            "message": f"Merged {result['merged_count']} location-aware automations"
        }), 201
        
    except Exception as e:
        logger.error(f"Failed to sync location-aware automations: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso()
        }), 500


@bp.post("/climate/preheat")
@require_token
def preheat_vacation_home():
    """Preheat vacation home climate (example location-aware automation).
    
    Request body:
    - source_home_id: Primary home identifier
    - target_home_id: Vacation home identifier
    - climate_entity_id: Climate entity to sync
    - target_temperature: Optional target temperature
    
    Returns:
    - Operation details
    - Climate state synced
    """
    state_sync = _get_state_sync()
    
    if not state_sync:
        return jsonify({
            "ok": False,
            "error": "State sync not available",
            "time": _now_iso()
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "ok": False,
                "error": "Invalid request body",
                "time": _now_iso()
            }), 400
        
        source_home_id = data.get("source_home_id")
        target_home_id = data.get("target_home_id")
        climate_entity_id = data.get("climate_entity_id")
        
        if not all([source_home_id, target_home_id, climate_entity_id]):
            return jsonify({
                "ok": False,
                "error": "source_home_id, target_home_id, and climate_entity_id are required",
                "time": _now_iso()
            }), 400
        
        result = state_sync.sync_climate_state(
            source_home_id=source_home_id,
            target_home_id=target_home_id,
            climate_entity_id=climate_entity_id
        )
        
        status_code = 201 if result.get("success") else 400
        
        return jsonify({
            "ok": result.get("success", False),
            "time": _now_iso(),
            "result": result,
            "message": "Climate sync initiated" if result.get("success") else result.get("error", "Failed")
        }), status_code
        
    except Exception as e:
        logger.error(f"Failed to preheat vacation home: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso()
        }), 500


# =============================================================================
# Conflict Management Endpoints
# =============================================================================

@bp.get("/conflicts")
@require_token
def list_conflicts():
    """List all active synchronization conflicts.
    
    Returns:
    - Array of conflict records
    - Resolution recommendations
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    active_conflicts = [
        c.to_dict() for c in sync_engine.conflicts
        if c.resolution is None
    ]
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "conflicts": active_conflicts,
        "count": len(active_conflicts),
        "resolution_strategy": sync_engine.conflict_resolution_strategy.value
    })


@bp.post("/conflicts/<conflict_id>/resolve")
@require_token
def resolve_conflict(conflict_id: str):
    """Resolve a synchronization conflict.
    
    Path params:
    - conflict_id: Conflict identifier
    
    Request body:
    - resolution: last_write_wins|primary_wins|manual|merge
    
    Returns:
    - Resolution result
    - Resolved value
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "ok": False,
                "error": "Invalid request body",
                "time": _now_iso()
            }), 400
        
        resolution_str = data.get("resolution", "last_write_wins")
        
        from copilot_core.multihome.sync_engine import ConflictResolution
        
        try:
            resolution = ConflictResolution(resolution_str)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid resolution. Must be one of: {[r.value for r in ConflictResolution]}",
                "time": _now_iso()
            }), 400
        
        resolved_value = sync_engine.resolve_conflict(conflict_id, resolution)
        
        if resolved_value is None:
            return jsonify({
                "ok": False,
                "error": "Conflict not found or manual resolution required",
                "conflict_id": conflict_id,
                "time": _now_iso()
            }), 404
        
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "conflict_id": conflict_id,
            "resolution": resolution.value,
            "resolved_value": resolved_value,
            "message": "Conflict resolved successfully"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to resolve conflict: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso()
        }), 500


# =============================================================================
# Sync Status & Operations Endpoints
# =============================================================================

@bp.get("/status")
@require_token
def get_sync_status():
    """Get overall synchronization status.
    
    Returns:
    - All configured homes
    - Pending operations count
    - Active conflicts count
    - Last update timestamp
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    status = sync_engine.get_sync_status()
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "status": status
    })


@bp.get("/operations")
@require_token
def list_operations():
    """List pending synchronization operations.
    
    Query params:
    - status: Filter by status (pending|in_progress|completed|failed|conflict)
    - limit: Maximum number of operations to return (default: 50)
    
    Returns:
    - Array of operation records
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    status_filter = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    
    operations = sync_engine.pending_operations
    
    if status_filter:
        from copilot_core.multihome.sync_engine import SyncStatus
        try:
            status_enum = SyncStatus(status_filter)
            operations = [op for op in operations if op.status == status_enum]
        except ValueError:
            pass
    
    # Sort by created_at descending
    operations = sorted(operations, key=lambda op: op.created_at, reverse=True)[:limit]
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "operations": [op.to_dict() for op in operations],
        "count": len(operations)
    })


@bp.post("/operations/<operation_id>/execute")
@require_token
def execute_operation(operation_id: str):
    """Execute a pending synchronization operation.
    
    Path params:
    - operation_id: Operation identifier
    
    Returns:
    - Execution result
    - Updated operation status
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    # Find operation
    operation = None
    for op in sync_engine.pending_operations:
        if op.id == operation_id:
            operation = op
            break
    
    if not operation:
        return jsonify({
            "ok": False,
            "error": "Operation not found",
            "operation_id": operation_id,
            "time": _now_iso()
        }), 404
    
    success = sync_engine.execute_sync_operation(operation)
    
    return jsonify({
        "ok": success,
        "time": _now_iso(),
        "operation": operation.to_dict(),
        "message": "Operation executed successfully" if success else "Operation failed"
    })


@bp.delete("/operations/cleanup")
@require_token
def cleanup_operations():
    """Clean up old synchronization operations.
    
    Query params:
    - max_age_hours: Maximum age in hours (default: 24)
    
    Returns:
    - Number of operations cleaned up
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    max_age_hours = int(request.args.get("max_age_hours", 24))
    cleaned = sync_engine.cleanup_old_operations(max_age_hours)
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "cleaned_count": cleaned,
        "message": f"Cleaned up {cleaned} old operations"
    })


# =============================================================================
# Settings Endpoints
# =============================================================================

@bp.get("/settings")
@require_token
def get_settings():
    """Get multi-home synchronization settings.
    
    Returns:
    - Conflict resolution strategy
    - Default sync intervals
    - Encryption settings
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "settings": {
            "conflict_resolution_strategy": sync_engine.conflict_resolution_strategy.value,
            "data_dir": sync_engine.data_dir
        }
    })


@bp.put("/settings")
@require_token
def update_settings():
    """Update multi-home synchronization settings.
    
    Request body:
    - conflict_resolution_strategy: last_write_wins|primary_wins|manual|merge
    
    Returns:
    - Updated settings
    """
    sync_engine = _get_sync_engine()
    
    if not sync_engine:
        return jsonify({
            "ok": False,
            "error": "Sync engine not available",
            "time": _now_iso()
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "ok": False,
                "error": "Invalid request body",
                "time": _now_iso()
            }), 400
        
        resolution_str = data.get("conflict_resolution_strategy")
        
        if resolution_str:
            from copilot_core.multihome.sync_engine import ConflictResolution
            
            try:
                sync_engine.conflict_resolution_strategy = ConflictResolution(resolution_str)
                sync_engine._save_state()
            except ValueError:
                return jsonify({
                    "ok": False,
                    "error": f"Invalid resolution strategy. Must be one of: {[r.value for r in ConflictResolution]}",
                    "time": _now_iso()
                }), 400
        
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "settings": {
                "conflict_resolution_strategy": sync_engine.conflict_resolution_strategy.value,
                "data_dir": sync_engine.data_dir
            },
            "message": "Settings updated successfully"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso()
        }), 500
