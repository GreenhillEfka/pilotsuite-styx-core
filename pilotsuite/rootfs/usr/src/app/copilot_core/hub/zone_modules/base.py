"""Base classes for self-describing zone automation modules."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ZoneModuleFieldSpec:
    """Specification for a single configurable field in a zone module.

    This is the self-describing schema that HA uses to dynamically
    generate Number/Switch/Select entities.
    """

    key: str                          # "brightness_target_pct"
    field_type: str                   # "bool" | "int" | "float" | "select"
    default: Any                      # 80
    label_de: str                     # "Ziel-Helligkeit"
    icon: str                         # "mdi:brightness-7"
    min_value: float | None = None    # 0
    max_value: float | None = None    # 100
    step: float | None = None         # 5
    unit: str | None = None           # "%"
    ha_platform: str = "number"       # "number" | "switch" | "select"
    options: list[str] | None = None  # For select fields

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Remove None values for cleaner API response
        return {k: v for k, v in d.items() if v is not None}


class ZoneModuleConfig(ABC):
    """Abstract base class for zone automation modules.

    Each module is self-describing: it declares its fields, icons,
    colors, and which entity roles/tags/domains it relates to.
    """

    MODULE_ID: str = ""               # "light"
    MODULE_NAME_DE: str = ""          # "Lichtsteuerung"
    MODULE_ICON: str = ""             # "mdi:lightbulb"
    MODULE_COLOR: str = ""            # "#fbbf24"
    RELEVANT_ROLES: list[str] = []    # ["lights"]
    RELEVANT_TAGS: list[str] = []     # ["licht"]
    RELEVANT_DOMAINS: list[str] = []  # ["light"]

    def __init__(self, enabled: bool = True, **kwargs: Any) -> None:
        self.enabled = enabled
        for spec in self.get_field_specs():
            if spec.key == "enabled":
                continue
            setattr(self, spec.key, kwargs.get(spec.key, spec.default))

    @classmethod
    @abstractmethod
    def get_field_specs(cls) -> list[ZoneModuleFieldSpec]:
        """Return the list of configurable fields for this module."""
        ...

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"enabled": self.enabled}
        for spec in self.get_field_specs():
            if spec.key == "enabled":
                continue
            result[spec.key] = getattr(self, spec.key, spec.default)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ZoneModuleConfig":
        kwargs: dict[str, Any] = {}
        for spec in cls.get_field_specs():
            if spec.key in data:
                kwargs[spec.key] = data[spec.key]
        kwargs["enabled"] = data.get("enabled", True)
        return cls(**kwargs)

    @classmethod
    def matches_entity(cls, entity_id: str, role: str = "", tags: list[str] | None = None) -> bool:
        """Check if an entity matches this module by role, tags, or domain."""
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        if domain in cls.RELEVANT_DOMAINS:
            return True
        if role and role in cls.RELEVANT_ROLES:
            return True
        if tags:
            for tag in tags:
                if tag in cls.RELEVANT_TAGS:
                    return True
        return False

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        """Return full self-describing schema for this module."""
        return {
            "module_id": cls.MODULE_ID,
            "name_de": cls.MODULE_NAME_DE,
            "icon": cls.MODULE_ICON,
            "color": cls.MODULE_COLOR,
            "relevant_roles": cls.RELEVANT_ROLES,
            "relevant_tags": cls.RELEVANT_TAGS,
            "relevant_domains": cls.RELEVANT_DOMAINS,
            "fields": [f.to_dict() for f in cls.get_field_specs()],
        }
