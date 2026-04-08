"""Pydantic v2 models for API v1 request validation."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ── Events ───────────────────────────────────────────────────────────

class EventItem(BaseModel):
    """A single event envelope in a batch."""
    entity_id: str | None = None
    domain: str | None = None
    event_type: str | None = Field(None, alias="event_type")
    data: dict[str, Any] | None = None


class BatchEventPayload(BaseModel):
    """POST /api/v1/events body."""
    items: list[dict[str, Any]] = Field(..., min_length=0, max_length=500)


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
