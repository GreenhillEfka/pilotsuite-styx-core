"""
Multi-Home Sync API v1 for PilotSuite Core.

REST API endpoints for multi-home synchronization:
- Home registration and management
- Sync pair configuration
- Manual sync operations
- Conflict resolution
- Sync status and statistics
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

from ...sync.homes_registry import HomesRegistry, HomeRegistration, HomeStatus, HomeRole, SyncPair
from ...sync.conflict_resolver import ConflictResolver, Conflict, ConflictStrategy, ConflictSeverity, ConflictType
from ...sync.multi_home_sync import MultiHomeSync, SyncOperation, SyncStatus, SyncDirection, SyncScope

logger = logging.getLogger(__name__)

sync_api_bp = Blueprint("sync_api", __name__, url_prefix="/api/v1/sync")

# Global instances (set during app initialization)
_homes_registry: Optional[HomesRegistry] = None
_conflict_resolver: Optional[ConflictResolver] = None
_multi_home_sync: Optional[MultiHomeSync] = None


def set_homes_registry(registry: HomesRegistry) -> None:
    """Set the homes registry instance for API access."""
    global _homes_registry
    _homes_registry = registry
    logger.info("Sync API: Homes registry set")


def set_conflict_resolver(resolver: ConflictResolver) -> None:
    """Set the conflict resolver instance for API access."""
    global _conflict_resolver
    _conflict_resolver = resolver
    logger.info("Sync API: Conflict resolver set")


def set_multi_home_sync(sync: MultiHomeSync) -> None:
    """Set the multi-home sync instance for API access."""
    global _multi_home_sync
    _multi_home_sync = sync
    logger.info("Sync API: Multi-home sync set")


def _get_registry() -> HomesRegistry:
    """Get the homes registry, creating if needed."""
    global _homes_registry
    if _homes_registry is None:
        _homes_registry = HomesRegistry()
    return _homes_registry


def _get_resolver() -> ConflictResolver:
    """Get the conflict resolver, creating if needed."""
    global _conflict_resolver
    if _conflict_resolver is None:
        _conflict_resolver = ConflictResolver()
    return _conflict_resolver


def _get_sync() -> MultiHomeSync:
    """Get the multi-home sync, creating if needed."""
    global _multi_home_sync
    if _multi_home_sync is None:
        registry = _get_registry()
        resolver = _get_resolver()
        _multi_home_sync = MultiHomeSync(registry, resolver)
    return _multi_home_sync


# =============================================================================
# Home Registration Endpoints
# =============================================================================

@sync_api_bp.route("/homes", methods=["GET"])
def list_homes():
    """
    List all registered homes.
    
    Query Parameters:
        status: Filter by status (online, offline, connecting, error, maintenance)
        role: Filter by role (primary, secondary, peer, standalone)
        sync_enabled: Filter by sync enabled status (true/false)
    
    Returns:
        JSON response with list of homes
    """
    try:
        registry = _get_registry()
        
        status = request.args.get("status")
        role = request.args.get("role")
        sync_enabled = request.args.get("sync_enabled")
        
        # Parse enums
        status_filter = HomeStatus(status) if status else None
        role_filter = HomeRole(role) if role else None
        
        # Parse boolean
        sync_filter = None
        if sync_enabled is not None:
            sync_filter = sync_enabled.lower() == "true"
        
        homes = registry.get_homes(
            status=status_filter,
            role=role_filter,
            sync_enabled=sync_filter,
        )
        
        return jsonify({
            "success": True,
            "homes": [h.to_dict() for h in homes],
            "count": len(homes),
            "local_home_id": registry.local_home_id,
        })
        
    except Exception as e:
        logger.exception("Failed to list homes")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/homes/<home_id>", methods=["GET"])
def get_home(home_id: str):
    """
    Get a specific home by ID.
    
    Path Parameters:
        home_id: Home ID
    
    Returns:
        JSON response with home details
    """
    try:
        registry = _get_registry()
        home = registry.get_home(home_id)
        
        if not home:
            return jsonify({
                "success": False,
                "error": "Home not found",
            }), 404
        
        return jsonify({
            "success": True,
            "home": home.to_dict(),
        })
        
    except Exception as e:
        logger.exception(f"Failed to get home {home_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/homes", methods=["POST"])
def register_home():
    """
    Register a new home.
    
    Request Body:
        name (required): Home name
        url (optional): API URL for remote home
        api_token (optional): API token for authentication
        role (optional): Home role (primary, secondary, peer, standalone)
        location (optional): Geographic location
        timezone (optional): Timezone (default: Europe/Berlin)
        metadata (optional): Additional metadata
    
    Returns:
        JSON response with registered home
    """
    try:
        data = request.get_json() or {}
        
        if not data.get("name"):
            return jsonify({
                "success": False,
                "error": "name is required",
            }), 400
        
        registry = _get_registry()
        
        # Parse role
        role_str = data.get("role", "secondary")
        try:
            role = HomeRole(role_str)
        except ValueError:
            return jsonify({
                "success": False,
                "error": f"Invalid role: {role_str}",
            }), 400
        
        home = registry.register_home(
            name=data["name"],
            url=data.get("url"),
            api_token=data.get("api_token"),
            role=role,
            location=data.get("location"),
            timezone=data.get("timezone", "Europe/Berlin"),
            metadata=data.get("metadata", {}),
        )
        
        return jsonify({
            "success": True,
            "home": home.to_dict(),
            "message": f"Home '{home.name}' registered",
        }), 201
        
    except Exception as e:
        logger.exception("Failed to register home")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/homes/<home_id>", methods=["DELETE"])
def unregister_home(home_id: str):
    """
    Unregister a home.
    
    Path Parameters:
        home_id: Home ID to unregister
    
    Returns:
        JSON response with unregistration result
    """
    try:
        registry = _get_registry()
        
        if not registry.unregister_home(home_id):
            return jsonify({
                "success": False,
                "error": "Home not found or cannot unregister local home",
            }), 404
        
        return jsonify({
            "success": True,
            "message": "Home unregistered",
        })
        
    except Exception as e:
        logger.exception(f"Failed to unregister home {home_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/homes/<home_id>/status", methods=["PUT"])
def update_home_status(home_id: str):
    """
    Update home status.
    
    Path Parameters:
        home_id: Home ID
    
    Request Body:
        status (required): New status (online, offline, connecting, error, maintenance)
        last_error_message (optional): Error message if status is error
    
    Returns:
        JSON response with updated home
    """
    try:
        data = request.get_json() or {}
        registry = _get_registry()
        
        status_str = data.get("status")
        if not status_str:
            return jsonify({
                "success": False,
                "error": "status is required",
            }), 400
        
        try:
            status = HomeStatus(status_str)
        except ValueError:
            return jsonify({
                "success": False,
                "error": f"Invalid status: {status_str}",
            }), 400
        
        home = registry.update_home_status(
            home_id=home_id,
            status=status,
            last_error_message=data.get("last_error_message"),
        )
        
        if not home:
            return jsonify({
                "success": False,
                "error": "Home not found",
            }), 404
        
        return jsonify({
            "success": True,
            "home": home.to_dict(),
        })
        
    except Exception as e:
        logger.exception(f"Failed to update home status {home_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# =============================================================================
# Sync Pair Endpoints
# =============================================================================

@sync_api_bp.route("/pairs", methods=["GET"])
def list_sync_pairs():
    """
    List sync pairs.
    
    Query Parameters:
        home_id: Filter by home ID (pairs involving this home)
    
    Returns:
        JSON response with list of sync pairs
    """
    try:
        registry = _get_registry()
        home_id = request.args.get("home_id")
        
        pairs = registry.get_sync_pairs(home_id=home_id)
        
        return jsonify({
            "success": True,
            "pairs": [p.to_dict() for p in pairs],
            "count": len(pairs),
        })
        
    except Exception as e:
        logger.exception("Failed to list sync pairs")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/pairs", methods=["POST"])
def create_sync_pair():
    """
    Create a sync pair between two homes.
    
    Request Body:
        home_a_id (required): First home ID
        home_b_id (required): Second home ID
        sync_direction (optional): Direction (bidirectional, a_to_b, b_to_a)
    
    Returns:
        JSON response with created sync pair
    """
    try:
        data = request.get_json() or {}
        registry = _get_registry()
        
        home_a_id = data.get("home_a_id")
        home_b_id = data.get("home_b_id")
        
        if not home_a_id or not home_b_id:
            return jsonify({
                "success": False,
                "error": "home_a_id and home_b_id are required",
            }), 400
        
        pair = registry.create_sync_pair(
            home_a_id=home_a_id,
            home_b_id=home_b_id,
            sync_direction=data.get("sync_direction", "bidirectional"),
        )
        
        if not pair:
            return jsonify({
                "success": False,
                "error": "One or both homes not found",
            }), 404
        
        return jsonify({
            "success": True,
            "pair": pair.to_dict(),
            "message": f"Sync pair created between {home_a_id} and {home_b_id}",
        }), 201
        
    except Exception as e:
        logger.exception("Failed to create sync pair")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/pairs/<home_a_id>/<home_b_id>", methods=["DELETE"])
def remove_sync_pair(home_a_id: str, home_b_id: str):
    """
    Remove a sync pair.
    
    Path Parameters:
        home_a_id: First home ID
        home_b_id: Second home ID
    
    Returns:
        JSON response with removal result
    """
    try:
        registry = _get_registry()
        
        if not registry.remove_sync_pair(home_a_id, home_b_id):
            return jsonify({
                "success": False,
                "error": "Sync pair not found",
            }), 404
        
        return jsonify({
            "success": True,
            "message": "Sync pair removed",
        })
        
    except Exception as e:
        logger.exception(f"Failed to remove sync pair {home_a_id}-{home_b_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/homes/<home_id>/connected", methods=["GET"])
def get_connected_homes(home_id: str):
    """
    Get homes connected to a specific home.
    
    Path Parameters:
        home_id: Home ID
    
    Returns:
        JSON response with connected homes
    """
    try:
        registry = _get_registry()
        homes = registry.get_connected_homes(home_id)
        
        return jsonify({
            "success": True,
            "homes": [h.to_dict() for h in homes],
            "count": len(homes),
        })
        
    except Exception as e:
        logger.exception(f"Failed to get connected homes for {home_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# =============================================================================
# Sync Operation Endpoints
# =============================================================================

@sync_api_bp.route("/sync/<home_id>", methods=["POST"])
def sync_with_home(home_id: str):
    """
    Synchronize with a specific home.
    
    Path Parameters:
        home_id: Target home ID
    
    Request Body:
        direction (optional): Sync direction (push, pull, bidirectional)
        scope (optional): Sync scope (scenes, automations, devices, users, all)
        force (optional): Force sync even if recently synced
    
    Returns:
        JSON response with sync result
    """
    try:
        data = request.get_json() or {}
        sync_engine = _get_sync()
        
        # Parse direction
        direction_str = data.get("direction", "bidirectional")
        try:
            direction = SyncDirection(direction_str)
        except ValueError:
            return jsonify({
                "success": False,
                "error": f"Invalid direction: {direction_str}",
            }), 400
        
        # Parse scope
        scope_str = data.get("scope", "all")
        try:
            scope = SyncScope(scope_str)
        except ValueError:
            return jsonify({
                "success": False,
                "error": f"Invalid scope: {scope_str}",
            }), 400
        
        result = sync_engine.sync_with_home(
            target_home_id=home_id,
            direction=direction,
            scope=scope,
            force=data.get("force", False),
        )
        
        return jsonify({
            "success": result.success,
            "result": result.to_dict(),
        })
        
    except Exception as e:
        logger.exception(f"Failed to sync with home {home_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/sync/all", methods=["POST"])
def sync_all_homes():
    """
    Synchronize with all connected homes.
    
    Request Body:
        direction (optional): Sync direction
        scope (optional): Sync scope
    
    Returns:
        JSON response with results for each home
    """
    try:
        data = request.get_json() or {}
        sync_engine = _get_sync()
        
        direction_str = data.get("direction", "bidirectional")
        scope_str = data.get("scope", "all")
        
        try:
            direction = SyncDirection(direction_str)
            scope = SyncScope(scope_str)
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": str(e),
            }), 400
        
        results = sync_engine.sync_all_homes(direction=direction, scope=scope)
        
        return jsonify({
            "success": True,
            "results": {hid: r.to_dict() for hid, r in results.items()},
            "total_homes": len(results),
            "successful": sum(1 for r in results.values() if r.success),
            "failed": sum(1 for r in results.values() if not r.success),
        })
        
    except Exception as e:
        logger.exception("Failed to sync all homes")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/operations", methods=["GET"])
def list_operations():
    """
    List sync operations.
    
    Query Parameters:
        home_id: Filter by target home
        status: Filter by status
        limit: Maximum number to return (default: 50)
    
    Returns:
        JSON response with list of operations
    """
    try:
        sync_engine = _get_sync()
        
        home_id = request.args.get("home_id")
        status = request.args.get("status")
        limit = int(request.args.get("limit", 50))
        
        status_filter = None
        if status:
            try:
                status_filter = SyncStatus(status)
            except ValueError:
                pass
        
        operations = sync_engine.get_operations(
            home_id=home_id,
            status=status_filter,
            limit=limit,
        )
        
        return jsonify({
            "success": True,
            "operations": [op.to_dict() for op in operations],
            "count": len(operations),
        })
        
    except Exception as e:
        logger.exception("Failed to list operations")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/operations/<operation_id>", methods=["GET"])
def get_operation(operation_id: str):
    """
    Get sync operation by ID.
    
    Path Parameters:
        operation_id: Operation ID
    
    Returns:
        JSON response with operation details
    """
    try:
        sync_engine = _get_sync()
        operation = sync_engine.get_operation(operation_id)
        
        if not operation:
            return jsonify({
                "success": False,
                "error": "Operation not found",
            }), 404
        
        return jsonify({
            "success": True,
            "operation": operation.to_dict(),
        })
        
    except Exception as e:
        logger.exception(f"Failed to get operation {operation_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/operations/<operation_id>/cancel", methods=["POST"])
def cancel_operation(operation_id: str):
    """
    Cancel a sync operation.
    
    Path Parameters:
        operation_id: Operation ID to cancel
    
    Returns:
        JSON response with cancellation result
    """
    try:
        sync_engine = _get_sync()
        
        if not sync_engine.cancel_operation(operation_id):
            return jsonify({
                "success": False,
                "error": "Operation not found or cannot be cancelled",
            }), 404
        
        return jsonify({
            "success": True,
            "message": "Operation cancelled",
        })
        
    except Exception as e:
        logger.exception(f"Failed to cancel operation {operation_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/stats", methods=["GET"])
def get_sync_stats():
    """
    Get synchronization statistics.
    
    Returns:
        JSON response with sync statistics
    """
    try:
        sync_engine = _get_sync()
        stats = sync_engine.get_sync_stats()
        
        return jsonify({
            "success": True,
            "stats": stats,
        })
        
    except Exception as e:
        logger.exception("Failed to get sync stats")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# =============================================================================
# Conflict Resolution Endpoints
# =============================================================================

@sync_api_bp.route("/conflicts", methods=["GET"])
def list_conflicts():
    """
    List conflicts.
    
    Query Parameters:
        conflict_type: Filter by type
        severity: Filter by severity
        resolved: Filter by resolution status (true/false)
        item_type: Filter by item type (scene, automation, etc.)
    
    Returns:
        JSON response with list of conflicts
    """
    try:
        resolver = _get_resolver()
        
        conflict_type = request.args.get("conflict_type")
        severity = request.args.get("severity")
        resolved = request.args.get("resolved")
        item_type = request.args.get("item_type")
        
        # Parse enums
        type_filter = ConflictType(conflict_type) if conflict_type else None
        severity_filter = ConflictSeverity(severity) if severity else None
        
        # Parse boolean
        resolved_filter = None
        if resolved is not None:
            resolved_filter = resolved.lower() == "true"
        
        conflicts = resolver.get_conflicts(
            conflict_type=type_filter,
            severity=severity_filter,
            resolved=resolved_filter,
            item_type=item_type,
        )
        
        return jsonify({
            "success": True,
            "conflicts": [c.to_dict() for c in conflicts],
            "count": len(conflicts),
            "unresolved_count": len(resolver.get_unresolved_conflicts()),
        })
        
    except Exception as e:
        logger.exception("Failed to list conflicts")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/conflicts/<conflict_id>", methods=["GET"])
def get_conflict(conflict_id: str):
    """
    Get a specific conflict by ID.
    
    Path Parameters:
        conflict_id: Conflict ID
    
    Returns:
        JSON response with conflict details
    """
    try:
        resolver = _get_resolver()
        conflict = resolver.get_conflict(conflict_id)
        
        if not conflict:
            return jsonify({
                "success": False,
                "error": "Conflict not found",
            }), 404
        
        return jsonify({
            "success": True,
            "conflict": conflict.to_dict(),
        })
        
    except Exception as e:
        logger.exception(f"Failed to get conflict {conflict_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/conflicts/<conflict_id>/resolve", methods=["POST"])
def resolve_conflict(conflict_id: str):
    """
    Resolve a conflict.
    
    Path Parameters:
        conflict_id: Conflict ID to resolve
    
    Request Body:
        strategy (optional): Resolution strategy
        resolved_by (optional): Who is resolving (default: "user")
        custom_value (optional): Custom merged value
    
    Returns:
        JSON response with resolution
    """
    try:
        data = request.get_json() or {}
        resolver = _get_resolver()
        
        strategy_str = data.get("strategy")
        strategy = None
        if strategy_str:
            try:
                strategy = ConflictStrategy(strategy_str)
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": f"Invalid strategy: {strategy_str}",
                }), 400
        
        import asyncio
        
        async def run():
            return await resolver.resolve(
                conflict_id=conflict_id,
                strategy=strategy,
                resolved_by=data.get("resolved_by", "user"),
                custom_value=data.get("custom_value"),
            )
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        resolution = loop.run_until_complete(run())
        
        if not resolution:
            return jsonify({
                "success": False,
                "error": "Conflict not found",
            }), 404
        
        return jsonify({
            "success": True,
            "resolution": resolution.to_dict(),
        })
        
    except Exception as e:
        logger.exception(f"Failed to resolve conflict {conflict_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/conflicts/auto-resolve", methods=["POST"])
def auto_resolve_conflicts():
    """
    Auto-resolve all low-severity conflicts.
    
    Returns:
        JSON response with resolution count
    """
    try:
        resolver = _get_resolver()
        conflicts = resolver.get_conflicts(severity=ConflictSeverity.LOW, resolved=False)
        
        import asyncio
        
        async def run():
            count = 0
            for conflict in conflicts:
                result = await resolver.auto_resolve(conflict.conflict_id)
                if result:
                    count += 1
            return count
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        resolved_count = loop.run_until_complete(run())
        
        return jsonify({
            "success": True,
            "resolved_count": resolved_count,
            "message": f"Auto-resolved {resolved_count} low-severity conflicts",
        })
        
    except Exception as e:
        logger.exception("Failed to auto-resolve conflicts")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/conflicts/clear-resolved", methods=["POST"])
def clear_resolved_conflicts():
    """
    Clear resolved conflicts older than specified hours.
    
    Request Body:
        older_than_hours (optional): Age threshold (default: 24)
    
    Returns:
        JSON response with cleared count
    """
    try:
        data = request.get_json() or {}
        resolver = _get_resolver()
        
        cleared = resolver.clear_resolved(
            older_than_hours=data.get("older_than_hours", 24),
        )
        
        return jsonify({
            "success": True,
            "cleared_count": cleared,
        })
        
    except Exception as e:
        logger.exception("Failed to clear resolved conflicts")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# =============================================================================
# Auto-Sync Configuration Endpoints
# =============================================================================

@sync_api_bp.route("/auto-sync/enable", methods=["POST"])
def enable_auto_sync():
    """
    Enable automatic synchronization.
    
    Request Body:
        interval_seconds (optional): Sync interval in seconds (default: 60)
    
    Returns:
        JSON response with confirmation
    """
    try:
        data = request.get_json() or {}
        sync_engine = _get_sync()
        
        interval = data.get("interval_seconds", 60)
        sync_engine.enable_auto_sync(interval_seconds=interval)
        
        return jsonify({
            "success": True,
            "message": f"Auto-sync enabled (interval: {interval}s)",
        })
        
    except Exception as e:
        logger.exception("Failed to enable auto-sync")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/auto-sync/disable", methods=["POST"])
def disable_auto_sync():
    """
    Disable automatic synchronization.
    
    Returns:
        JSON response with confirmation
    """
    try:
        sync_engine = _get_sync()
        sync_engine.disable_auto_sync()
        
        return jsonify({
            "success": True,
            "message": "Auto-sync disabled",
        })
        
    except Exception as e:
        logger.exception("Failed to disable auto-sync")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@sync_api_bp.route("/local-home", methods=["GET"])
def get_local_home():
    """
    Get the local home registration.
    
    Returns:
        JSON response with local home details
    """
    try:
        registry = _get_registry()
        home = registry.get_home(registry.local_home_id)
        
        if not home:
            return jsonify({
                "success": False,
                "error": "Local home not found",
            }), 500
        
        return jsonify({
            "success": True,
            "home": home.to_dict(),
        })
        
    except Exception as e:
        logger.exception("Failed to get local home")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
