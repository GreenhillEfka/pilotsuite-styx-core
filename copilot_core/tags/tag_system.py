"""Simple tag system for repo-root compatibility tests."""
from __future__ import annotations

import fnmatch
import json
from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict, List, Set


class TagSystem:
    """In-memory entity tagging with small compatibility helpers."""

    def __init__(self):
        self._entity_tags: Dict[str, Set[str]] = defaultdict(set)
        self._tag_metadata: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self._auto_rules: List[Dict[str, Any]] = []

    def add_tag(self, entity_id: str, tag: str, metadata: Dict[str, Any] | None = None) -> bool:
        self._entity_tags[entity_id].add(tag)
        if metadata is not None:
            self._tag_metadata[entity_id][tag] = dict(metadata)
        self._apply_auto_rules(entity_id)
        return True

    def remove_tag(self, entity_id: str, tag: str) -> bool:
        if tag not in self._entity_tags.get(entity_id, set()):
            return False
        self._entity_tags[entity_id].discard(tag)
        self._tag_metadata.get(entity_id, {}).pop(tag, None)
        if not self._entity_tags[entity_id]:
            self._entity_tags.pop(entity_id, None)
            self._tag_metadata.pop(entity_id, None)
        return True

    def get_tags(self, entity_id: str) -> List[str]:
        return sorted(self._entity_tags.get(entity_id, set()))

    def query_by_tag(self, tag: str) -> List[str]:
        matches: List[str] = []
        wildcard = "*" in tag
        for entity_id, tags in self._entity_tags.items():
            if wildcard:
                if any(fnmatch.fnmatch(existing_tag, tag) for existing_tag in tags):
                    matches.append(entity_id)
            elif tag in tags:
                matches.append(entity_id)
        return sorted(matches)

    def query_by_tags(self, tags: List[str]) -> List[str]:
        required = list(tags)
        return sorted(
            entity_id
            for entity_id, entity_tags in self._entity_tags.items()
            if all(tag in entity_tags for tag in required)
        )

    def bulk_add_tag(self, entities: List[str], tag: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        for entity_id in entities:
            self.add_tag(entity_id, tag, metadata=metadata)
        return {"success": True, "tagged_count": len(entities), "tag": tag}

    def get_tag_metadata(self, entity_id: str, tag: str) -> Dict[str, Any] | None:
        metadata = self._tag_metadata.get(entity_id, {}).get(tag)
        return deepcopy(metadata) if metadata is not None else None

    def add_auto_rule(self, name: str, condition: Dict[str, Any], tags: List[str]) -> Dict[str, Any]:
        rule = {"name": name, "condition": dict(condition), "tags": list(tags)}
        self._auto_rules.append(rule)
        for entity_id in list(self._entity_tags.keys()):
            self._apply_auto_rules(entity_id)
        return {"success": True, "rule": name}

    def get_statistics(self) -> Dict[str, Any]:
        unique_tags = {tag for tags in self._entity_tags.values() for tag in tags}
        return {
            "total_tags": len(unique_tags),
            "total_entities": len(self._entity_tags),
            "total_assignments": sum(len(tags) for tags in self._entity_tags.values()),
            "auto_rules": len(self._auto_rules),
        }

    def export_to_json(self) -> str:
        payload = {
            "entity_tags": {entity_id: sorted(tags) for entity_id, tags in self._entity_tags.items()},
            "tag_metadata": self._tag_metadata,
            "auto_rules": self._auto_rules,
        }
        return json.dumps(payload, sort_keys=True)

    def import_from_json(self, payload: str) -> None:
        data = json.loads(payload)
        self.clear()
        for entity_id, tags in data.get("entity_tags", {}).items():
            self._entity_tags[entity_id] = set(tags)
        for entity_id, metadata in data.get("tag_metadata", {}).items():
            self._tag_metadata[entity_id] = dict(metadata)
        self._auto_rules = list(data.get("auto_rules", []))
        for entity_id in list(self._entity_tags.keys()):
            self._apply_auto_rules(entity_id)

    def clear(self) -> None:
        self._entity_tags.clear()
        self._tag_metadata.clear()
        self._auto_rules.clear()

    def _apply_auto_rules(self, entity_id: str) -> None:
        current_tags = self._entity_tags.get(entity_id, set())
        for rule in self._auto_rules:
            if self._rule_matches(entity_id, current_tags, rule.get("condition", {})):
                for auto_tag in rule.get("tags", []):
                    current_tags.add(auto_tag)
        if current_tags:
            self._entity_tags[entity_id] = current_tags

    def _rule_matches(self, entity_id: str, current_tags: Set[str], condition: Dict[str, Any]) -> bool:
        pattern = condition.get("entity_id_pattern")
        if pattern and not fnmatch.fnmatch(entity_id, pattern):
            return False
        room = condition.get("room")
        if room and room not in current_tags and f"room:{room}" not in current_tags:
            return False
        return True
