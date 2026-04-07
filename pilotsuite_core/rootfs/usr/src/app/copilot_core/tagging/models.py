"""Data structures for the tag system."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True)
class TagDisplay:
    """Localized display metadata for a tag."""

    names: Mapping[str, str] = field(default_factory=dict)
    descriptions: Mapping[str, str] = field(default_factory=dict)

    def get_name(self, lang: str, default: str | None = None) -> str | None:
        return self.names.get(lang) or default

    def get_description(self, lang: str, default: str | None = None) -> str | None:
        if lang in self.descriptions:
            return self.descriptions[lang]
        return default


@dataclass(frozen=True)
class TagGovernance:
    visibility: str = "public"
    source: str = "system"
    confidence: float | None = None
    pii_risk: str = "none"
    retention: str | None = None


@dataclass(frozen=True)
class TagHAConfig:
    materialize_as_label: bool = True
    label_slug: str | None = None


@dataclass(frozen=True)
class Tag:
    """Canonical representation of a tag."""

    id: str
    namespace: str
    facet: str
    key: str
    type: str = "tag"
    icon: str | None = None
    color: str | None = None
    display: TagDisplay = field(default_factory=TagDisplay)
    governance: TagGovernance = field(default_factory=TagGovernance)
    aliases: Sequence[str] = field(default_factory=tuple)
    ha: TagHAConfig = field(default_factory=TagHAConfig)

    def is_public(self) -> bool:
        return self.governance.visibility == "public"

    @property
    def materializes_in_ha(self) -> bool:
        return self.is_public() and self.ha.materialize_as_label
