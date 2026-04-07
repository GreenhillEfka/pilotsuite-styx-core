"""YAML-backed tag registry loader."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

try:  # pragma: no cover - optional dependency
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None

from .models import Tag, TagDisplay, TagGovernance, TagHAConfig

_TAG_ID_RE = re.compile(r"^[a-z0-9_-]+(\.[a-z0-9_-]+)+$")
_HEX_COLOR_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


class TagRegistryError(RuntimeError):
    """Raised when the registry payload is invalid."""


class TagRegistry:
    """In-memory view of the canonical tags registry."""

    def __init__(
        self,
        *,
        schema_version: str,
        reserved_namespaces: Iterable[str],
        tags: Iterable[Tag],
        source_path: Path | None = None,
    ) -> None:
        self.schema_version = schema_version
        self.source_path = source_path
        self._reserved_namespaces = tuple(sorted(reserved_namespaces))
        self._tags: dict[str, Tag] = {}
        self._aliases: dict[str, str] = {}

        for tag in tags:
            if tag.id in self._tags:
                raise TagRegistryError(f"Duplicate tag id: {tag.id}")
            self._tags[tag.id] = tag
            self._aliases[tag.id] = tag.id
            for alias in tag.aliases:
                if alias in self._aliases:
                    raise TagRegistryError(
                        f"Alias '{alias}' defined multiple times (tag {tag.id})"
                    )
                self._aliases[alias] = tag.id

    @classmethod
    def from_file(cls, path: str | Path) -> "TagRegistry":
        text = Path(path).read_text(encoding="utf-8")
        payload = _load_payload(text)
        return cls.from_dict(payload, source_path=Path(path))

    @classmethod
    def from_dict(cls, payload: dict, *, source_path: Path | None = None) -> "TagRegistry":
        if not isinstance(payload, dict):
            raise TagRegistryError("Registry payload must be a mapping")

        version = str(payload.get("schema_version", "")).strip()
        if not version:
            raise TagRegistryError("schema_version is required")

        reserved = payload.get("reserved_namespaces", []) or []
        if not isinstance(reserved, list):
            raise TagRegistryError("reserved_namespaces must be a list")

        tags_payload = payload.get("tags", [])
        if not isinstance(tags_payload, list):
            raise TagRegistryError("tags must be a list")

        tags: list[Tag] = []
        for entry in tags_payload:
            tags.append(_parse_tag(entry))

        return cls(
            schema_version=version,
            reserved_namespaces=reserved,
            tags=tags,
            source_path=source_path,
        )

    def get(self, tag_id: str) -> Tag | None:
        canonical = self._aliases.get(tag_id)
        if not canonical:
            return None
        return self._tags.get(canonical)

    def all(self) -> list[Tag]:
        return sorted(self._tags.values(), key=lambda t: t.id)

    def __contains__(self, tag_id: str) -> bool:  # pragma: no cover - trivial
        return self.get(tag_id) is not None

    def namespaces(self) -> set[str]:
        return {tag.namespace for tag in self._tags.values()}

    def reserved_namespaces(self) -> tuple[str, ...]:
        return self._reserved_namespaces


def _load_payload(text: str) -> dict:
    if yaml is not None:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise TagRegistryError("Tag registry must be a mapping at top level")
    return data


def _parse_tag(entry: dict) -> Tag:
    if not isinstance(entry, dict):
        raise TagRegistryError("tag entry must be a mapping")

    tag_id = str(entry.get("id", "")).strip()
    if not tag_id:
        raise TagRegistryError("tag id is required")
    if not _TAG_ID_RE.match(tag_id):
        raise TagRegistryError(f"invalid tag id '{tag_id}'")

    parts = tag_id.split(".")
    if len(parts) < 3:
        raise TagRegistryError(
            f"tag id '{tag_id}' must contain namespace, facet, and key segments"
        )
    namespace = parts[0]
    facet = parts[1]
    key = ".".join(parts[2:])

    aliases = tuple(str(alias).strip() for alias in entry.get("aliases", []) if alias)
    for alias in aliases:
        if not _TAG_ID_RE.match(alias):
            raise TagRegistryError(f"invalid alias '{alias}' for tag {tag_id}")

    display_section = entry.get("display", {}) or {}
    description_section = entry.get("description", {}) or {}
    if not isinstance(display_section, dict) or not isinstance(description_section, dict):
        raise TagRegistryError(f"display/description must be mappings ({tag_id})")

    display = TagDisplay(names=display_section, descriptions=description_section)

    governance_data = entry.get("governance", {}) or {}
    if not isinstance(governance_data, dict):
        raise TagRegistryError(f"governance must be a mapping ({tag_id})")
    governance = TagGovernance(
        visibility=str(governance_data.get("visibility", "public")),
        source=str(governance_data.get("source", "system")),
        confidence=governance_data.get("confidence"),
        pii_risk=str(governance_data.get("pii_risk", "none")),
        retention=governance_data.get("retention"),
    )

    ha_data = entry.get("ha", {}) or {}
    if not isinstance(ha_data, dict):
        raise TagRegistryError(f"ha config must be a mapping ({tag_id})")
    ha = TagHAConfig(
        materialize_as_label=bool(ha_data.get("materialize_as_label", True)),
        label_slug=_normalize_label_slug(ha_data.get("label_slug"), tag_id),
    )

    color = entry.get("color")
    if color is not None:
        color = str(color).strip()
        if not _HEX_COLOR_RE.match(color):
            raise TagRegistryError(f"invalid color '{color}' for tag {tag_id}")
        if not color.startswith("#"):
            color = f"#{color}"

    tag = Tag(
        id=tag_id,
        namespace=namespace,
        facet=facet,
        key=key,
        type=str(entry.get("type", "tag")),
        icon=str(entry.get("icon")) if entry.get("icon") else None,
        color=color,
        display=display,
        governance=governance,
        aliases=aliases,
        ha=ha,
    )

    return tag


def _normalize_label_slug(slug: str | None, tag_id: str) -> str:
    base = slug or tag_id
    transformed = base.replace(".", "_")
    return re.sub(r"[^a-z0-9_]+", "_", transformed)
