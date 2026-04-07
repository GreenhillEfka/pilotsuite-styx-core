"""
Scene Manager for PilotSuite Core.

Handles scene CRUD operations, storage, and retrieval.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SceneActionType(str, Enum):
    """Types of scene actions."""
    LIGHT_ON = "light_on"
    LIGHT_OFF = "light_off"
    LIGHT_SET = "light_set"
    SWITCH_ON = "switch_on"
    SWITCH_OFF = "switch_off"
    CLIMATE_SET = "climate_set"
    COVER_OPEN = "cover_open"
    COVER_CLOSE = "cover_close"
    COVER_SET = "cover_set"
    MEDIA_PLAY = "media_play"
    MEDIA_PAUSE = "media_pause"
    MEDIA_VOLUME = "media_volume"
    SCRIPT_EXECUTE = "script_execute"
    SERVICE_CALL = "service_call"
    DELAY = "delay"
    CONDITION = "condition"


class SceneTriggerType(str, Enum):
    """Types of scene triggers."""
    MANUAL = "manual"
    SCHEDULE = "schedule"
    EVENT = "event"
    PRESENCE = "presence"
    SUN = "sun"
    STATE = "state"


@dataclass
class SceneAction:
    """
    A single action within a scene.
    """
    action_id: str
    action_type: SceneActionType
    entity_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    order: int = 0
    delay_seconds: float = 0.0
    enabled: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "entity_id": self.entity_id,
            "parameters": self.parameters,
            "order": self.order,
            "delay_seconds": self.delay_seconds,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SceneAction:
        """Create from dictionary."""
        return cls(
            action_id=data["action_id"],
            action_type=SceneActionType(data["action_type"]),
            entity_id=data["entity_id"],
            parameters=data.get("parameters", {}),
            order=data.get("order", 0),
            delay_seconds=data.get("delay_seconds", 0.0),
            enabled=data.get("enabled", True),
        )


@dataclass
class SceneEntity:
    """
    An entity reference in a scene with its target state.
    """
    entity_id: str
    entity_type: str  # light, switch, climate, cover, media_player, etc.
    state: str  # on, off, or specific value
    attributes: Dict[str, Any] = field(default_factory=dict)
    friendly_name: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "state": self.state,
            "attributes": self.attributes,
            "friendly_name": self.friendly_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SceneEntity:
        """Create from dictionary."""
        return cls(
            entity_id=data["entity_id"],
            entity_type=data["entity_type"],
            state=data["state"],
            attributes=data.get("attributes", {}),
            friendly_name=data.get("friendly_name"),
        )


@dataclass
class Scene:
    """
    A scene definition containing entities and actions.
    """
    scene_id: str
    name: str
    description: Optional[str] = None
    home_id: str = "default"
    zone_ids: List[str] = field(default_factory=list)
    entities: List[SceneEntity] = field(default_factory=list)
    actions: List[SceneAction] = field(default_factory=list)
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    icon: Optional[str] = None
    color: Optional[str] = None
    is_favorite: bool = False
    is_active: bool = True
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    last_executed_at: Optional[datetime] = None
    execution_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "description": self.description,
            "home_id": self.home_id,
            "zone_ids": self.zone_ids,
            "entities": [e.to_dict() for e in self.entities],
            "actions": [a.to_dict() for a in self.actions],
            "triggers": self.triggers,
            "metadata": self.metadata,
            "icon": self.icon,
            "color": self.color,
            "is_favorite": self.is_favorite,
            "is_active": self.is_active,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None,
            "execution_count": self.execution_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Scene:
        """Create from dictionary."""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        last_executed_at = data.get("last_executed_at")

        return cls(
            scene_id=data["scene_id"],
            name=data["name"],
            description=data.get("description"),
            home_id=data.get("home_id", "default"),
            zone_ids=data.get("zone_ids", []),
            entities=[SceneEntity.from_dict(e) for e in data.get("entities", [])],
            actions=[SceneAction.from_dict(a) for a in data.get("actions", [])],
            triggers=data.get("triggers", []),
            metadata=data.get("metadata", {}),
            icon=data.get("icon"),
            color=data.get("color"),
            is_favorite=data.get("is_favorite", False),
            is_active=data.get("is_active", True),
            version=data.get("version", 1),
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(updated_at) if updated_at else datetime.now(timezone.utc),
            created_by=data.get("created_by"),
            last_executed_at=datetime.fromisoformat(last_executed_at) if last_executed_at else None,
            execution_count=data.get("execution_count", 0),
        )


class SceneManager:
    """
    Manages scene CRUD operations and persistence.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the scene manager.

        Args:
            storage_path: Path to JSON file for persistence. If None, uses memory-only storage.
        """
        self._scenes: Dict[str, Scene] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        self._lock = __import__("threading").Lock()
        
        if self._storage_path:
            self._load()
            logger.info(f"SceneManager initialized with storage: {self._storage_path}")
        else:
            logger.info("SceneManager initialized (memory-only)")

    def _load(self) -> None:
        """Load scenes from storage."""
        if not self._storage_path or not self._storage_path.exists():
            return

        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for scene_data in data.get("scenes", []):
                scene = Scene.from_dict(scene_data)
                self._scenes[scene.scene_id] = scene
            
            logger.info(f"Loaded {len(self._scenes)} scenes from storage")
        except Exception as e:
            logger.error(f"Failed to load scenes: {e}")

    def _save(self) -> None:
        """Save scenes to storage."""
        if not self._storage_path:
            return

        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "scenes": [s.to_dict() for s in self._scenes.values()],
            }
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            logger.debug(f"Saved {len(self._scenes)} scenes to storage")
        except Exception as e:
            logger.error(f"Failed to save scenes: {e}")

    def create_scene(
        self,
        name: str,
        home_id: str = "default",
        description: Optional[str] = None,
        zone_ids: Optional[List[str]] = None,
        entities: Optional[List[SceneEntity]] = None,
        actions: Optional[List[SceneAction]] = None,
        triggers: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Scene:
        """
        Create a new scene.

        Args:
            name: Scene name (required)
            home_id: Home identifier
            description: Optional description
            zone_ids: List of zone IDs this scene applies to
            entities: List of entity states to restore
            actions: List of actions to execute
            triggers: List of trigger configurations
            metadata: Additional metadata
            icon: Icon name/URL
            color: Color hex code
            created_by: User ID of creator

        Returns:
            The created Scene object
        """
        with self._lock:
            scene_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            scene = Scene(
                scene_id=scene_id,
                name=name,
                description=description,
                home_id=home_id,
                zone_ids=zone_ids or [],
                entities=entities or [],
                actions=actions or [],
                triggers=triggers or [],
                metadata=metadata or {},
                icon=icon,
                color=color,
                is_favorite=False,
                is_active=True,
                version=1,
                created_at=now,
                updated_at=now,
                created_by=created_by,
            )

            self._scenes[scene_id] = scene
            self._save()
            logger.info(f"Created scene '{name}' (id={scene_id})")
            return scene

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        """Get a scene by ID."""
        return self._scenes.get(scene_id)

    def get_scenes(
        self,
        home_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_favorite: Optional[bool] = None,
    ) -> List[Scene]:
        """
        Get scenes with optional filters.

        Args:
            home_id: Filter by home ID
            zone_id: Filter by zone ID (scenes containing this zone)
            is_active: Filter by active status
            is_favorite: Filter by favorite status

        Returns:
            List of matching scenes
        """
        with self._lock:
            results = list(self._scenes.values())

            if home_id is not None:
                results = [s for s in results if s.home_id == home_id]
            if zone_id is not None:
                results = [s for s in results if zone_id in s.zone_ids]
            if is_active is not None:
                results = [s for s in results if s.is_active == is_active]
            if is_favorite is not None:
                results = [s for s in results if s.is_favorite == is_favorite]

            return sorted(results, key=lambda s: s.name.lower())

    def update_scene(
        self,
        scene_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        zone_ids: Optional[List[str]] = None,
        entities: Optional[List[SceneEntity]] = None,
        actions: Optional[List[SceneAction]] = None,
        triggers: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        is_favorite: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Scene]:
        """
        Update an existing scene.

        Args:
            scene_id: Scene ID to update
            **kwargs: Fields to update (only provided fields are changed)

        Returns:
            Updated Scene object, or None if not found
        """
        with self._lock:
            scene = self._scenes.get(scene_id)
            if not scene:
                logger.warning(f"Scene not found: {scene_id}")
                return None

            now = datetime.now(timezone.utc)

            if name is not None:
                scene.name = name
            if description is not None:
                scene.description = description
            if zone_ids is not None:
                scene.zone_ids = zone_ids
            if entities is not None:
                scene.entities = entities
            if actions is not None:
                scene.actions = actions
            if triggers is not None:
                scene.triggers = triggers
            if metadata is not None:
                scene.metadata = metadata
            if icon is not None:
                scene.icon = icon
            if color is not None:
                scene.color = color
            if is_favorite is not None:
                scene.is_favorite = is_favorite
            if is_active is not None:
                scene.is_active = is_active

            scene.updated_at = now
            scene.version += 1

            self._save()
            logger.info(f"Updated scene '{scene.name}' (id={scene_id}, version={scene.version})")
            return scene

    def delete_scene(self, scene_id: str) -> bool:
        """
        Delete a scene.

        Args:
            scene_id: Scene ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if scene_id not in self._scenes:
                logger.warning(f"Scene not found for deletion: {scene_id}")
                return False

            scene = self._scenes.pop(scene_id)
            self._save()
            logger.info(f"Deleted scene '{scene.name}' (id={scene_id})")
            return True

    def toggle_favorite(self, scene_id: str) -> Optional[Scene]:
        """Toggle favorite status of a scene."""
        with self._lock:
            scene = self._scenes.get(scene_id)
            if not scene:
                return None

            scene.is_favorite = not scene.is_favorite
            scene.updated_at = datetime.now(timezone.utc)
            scene.version += 1
            self._save()
            return scene

    def activate_scene(self, scene_id: str) -> Optional[Scene]:
        """Activate a scene."""
        return self.update_scene(scene_id, is_active=True)

    def deactivate_scene(self, scene_id: str) -> Optional[Scene]:
        """Deactivate a scene."""
        return self.update_scene(scene_id, is_active=False)

    def record_execution(self, scene_id: str) -> None:
        """Record that a scene was executed."""
        with self._lock:
            scene = self._scenes.get(scene_id)
            if scene:
                scene.last_executed_at = datetime.now(timezone.utc)
                scene.execution_count += 1
                self._save()

    def get_scene_count(self, home_id: Optional[str] = None) -> int:
        """Get total scene count, optionally filtered by home."""
        if home_id is None:
            return len(self._scenes)
        return len([s for s in self._scenes.values() if s.home_id == home_id])

    def export_scenes(self, home_id: Optional[str] = None) -> Dict[str, Any]:
        """Export scenes as a dictionary for backup/transfer."""
        with self._lock:
            scenes = self.get_scenes(home_id=home_id)
            return {
                "export_version": 1,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "home_id": home_id,
                "scenes": [s.to_dict() for s in scenes],
            }

    def import_scenes(
        self,
        export_data: Dict[str, Any],
        home_id: Optional[str] = None,
        merge: bool = True,
    ) -> Dict[str, str]:
        """
        Import scenes from export data.

        Args:
            export_data: Export dictionary from export_scenes()
            home_id: Override home_id for imported scenes
            merge: If True, merge with existing; if False, replace

        Returns:
            Mapping of old scene_id to new scene_id
        """
        id_mapping = {}
        
        with self._lock:
            if not merge:
                self._scenes.clear()

            for scene_data in export_data.get("scenes", []):
                old_id = scene_data["scene_id"]
                new_id = str(uuid.uuid4())
                scene_data["scene_id"] = new_id
                
                if home_id:
                    scene_data["home_id"] = home_id
                
                scene = Scene.from_dict(scene_data)
                self._scenes[new_id] = scene
                id_mapping[old_id] = new_id

            self._save()
            logger.info(f"Imported {len(id_mapping)} scenes")

        return id_mapping

    def find_scenes_by_entity(self, entity_id: str) -> List[Scene]:
        """Find all scenes that reference a specific entity."""
        with self._lock:
            return [
                s for s in self._scenes.values()
                if any(e.entity_id == entity_id for e in s.entities)
            ]

    def get_scenes_by_home(self, home_id: str) -> List[Scene]:
        """Get all scenes for a specific home."""
        return self.get_scenes(home_id=home_id)

    def get_favorite_scenes(self, home_id: Optional[str] = None) -> List[Scene]:
        """Get all favorite scenes."""
        return self.get_scenes(home_id=home_id, is_favorite=True)
