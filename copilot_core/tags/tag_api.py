"""Small tag API wrapper for repo-root compatibility tests."""
from __future__ import annotations

from typing import Any, Dict

from .tag_system import TagSystem


class TagAPI:
    """Dict-based API facade over TagSystem."""

    def __init__(self):
        self._system = TagSystem()

    def add_tag(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = payload["entity_id"]
        tag = payload["tag"]
        metadata = payload.get("metadata")
        success = self._system.add_tag(entity_id, tag, metadata=metadata)
        return {"success": success, "entity_id": entity_id, "tag": tag}

    def get_tags(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = payload["entity_id"]
        return {"success": True, "entity_id": entity_id, "tags": self._system.get_tags(entity_id)}

    def bulk_add_tag(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        entities = payload["entities"]
        tag = payload["tag"]
        metadata = payload.get("metadata")
        return self._system.bulk_add_tag(entities, tag, metadata=metadata)

    def cleanup(self) -> None:
        self._system.clear()
