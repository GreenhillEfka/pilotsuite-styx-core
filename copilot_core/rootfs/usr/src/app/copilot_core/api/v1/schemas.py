"""Pydantic v2 models for API v1 request validation."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ── Events / HA → Core contract ────────────────────────────────────

_ALLOWED_HA_EVENT_KINDS = ("state_changed", "call_service", "heartbeat")
_ALLOWED_HA_EVENT_SOURCES = ("ha", "home_assistant")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


class HAStateSnapshot(BaseModel):
    """Canonical before/after state snapshot."""

    model_config = ConfigDict(extra="allow")

    state: Any | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_attrs_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        attrs = data.get("attrs")
        if not isinstance(attrs, dict):
            attrs = data.get("attributes") if isinstance(data.get("attributes"), dict) else {}
        data["attrs"] = attrs
        return data


class HAServiceCall(BaseModel):
    """Canonical service-call payload."""

    model_config = ConfigDict(extra="allow")

    domain: str = ""
    service: str = ""
    entity_ids: list[str] = Field(default_factory=list)

    @field_validator("entity_ids", mode="before")
    @classmethod
    def _normalize_entity_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
        return []

    @model_validator(mode="before")
    @classmethod
    def _normalize_entity_id_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        entity_ids = data.get("entity_ids")
        if entity_ids is None:
            entity_ids = data.get("entity_id")
        if entity_ids is None:
            entity_ids = []
        data["entity_ids"] = entity_ids
        return data


class HAEventInput(BaseModel):
    """Uniform HA → Core event envelope accepted by /api/v1/events."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    v: int = 1
    id: str | None = None
    kind: Literal["state_changed", "call_service", "heartbeat"] = Field(
        validation_alias=AliasChoices("kind", "type")
    )
    src: Literal["ha", "home_assistant"] = Field(
        validation_alias=AliasChoices("src", "source")
    )
    ts: str
    entity_id: str | None = None
    domain: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    old: HAStateSnapshot | None = None
    new: HAStateSnapshot | None = None
    service: HAServiceCall | None = None
    zone_id: str | None = None
    zone_ids: list[str] = Field(default_factory=list)
    context_id: str | None = None
    context_parent_id: str | None = None
    context_user_id: str | None = None
    trigger: str | None = None
    entity_count: int | None = None

    @field_validator("ts")
    @classmethod
    def _validate_ts(cls, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("ts must not be empty")
        return value

    @field_validator("zone_ids", mode="before")
    @classmethod
    def _normalize_zone_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
        return []

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_shapes(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        data = dict(data)
        attrs = _as_dict(data.get("attributes"))
        habitat_event = _as_dict(data.get("habitat_event"))
        habitat_attrs = _as_dict(habitat_event.get("attributes"))
        habitat_context = _as_dict(habitat_event.get("context"))
        habitat_state = _as_dict(habitat_event.get("state"))
        neuron_input = _as_dict(data.get("neuron_input"))
        neuron_context = _as_dict(neuron_input.get("context"))
        neuron_metadata = _as_dict(neuron_input.get("metadata"))
        adapter = _as_dict(data.get("adapter"))

        kind = str(
            _first_present(
                data.get("kind"),
                data.get("type"),
                habitat_event.get("event_type"),
                adapter.get("event_type"),
                neuron_context.get("event_type"),
                "",
            )
        ).strip().lower()
        src = str(
            _first_present(
                data.get("src"),
                data.get("source"),
                habitat_context.get("source"),
                neuron_context.get("source"),
                adapter.get("name"),
                "",
            )
        ).strip().lower()

        if kind == "service_call":
            kind = "call_service"
        if kind:
            data["kind"] = kind

        if src in {"home_assistant", "homeassistant"}:
            src = "ha"
        if src:
            data["src"] = src

        if "ts" not in data or not str(data.get("ts") or "").strip():
            nested_ts = _first_present(habitat_context.get("ts"), neuron_context.get("ts"))
            if nested_ts is not None:
                data["ts"] = nested_ts

        if not data.get("entity_id"):
            entity_id = _first_present(
                habitat_event.get("entity_id"),
                neuron_input.get("entity_id"),
            )
            if entity_id is not None:
                data["entity_id"] = entity_id

        if not data.get("domain"):
            domain = _first_present(
                data.get("domain"),
                attrs.get("domain"),
                habitat_event.get("domain"),
                habitat_attrs.get("domain"),
                neuron_input.get("domain"),
                habitat_event.get("module_id"),
                neuron_input.get("module_id"),
            )
            if domain is not None:
                data["domain"] = domain

        zone_ids = data.get("zone_ids")
        if zone_ids is None:
            zone_ids = _first_present(
                attrs.get("zone_ids"),
                habitat_attrs.get("zone_ids"),
                neuron_metadata.get("zone_ids"),
            )
        zone_id = _first_present(
            data.get("zone_id"),
            habitat_event.get("zone_id"),
            neuron_input.get("zone_id"),
        )
        if zone_ids is None and zone_id is not None:
            zone_ids = [zone_id]
        if zone_ids is not None:
            data["zone_ids"] = zone_ids
        if zone_id is not None and not data.get("zone_id"):
            data["zone_id"] = zone_id

        if kind == "state_changed":
            old_state = _first_present(
                attrs.get("old_state"),
                habitat_attrs.get("old_state"),
                neuron_metadata.get("old_state"),
            )
            new_state = _first_present(
                attrs.get("new_state"),
                habitat_attrs.get("new_state"),
                neuron_metadata.get("new_state"),
                habitat_event.get("state"),
                neuron_input.get("value"),
            )
            state_attrs = _first_present(
                attrs.get("state_attributes"),
                attrs.get("new_attrs"),
                habitat_attrs.get("state_attributes"),
                habitat_attrs.get("new_attrs"),
                neuron_metadata.get("state_attributes"),
                {},
            )
            if "old" not in data:
                data["old"] = {
                    "state": old_state,
                    "attrs": attrs.get("old_attrs") or habitat_attrs.get("old_attrs") or {},
                }
            if "new" not in data:
                data["new"] = {
                    "state": new_state,
                    "attrs": state_attrs,
                }

        if kind == "call_service" and "service" not in data:
            entity_ids = _first_present(
                habitat_state.get("entity_ids"),
                habitat_attrs.get("entity_ids"),
                neuron_metadata.get("entity_ids"),
                attrs.get("entity_ids"),
                data.get("entity_id"),
                habitat_event.get("entity_id"),
                [],
            )
            service_payload = {
                "domain": _first_present(
                    data.get("domain"),
                    attrs.get("domain"),
                    habitat_state.get("domain"),
                    habitat_attrs.get("domain"),
                    neuron_input.get("domain"),
                    "",
                ) or "",
                "service": _first_present(
                    habitat_state.get("service"),
                    habitat_attrs.get("service"),
                    attrs.get("service"),
                    data.get("service"),
                    "",
                ) or "",
                "entity_ids": entity_ids,
            }
            data["service"] = service_payload

        return data

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "HAEventInput":
        if self.kind not in _ALLOWED_HA_EVENT_KINDS:
            raise ValueError(f"kind must be one of {_ALLOWED_HA_EVENT_KINDS}")

        if self.src not in _ALLOWED_HA_EVENT_SOURCES:
            raise ValueError(f"src must be one of {_ALLOWED_HA_EVENT_SOURCES}")

        if self.kind == "state_changed" and not self.entity_id:
            raise ValueError("entity_id is required for state_changed events")

        if self.kind == "call_service":
            service_domain = (self.service.domain if self.service else "").strip()
            service_name = (self.service.service if self.service else "").strip()
            if not service_domain or not service_name:
                raise ValueError("call_service events require service.domain and service.service")

        if self.zone_id and not self.zone_ids:
            self.zone_ids = [self.zone_id]
        if self.zone_ids and not self.zone_id:
            self.zone_id = self.zone_ids[0]

        return self


class EventItem(HAEventInput):
    """Backward-compatible alias for a single HA event envelope."""


class BatchEventPayload(BaseModel):
    """POST /api/v1/events body."""

    items: list[HAEventInput] = Field(default_factory=list, max_length=500)


class EventPayload(BaseModel):
    """Single event ingest (POST /events)."""

    entity_id: str | None = None
    domain: str | None = None
    event_type: str | None = None
    state: str | None = None
    old_state: str | None = None
    data: dict[str, Any] | None = None


class EventBatchPayload(BaseModel):
    """Batch event ingest (POST /events with items key)."""

    items: list[dict[str, Any]] = Field(..., min_length=1)


# ── Graph Operations ─────────────────────────────────────────────────

ALLOWED_EDGE_TYPES = {"observed_with", "controls"}


class GraphOpsRequest(BaseModel):
    """POST /graph/ops body."""

    op: Literal["touch_edge"]
    from_id: str = Field(..., alias="from", min_length=1)
    to_id: str = Field(..., alias="to", min_length=1)
    type: str = Field(..., min_length=1)
    delta: float = Field(default=1.0, ge=0.0, le=5.0)
    idempotency_key: str | None = None
    key: str | None = None
    id: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("type")
    @classmethod
    def validate_edge_type(cls, v: str) -> str:
        v = v.strip()
        if v not in ALLOWED_EDGE_TYPES:
            raise ValueError(f"edge_type_not_allowed: must be one of {sorted(ALLOWED_EDGE_TYPES)}")
        return v


# ── Tag Assignments ──────────────────────────────────────────────────

class TagAssignmentRequest(BaseModel):
    """POST /api/v1/tag-system/assignments body."""

    subject_id: str = Field(..., min_length=1)
    subject_kind: str = Field(..., min_length=1)
    tag_id: str = Field(..., min_length=1)
    source: str | None = None
    confidence: float | None = None
    meta: dict[str, Any] | None = None
    materialized: bool = False


# ── Vector / Embeddings ──────────────────────────────────────────────

class EmbeddingRequest(BaseModel):
    """POST /vector/embeddings body."""

    type: Literal["entity", "user_preference", "pattern"]
    id: str = Field(..., min_length=1)
    # entity fields
    domain: str | None = None
    area: str | None = None
    capabilities: list[str] | None = None
    tags: list[str] | None = None
    state: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    # user_preference fields
    preferences: dict[str, Any] | None = None
    # pattern fields
    pattern_type: str | None = None
    entities: list[str] | None = None
    conditions: dict[str, Any] | None = None
    confidence: float | None = None


class SimilarityRequest(BaseModel):
    """POST /vector/similarity body."""

    id1: str | None = None
    id2: str | None = None
    vector1: list[float] | None = None
    vector2: list[float] | None = None

    @field_validator("vector2")
    @classmethod
    def check_pair_provided(cls, v, info):
        values = info.data
        has_ids = values.get("id1") and values.get("id2")
        has_vectors = values.get("vector1") is not None and v is not None
        if not has_ids and not has_vectors:
            raise ValueError("Provide either id1/id2 or vector1/vector2")
        return v


class BulkEmbeddingRequest(BaseModel):
    """POST /vector/embeddings/bulk body."""

    entities: list[dict[str, Any]] = Field(default_factory=list)
    user_preferences: list[dict[str, Any]] = Field(default_factory=list)
    patterns: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("patterns")
    @classmethod
    def check_not_all_empty(cls, v, info):
        values = info.data
        if not values.get("entities") and not values.get("user_preferences") and not v:
            raise ValueError("No entries provided")
        return v


# ── Chat ────────────────────────────────────────────────────────────

class ChatRequestSchema(BaseModel):
    """POST /api/styx/chat body."""

    query: str = Field(..., min_length=1, max_length=10000)
    user_id: str = Field(default="anonymous", max_length=200)
    use_web: bool = False
    model: str = Field(default="qwen3.5:397b-cloud", max_length=100)
    conversation_id: str = Field(default="", max_length=200)

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be empty after stripping whitespace")
        return v


# ── Integration Feedback ────────────────────────────────────────────

class FeedbackRequestSchema(BaseModel):
    """POST /api/v1/integration/feedback body."""

    suggestion_id: str = Field(default="", max_length=200)
    accepted: bool
    related_entities: list[str] = Field(default_factory=list, max_length=50)
    pattern_key: str | None = Field(default=None, max_length=500)


# ── Automation ──────────────────────────────────────────────────────

class AutomationCreateSchema(BaseModel):
    """POST /api/v1/automations/create body."""

    antecedent: str = Field(..., min_length=1, max_length=2000)
    consequent: str = Field(..., min_length=1, max_length=2000)
    alias: str | None = Field(default=None, max_length=200)
