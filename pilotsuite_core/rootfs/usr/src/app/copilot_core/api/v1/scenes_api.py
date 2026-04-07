"""
Scenes API v1 for PilotSuite Core.

REST API endpoints for scene management:
- CRUD operations for scenes
- Scene execution
- Scene templates and presets
- Multi-home scene sync
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

from ...scenes.scene_manager import SceneManager, Scene, SceneEntity, SceneAction, SceneActionType
from ...scenes.scene_executor import SceneExecutor, ExecutionMode

logger = logging.getLogger(__name__)

scenes_api_bp = Blueprint("scenes_api", __name__, url_prefix="/api/v1/scenes")

# Global scene manager instance (set during app initialization)
_scene_manager: Optional[SceneManager] = None
_scene_executor: Optional[SceneExecutor] = None


def set_scene_manager(manager: SceneManager) -> None:
    """Set the scene manager instance for API access."""
    global _scene_manager
    _scene_manager = manager
    logger.info("Scenes API: Manager set")


def set_scene_executor(executor: SceneExecutor) -> None:
    """Set the scene executor instance for API access."""
    global _scene_executor
    _scene_executor = executor
    logger.info("Scenes API: Executor set")


def _get_manager() -> SceneManager:
    """Get the scene manager, creating if needed."""
    global _scene_manager
    if _scene_manager is None:
        _scene_manager = SceneManager()
    return _scene_manager


def _get_executor() -> SceneExecutor:
    """Get the scene executor, creating if needed."""
    global _scene_executor
    if _scene_executor is None:
        _scene_executor = SceneExecutor()
    return _scene_executor


# =============================================================================
# Scene CRUD Endpoints
# =============================================================================

@scenes_api_bp.route("", methods=["GET"])
def list_scenes():
    """
    List all scenes with optional filters.
    
    Query Parameters:
        home_id: Filter by home ID
        zone_id: Filter by zone ID
        is_active: Filter by active status (true/false)
        is_favorite: Filter by favorite status (true/false)
    
    Returns:
        JSON response with list of scenes
    """
    try:
        manager = _get_manager()
        
        home_id = request.args.get("home_id")
        zone_id = request.args.get("zone_id")
        is_active = request.args.get("is_active")
        is_favorite = request.args.get("is_favorite")
        
        # Parse boolean filters
        active_filter = None
        if is_active is not None:
            active_filter = is_active.lower() == "true"
        
        favorite_filter = None
        if is_favorite is not None:
            favorite_filter = is_favorite.lower() == "true"
        
        scenes = manager.get_scenes(
            home_id=home_id,
            zone_id=zone_id,
            is_active=active_filter,
            is_favorite=favorite_filter,
        )
        
        return jsonify({
            "success": True,
            "scenes": [s.to_dict() for s in scenes],
            "count": len(scenes),
        })
        
    except Exception as e:
        logger.exception("Failed to list scenes")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("/<scene_id>", methods=["GET"])
def get_scene(scene_id: str):
    """
    Get a specific scene by ID.
    
    Path Parameters:
        scene_id: Scene ID
    
    Returns:
        JSON response with scene details
    """
    try:
        manager = _get_manager()
        scene = manager.get_scene(scene_id)
        
        if not scene:
            return jsonify({
                "success": False,
                "error": "Scene not found",
            }), 404
        
        return jsonify({
            "success": True,
            "scene": scene.to_dict(),
        })
        
    except Exception as e:
        logger.exception(f"Failed to get scene {scene_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("", methods=["POST"])
def create_scene():
    """
    Create a new scene.
    
    Request Body:
        name (required): Scene name
        home_id (optional): Home ID (default: "default")
        description (optional): Scene description
        zone_ids (optional): List of zone IDs
        entities (optional): List of entity states
        actions (optional): List of actions
        triggers (optional): List of triggers
        metadata (optional): Additional metadata
        icon (optional): Icon name/URL
        color (optional): Color hex code
        created_by (optional): User ID of creator
    
    Returns:
        JSON response with created scene
    """
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        if not data.get("name"):
            return jsonify({
                "success": False,
                "error": "name is required",
            }), 400
        
        manager = _get_manager()
        
        # Parse entities
        entities = []
        for e in data.get("entities", []):
            entities.append(SceneEntity(
                entity_id=e["entity_id"],
                entity_type=e["entity_type"],
                state=e["state"],
                attributes=e.get("attributes", {}),
                friendly_name=e.get("friendly_name"),
            ))
        
        # Parse actions
        actions = []
        for a in data.get("actions", []):
            actions.append(SceneAction(
                action_id=a.get("action_id", f"action_{len(actions)}"),
                action_type=SceneActionType(a["action_type"]),
                entity_id=a["entity_id"],
                parameters=a.get("parameters", {}),
                order=a.get("order", len(actions)),
                delay_seconds=a.get("delay_seconds", 0.0),
                enabled=a.get("enabled", True),
            ))
        
        scene = manager.create_scene(
            name=data["name"],
            home_id=data.get("home_id", "default"),
            description=data.get("description"),
            zone_ids=data.get("zone_ids", []),
            entities=entities or None,
            actions=actions or None,
            triggers=data.get("triggers", []),
            metadata=data.get("metadata", {}),
            icon=data.get("icon"),
            color=data.get("color"),
            created_by=data.get("created_by"),
        )
        
        return jsonify({
            "success": True,
            "scene": scene.to_dict(),
            "message": f"Scene '{scene.name}' created",
        }), 201
        
    except Exception as e:
        logger.exception("Failed to create scene")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("/<scene_id>", methods=["PUT"])
def update_scene(scene_id: str):
    """
    Update an existing scene.
    
    Path Parameters:
        scene_id: Scene ID to update
    
    Request Body:
        name (optional): New name
        description (optional): New description
        zone_ids (optional): New zone IDs
        entities (optional): New entity states
        actions (optional): New actions
        triggers (optional): New triggers
        metadata (optional): New metadata
        icon (optional): New icon
        color (optional): New color
        is_favorite (optional): Favorite status
        is_active (optional): Active status
    
    Returns:
        JSON response with updated scene
    """
    try:
        data = request.get_json() or {}
        manager = _get_manager()
        
        # Parse entities if provided
        entities = None
        if "entities" in data:
            entities = [
                SceneEntity(
                    entity_id=e["entity_id"],
                    entity_type=e["entity_type"],
                    state=e["state"],
                    attributes=e.get("attributes", {}),
                    friendly_name=e.get("friendly_name"),
                )
                for e in data["entities"]
            ]
        
        # Parse actions if provided
        actions = None
        if "actions" in data:
            actions = [
                SceneAction(
                    action_id=a.get("action_id", f"action_{i}"),
                    action_type=SceneActionType(a["action_type"]),
                    entity_id=a["entity_id"],
                    parameters=a.get("parameters", {}),
                    order=a.get("order", i),
                    delay_seconds=a.get("delay_seconds", 0.0),
                    enabled=a.get("enabled", True),
                )
                for i, a in enumerate(data["actions"])
            ]
        
        scene = manager.update_scene(
            scene_id=scene_id,
            name=data.get("name"),
            description=data.get("description"),
            zone_ids=data.get("zone_ids"),
            entities=entities,
            actions=actions,
            triggers=data.get("triggers"),
            metadata=data.get("metadata"),
            icon=data.get("icon"),
            color=data.get("color"),
            is_favorite=data.get("is_favorite"),
            is_active=data.get("is_active"),
        )
        
        if not scene:
            return jsonify({
                "success": False,
                "error": "Scene not found",
            }), 404
        
        return jsonify({
            "success": True,
            "scene": scene.to_dict(),
            "message": f"Scene '{scene.name}' updated",
        })
        
    except Exception as e:
        logger.exception(f"Failed to update scene {scene_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("/<scene_id>", methods=["DELETE"])
def delete_scene(scene_id: str):
    """
    Delete a scene.
    
    Path Parameters:
        scene_id: Scene ID to delete
    
    Returns:
        JSON response with deletion result
    """
    try:
        manager = _get_manager()
        
        if not manager.delete_scene(scene_id):
            return jsonify({
                "success": False,
                "error": "Scene not found",
            }), 404
        
        return jsonify({
            "success": True,
            "message": "Scene deleted",
        })
        
    except Exception as e:
        logger.exception(f"Failed to delete scene {scene_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# =============================================================================
# Scene Execution Endpoints
# =============================================================================

@scenes_api_bp.route("/<scene_id>/execute", methods=["POST"])
def execute_scene(scene_id: str):
    """
    Execute a scene.
    
    Path Parameters:
        scene_id: Scene ID to execute
    
    Request Body:
        mode (optional): Execution mode (sequential, parallel, grouped)
        dry_run (optional): If true, log only without executing
        user_id (optional): User ID triggering execution
        triggered_by (optional): What triggered this (manual, schedule, event)
    
    Returns:
        JSON response with execution result
    """
    try:
        data = request.get_json() or {}
        manager = _get_manager()
        executor = _get_executor()
        
        scene = manager.get_scene(scene_id)
        if not scene:
            return jsonify({
                "success": False,
                "error": "Scene not found",
            }), 404
        
        # Parse execution mode
        mode_str = data.get("mode", "sequential").lower()
        mode_map = {
            "sequential": ExecutionMode.SEQUENTIAL,
            "parallel": ExecutionMode.PARALLEL,
            "grouped": ExecutionMode.GROUPED,
        }
        mode = mode_map.get(mode_str, ExecutionMode.SEQUENTIAL)
        
        # Execute scene (async, but we wait for result in this simple implementation)
        import asyncio
        
        async def run():
            return await executor.execute(
                scene=scene,
                mode=mode,
                dry_run=data.get("dry_run", False),
                user_id=data.get("user_id"),
                triggered_by=data.get("triggered_by", "manual"),
            )
        
        # Run in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(run())
        
        # Record execution
        manager.record_execution(scene_id)
        
        return jsonify({
            "success": result.status.value == "completed",
            "execution": result.to_dict(),
        })
        
    except Exception as e:
        logger.exception(f"Failed to execute scene {scene_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("/executions/<execution_id>", methods=["GET"])
def get_execution(execution_id: str):
    """
    Get execution status by ID.
    
    Path Parameters:
        execution_id: Execution ID
    
    Returns:
        JSON response with execution details
    """
    try:
        executor = _get_executor()
        context = executor.get_execution(execution_id)
        
        if not context:
            return jsonify({
                "success": False,
                "error": "Execution not found",
            }), 404
        
        return jsonify({
            "success": True,
            "execution": {
                "execution_id": context.execution_id,
                "scene_id": context.scene.scene_id,
                "scene_name": context.scene.name,
                "status": context.status.value,
                "started_at": context.started_at.isoformat() if context.started_at else None,
                "completed_at": context.completed_at.isoformat() if context.completed_at else None,
            },
        })
        
    except Exception as e:
        logger.exception(f"Failed to get execution {execution_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("/executions/<execution_id>/cancel", methods=["POST"])
def cancel_execution(execution_id: str):
    """
    Cancel a running execution.
    
    Path Parameters:
        execution_id: Execution ID to cancel
    
    Returns:
        JSON response with cancellation result
    """
    try:
        executor = _get_executor()
        
        if not executor.cancel_execution(execution_id):
            return jsonify({
                "success": False,
                "error": "Execution not found or already completed",
            }), 404
        
        return jsonify({
            "success": True,
            "message": "Execution cancelled",
        })
        
    except Exception as e:
        logger.exception(f"Failed to cancel execution {execution_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# =============================================================================
# Scene Utility Endpoints
# =============================================================================

@scenes_api_bp.route("/<scene_id>/favorite", methods=["POST"])
def toggle_favorite(scene_id: str):
    """Toggle favorite status of a scene."""
    try:
        manager = _get_manager()
        scene = manager.toggle_favorite(scene_id)
        
        if not scene:
            return jsonify({
                "success": False,
                "error": "Scene not found",
            }), 404
        
        return jsonify({
            "success": True,
            "scene": scene.to_dict(),
            "is_favorite": scene.is_favorite,
        })
        
    except Exception as e:
        logger.exception(f"Failed to toggle favorite for scene {scene_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("/<scene_id>/activate", methods=["POST"])
def activate_scene(scene_id: str):
    """Activate a scene."""
    try:
        manager = _get_manager()
        scene = manager.activate_scene(scene_id)
        
        if not scene:
            return jsonify({
                "success": False,
                "error": "Scene not found",
            }), 404
        
        return jsonify({
            "success": True,
            "scene": scene.to_dict(),
        })
        
    except Exception as e:
        logger.exception(f"Failed to activate scene {scene_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("/<scene_id>/deactivate", methods=["POST"])
def deactivate_scene(scene_id: str):
    """Deactivate a scene."""
    try:
        manager = _get_manager()
        scene = manager.deactivate_scene(scene_id)
        
        if not scene:
            return jsonify({
                "success": False,
                "error": "Scene not found",
            }), 404
        
        return jsonify({
            "success": True,
            "scene": scene.to_dict(),
        })
        
    except Exception as e:
        logger.exception(f"Failed to deactivate scene {scene_id}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("/presets", methods=["GET"])
def get_presets():
    """Get built-in scene presets."""
    presets = [
        {"preset_id": "morning", "name": "Morning", "icon": "mdi:weather-sunset-up"},
        {"preset_id": "day", "name": "Day", "icon": "mdi:white-balance-sunny"},
        {"preset_id": "evening", "name": "Evening", "icon": "mdi:weather-sunset-down"},
        {"preset_id": "night", "name": "Night", "icon": "mdi:weather-night"},
        {"preset_id": "movie", "name": "Movie", "icon": "mdi:movie-open"},
        {"preset_id": "party", "name": "Party", "icon": "mdi:party-popper"},
        {"preset_id": "focus", "name": "Focus", "icon": "mdi:head-lightbulb"},
        {"preset_id": "away", "name": "Away", "icon": "mdi:home-export-outline"},
    ]
    return jsonify({"presets": presets})


@scenes_api_bp.route("/export", methods=["GET"])
def export_scenes():
    """Export scenes for backup."""
    try:
        manager = _get_manager()
        home_id = request.args.get("home_id")
        
        export_data = manager.export_scenes(home_id=home_id)
        
        return jsonify({
            "success": True,
            "export": export_data,
        })
        
    except Exception as e:
        logger.exception("Failed to export scenes")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("/import", methods=["POST"])
def import_scenes():
    """Import scenes from backup."""
    try:
        data = request.get_json() or {}
        manager = _get_manager()
        
        export_data = data.get("export", {})
        home_id = data.get("home_id")
        merge = data.get("merge", True)
        
        id_mapping = manager.import_scenes(export_data, home_id=home_id, merge=merge)
        
        return jsonify({
            "success": True,
            "imported_count": len(id_mapping),
            "id_mapping": id_mapping,
        })
        
    except Exception as e:
        logger.exception("Failed to import scenes")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scenes_api_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get scene statistics."""
    try:
        manager = _get_manager()
        home_id = request.args.get("home_id")
        
        all_scenes = manager.get_scenes(home_id=home_id)
        favorites = [s for s in all_scenes if s.is_favorite]
        active = [s for s in all_scenes if s.is_active]
        
        return jsonify({
            "success": True,
            "stats": {
                "total": len(all_scenes),
                "favorites": len(favorites),
                "active": len(active),
                "inactive": len(all_scenes) - len(active),
            },
        })
        
    except Exception as e:
        logger.exception("Failed to get scene stats")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
