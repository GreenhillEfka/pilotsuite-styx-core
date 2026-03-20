"""Tag System API (FastAPI)

Implements:
- Tag creation / listing / deletion
- Tag ↔ Zone mapping (Zone-Taxonomy + RAUM_REGISTRY integration)
- Tag ↔ Entity assignments
- Bulk tag operations

This module keeps an in-memory store by default. It is intentionally lightweight
for local Core runtime usage and testability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import logging
import re
from threading import RLock
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from copilot_core.homeassistant.habitus_zones import HABITUS_ZONES, ZoneType, get_all_zones
from copilot_core.homeassistant.zone_matcher import match_room

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tags", tags=["tags"])


# =============================================================================
# Zone-Taxonomy + RAUM_REGISTRY
# =============================================================================


def _normalize_key(value: str) -> str:
    """Normalize room/zone text for fuzzy dictionary lookup."""
    text = (value or "").strip().lower()
    if not text:
        return ""

    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
    for src, target in replacements.items():
        text = text.replace(src, target)

    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


@dataclass(frozen=True)
class RaumRegistryEntry:
    """Canonical mapping entry for room aliases -> ZoneType."""

    key: str
    zone_type: ZoneType
    source: str


def _build_raum_registry() -> Dict[str, RaumRegistryEntry]:
    """Build alias registry from the zone taxonomy.

    RAUM_REGISTRY intentionally includes:
    - Zone enum values (e.g. "living")
    - Zone names (DE/EN)
    - Keywords (DE/EN)
    - `zone:<type>` aliases
    """

    registry: Dict[str, RaumRegistryEntry] = {}

    for zone in get_all_zones():
        zone_type = zone.zone_type
        candidates: list[tuple[str, str]] = [
            (zone_type.value, "zone_type"),
            (f"zone:{zone_type.value}", "zone_alias"),
            (zone.name_de, "zone_name_de"),
            (zone.name_en, "zone_name_en"),
        ]

        candidates.extend((kw, "keyword_de") for kw in zone.keywords_de)
        candidates.extend((kw, "keyword_en") for kw in zone.keywords_en)

        for raw, source in candidates:
            key = _normalize_key(raw)
            if not key:
                continue
            registry[key] = RaumRegistryEntry(key=key, zone_type=zone_type, source=source)

    return registry


RAUM_REGISTRY: Dict[str, RaumRegistryEntry] = _build_raum_registry()


# =============================================================================
# Pydantic models
# =============================================================================


class TagSource(str, Enum):
    MANUAL = "manual"
    INFERRED = "inferred"
    LEARNED = "learned"
    IMPORTED = "imported"
    BULK = "bulk"


class TagSchema(BaseModel):
    """Canonical tag schema."""

    tag_id: str = Field(..., description="Canonical tag id (e.g. aicp.role.licht)")
    namespace: str = Field(..., description="Tag namespace")
    facet: str = Field(..., description="Tag facet/category")
    key: str = Field(..., description="Tag key")
    name: Optional[str] = Field(None, description="Human-readable label")
    description: Optional[str] = Field(None, description="Optional description")
    icon: Optional[str] = Field(None, description="Optional MDI icon")
    color: Optional[str] = Field(None, description="Optional UI color")
    source: TagSource = Field(default=TagSource.MANUAL)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TagCreateRequest(BaseModel):
    """Create a tag.

    If `tag_id` is omitted, it is generated from namespace/facet/key.
    """

    tag_id: Optional[str] = Field(None, description="Optional explicit tag id")
    namespace: str = Field(default="aicp")
    facet: str = Field(default="custom")
    key: str = Field(..., min_length=1, max_length=128)
    name: Optional[str] = Field(None, max_length=160)
    description: Optional[str] = Field(None, max_length=1000)
    icon: Optional[str] = Field(None, max_length=120)
    color: Optional[str] = Field(None, max_length=32)
    source: TagSource = Field(default=TagSource.MANUAL)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("namespace", "facet", "key")
    @classmethod
    def _validate_parts(cls, value: str) -> str:
        cleaned = _normalize_key(value)
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned


class TagZoneMappingRequest(BaseModel):
    tag_id: str = Field(..., description="Tag to map")
    zone: str = Field(..., description="ZoneType value, room name, or RAUM_REGISTRY alias")
    source: TagSource = Field(default=TagSource.MANUAL)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    meta: Dict[str, Any] = Field(default_factory=dict)


class TagZoneMappingResponse(BaseModel):
    tag_id: str
    zone_type: str
    zone_name_de: str
    zone_name_en: str
    matched_by: str
    confidence: float
    source: TagSource
    mapped_at: datetime


class TagEntityAssignmentRequest(BaseModel):
    tag_id: str = Field(..., description="Tag to assign")
    entity_id: str = Field(..., min_length=1, description="HA entity id")
    source: TagSource = Field(default=TagSource.MANUAL)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    materialized: bool = Field(default=False)
    meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("entity_id")
    @classmethod
    def _validate_entity_id(cls, value: str) -> str:
        entity_id = value.strip()
        if not entity_id:
            raise ValueError("entity_id must not be empty")
        return entity_id


class TagEntityAssignmentResponse(BaseModel):
    assignment_id: str
    tag_id: str
    entity_id: str
    zone_type: Optional[str] = None
    source: TagSource
    confidence: float
    materialized: bool
    meta: Dict[str, Any] = Field(default_factory=dict)
    assigned_at: datetime
    updated_at: datetime


class BulkTagOperationsRequest(BaseModel):
    create_tags: list[TagCreateRequest] = Field(default_factory=list)
    zone_mappings: list[TagZoneMappingRequest] = Field(default_factory=list)
    entity_assignments: list[TagEntityAssignmentRequest] = Field(default_factory=list)
    continue_on_error: bool = Field(default=True)


class BulkOperationError(BaseModel):
    operation: str
    index: int
    message: str


class BulkTagOperationsResponse(BaseModel):
    created_tags: int
    mapped_zones: int
    assigned_entities: int
    errors: list[BulkOperationError] = Field(default_factory=list)


class ZoneTaxonomyEntry(BaseModel):
    zone_type: str
    name_de: str
    name_en: str
    keywords_de: list[str]
    keywords_en: list[str]


class RaumRegistryResponse(BaseModel):
    count: int
    entries: dict[str, dict[str, str]]


# =============================================================================
# In-memory state
# =============================================================================


_LOCK = RLock()

_TAGS: dict[str, TagSchema] = {}
_TAG_ZONE_MAP: dict[str, set[str]] = {}
_ZONE_TAG_MAP: dict[str, set[str]] = {}
_TAG_ENTITY_MAP: dict[str, dict[str, TagEntityAssignmentResponse]] = {}
_ENTITY_TAG_MAP: dict[str, set[str]] = {}


# =============================================================================
# Helpers
# =============================================================================


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_tag_id(namespace: str, facet: str, key: str) -> str:
    return f"{_normalize_key(namespace)}.{_normalize_key(facet)}.{_normalize_key(key)}"


def _split_tag_id(tag_id: str) -> tuple[str, str, str]:
    parts = (tag_id or "").split(".")
    if len(parts) >= 3:
        namespace, facet = parts[0], parts[1]
        key = ".".join(parts[2:])
        return _normalize_key(namespace), _normalize_key(facet), _normalize_key(key)

    # fallback for non-canonical ids
    norm = _normalize_key(tag_id)
    return "aicp", "custom", norm


def _ensure_tag_exists(tag_id: str) -> TagSchema:
    tag = _TAGS.get(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail=f"Tag not found: {tag_id}")
    return tag


def _resolve_zone(zone_input: str) -> tuple[ZoneType, str, float]:
    """Resolve zone from taxonomy + RAUM_REGISTRY + matcher.

    Returns (zone_type, matched_by, confidence_0_to_1)
    """

    raw = (zone_input or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="zone must not be empty")

    # 1) Direct enum match (zone:<type> supported)
    direct = raw[5:] if raw.lower().startswith("zone:") else raw
    try:
        zone_type = ZoneType(direct.lower())
        return zone_type, "zone_type", 1.0
    except ValueError:
        pass

    # 2) RAUM_REGISTRY alias lookup
    normalized = _normalize_key(raw)
    entry = RAUM_REGISTRY.get(normalized)
    if entry:
        return entry.zone_type, f"raum_registry:{entry.source}", 0.98

    # 3) Taxonomy matcher fallback
    try:
        match = match_room(raw)
        if match and match.zone:
            return match.zone.zone_type, "zone_taxonomy_matcher", max(0.0, min(match.confidence / 100.0, 1.0))
    except Exception as err:  # pragma: no cover - defensive fallback
        logger.debug("Zone matcher fallback failed for %s: %s", raw, err)

    allowed = [z.value for z in ZoneType]
    raise HTTPException(
        status_code=400,
        detail={
            "code": "INVALID_ZONE",
            "message": f"Could not resolve zone: {zone_input}",
            "allowed_zone_types": allowed,
        },
    )


def _infer_zone_from_entity(entity_id: str) -> Optional[str]:
    """Best-effort zone inference from entity id via RAUM_REGISTRY aliases."""
    normalized = _normalize_key(entity_id.replace(".", "_"))
    for key, entry in RAUM_REGISTRY.items():
        if key and key in normalized:
            return entry.zone_type.value
    return None


def _serialize_tag_with_links(tag: TagSchema) -> dict[str, Any]:
    zones = sorted(_TAG_ZONE_MAP.get(tag.tag_id, set()))
    entities = sorted(_TAG_ENTITY_MAP.get(tag.tag_id, {}).keys())
    payload = tag.model_dump()
    payload["zones"] = zones
    payload["entities"] = entities
    payload["zone_count"] = len(zones)
    payload["entity_count"] = len(entities)
    return payload


# =============================================================================
# Core operations (reused by single + bulk endpoints)
# =============================================================================


def _create_tag(request: TagCreateRequest) -> TagSchema:
    tag_id = request.tag_id or _build_tag_id(request.namespace, request.facet, request.key)
    tag_id = tag_id.strip()
    if not tag_id:
        raise HTTPException(status_code=400, detail="tag_id must not be empty")

    with _LOCK:
        if tag_id in _TAGS:
            raise HTTPException(status_code=409, detail=f"Tag already exists: {tag_id}")

        namespace, facet, key = _split_tag_id(tag_id)
        now = _utcnow()
        tag = TagSchema(
            tag_id=tag_id,
            namespace=namespace,
            facet=facet,
            key=key,
            name=request.name,
            description=request.description,
            icon=request.icon,
            color=request.color,
            source=request.source,
            metadata=dict(request.metadata),
            created_at=now,
            updated_at=now,
        )
        _TAGS[tag_id] = tag
        _TAG_ZONE_MAP.setdefault(tag_id, set())
        _TAG_ENTITY_MAP.setdefault(tag_id, {})

        return tag


def _map_tag_to_zone(request: TagZoneMappingRequest) -> TagZoneMappingResponse:
    with _LOCK:
        _ensure_tag_exists(request.tag_id)
        zone_type, matched_by, confidence = _resolve_zone(request.zone)
        zone_value = zone_type.value

        _TAG_ZONE_MAP.setdefault(request.tag_id, set()).add(zone_value)
        _ZONE_TAG_MAP.setdefault(zone_value, set()).add(request.tag_id)

        zone = HABITUS_ZONES[zone_type]
        return TagZoneMappingResponse(
            tag_id=request.tag_id,
            zone_type=zone_value,
            zone_name_de=zone.name_de,
            zone_name_en=zone.name_en,
            matched_by=matched_by,
            confidence=max(request.confidence, confidence),
            source=request.source,
            mapped_at=_utcnow(),
        )


def _assign_tag_to_entity(request: TagEntityAssignmentRequest) -> TagEntityAssignmentResponse:
    with _LOCK:
        _ensure_tag_exists(request.tag_id)

        assignment_id = f"{request.tag_id}::{request.entity_id}"
        now = _utcnow()

        existing = _TAG_ENTITY_MAP.setdefault(request.tag_id, {}).get(request.entity_id)
        assigned_at = existing.assigned_at if existing else now

        zone_type = _infer_zone_from_entity(request.entity_id)

        assignment = TagEntityAssignmentResponse(
            assignment_id=assignment_id,
            tag_id=request.tag_id,
            entity_id=request.entity_id,
            zone_type=zone_type,
            source=request.source,
            confidence=request.confidence,
            materialized=request.materialized,
            meta=dict(request.meta),
            assigned_at=assigned_at,
            updated_at=now,
        )

        _TAG_ENTITY_MAP[request.tag_id][request.entity_id] = assignment
        _ENTITY_TAG_MAP.setdefault(request.entity_id, set()).add(request.tag_id)

        return assignment


# =============================================================================
# API endpoints
# =============================================================================


@router.get("/zone-taxonomy", response_model=list[ZoneTaxonomyEntry])
async def get_zone_taxonomy() -> list[ZoneTaxonomyEntry]:
    """Expose the active zone taxonomy used for mapping."""
    return [
        ZoneTaxonomyEntry(
            zone_type=zone.zone_type.value,
            name_de=zone.name_de,
            name_en=zone.name_en,
            keywords_de=list(zone.keywords_de),
            keywords_en=list(zone.keywords_en),
        )
        for zone in get_all_zones()
    ]


@router.get("/raum-registry", response_model=RaumRegistryResponse)
async def get_raum_registry() -> RaumRegistryResponse:
    """Expose normalized RAUM_REGISTRY aliases for debugging and tooling."""
    entries = {
        key: {
            "zone_type": entry.zone_type.value,
            "source": entry.source,
        }
        for key, entry in sorted(RAUM_REGISTRY.items())
    }
    return RaumRegistryResponse(count=len(entries), entries=entries)


@router.post("", response_model=TagSchema, status_code=201)
async def create_tag(request: TagCreateRequest) -> TagSchema:
    """Create a new tag."""
    return _create_tag(request)


@router.get("", response_model=list[dict[str, Any]])
async def list_tags(
    namespace: Optional[str] = Query(None),
    facet: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search by tag_id/name/description"),
) -> list[dict[str, Any]]:
    """List tags with optional filtering."""
    namespace_norm = _normalize_key(namespace) if namespace else None
    facet_norm = _normalize_key(facet) if facet else None
    query = (q or "").strip().lower()

    with _LOCK:
        tags = list(_TAGS.values())

    result: list[dict[str, Any]] = []
    for tag in tags:
        if namespace_norm and tag.namespace != namespace_norm:
            continue
        if facet_norm and tag.facet != facet_norm:
            continue

        if query:
            haystack = " ".join(
                [
                    tag.tag_id.lower(),
                    (tag.name or "").lower(),
                    (tag.description or "").lower(),
                ]
            )
            if query not in haystack:
                continue

        result.append(_serialize_tag_with_links(tag))

    return result



@router.post("/zone-mappings", response_model=TagZoneMappingResponse, status_code=201)
async def create_zone_mapping(request: TagZoneMappingRequest) -> TagZoneMappingResponse:
    """Map an existing tag to a zone (taxonomy + RAUM_REGISTRY aware)."""
    return _map_tag_to_zone(request)


@router.post("/zone-mapping", response_model=TagZoneMappingResponse, status_code=201)
async def create_zone_mapping_alias(request: TagZoneMappingRequest) -> TagZoneMappingResponse:
    """Backward-compatible alias for single tag-zone mapping."""
    return _map_tag_to_zone(request)


@router.post("/{tag_id}/zones", response_model=TagZoneMappingResponse, status_code=201)
async def create_zone_mapping_for_tag(tag_id: str, request: TagZoneMappingRequest) -> TagZoneMappingResponse:
    """Convenience endpoint for tag-scoped zone mapping."""
    if request.tag_id != tag_id:
        request = request.model_copy(update={"tag_id": tag_id})
    return _map_tag_to_zone(request)


@router.get("/zone-mappings", response_model=list[TagZoneMappingResponse])
async def list_zone_mappings(
    tag_id: Optional[str] = Query(None),
    zone: Optional[str] = Query(None),
) -> list[TagZoneMappingResponse]:
    """List current tag-zone mappings."""
    zone_filter: Optional[str] = None
    if zone:
        zone_filter = _resolve_zone(zone)[0].value

    with _LOCK:
        result: list[TagZoneMappingResponse] = []
        for current_tag_id, zones in _TAG_ZONE_MAP.items():
            if tag_id and current_tag_id != tag_id:
                continue
            for zone_value in zones:
                if zone_filter and zone_filter != zone_value:
                    continue
                zone_type = ZoneType(zone_value)
                zone_obj = HABITUS_ZONES[zone_type]
                result.append(
                    TagZoneMappingResponse(
                        tag_id=current_tag_id,
                        zone_type=zone_value,
                        zone_name_de=zone_obj.name_de,
                        zone_name_en=zone_obj.name_en,
                        matched_by="stored_mapping",
                        confidence=1.0,
                        source=TagSource.MANUAL,
                        mapped_at=_utcnow(),
                    )
                )

    return result


@router.get("/zone-mapping", response_model=list[TagZoneMappingResponse])
async def list_zone_mappings_alias(
    tag_id: Optional[str] = Query(None),
    zone: Optional[str] = Query(None),
) -> list[TagZoneMappingResponse]:
    """Backward-compatible alias for listing tag-zone mappings."""
    return await list_zone_mappings(tag_id=tag_id, zone=zone)


@router.delete("/{tag_id}/zones/{zone}")
async def delete_zone_mapping(tag_id: str, zone: str) -> dict[str, Any]:
    """Remove one mapping between a tag and zone."""
    with _LOCK:
        _ensure_tag_exists(tag_id)
        zone_type, _matched_by, _confidence = _resolve_zone(zone)
        zone_value = zone_type.value

        mapped_zones = _TAG_ZONE_MAP.get(tag_id, set())
        if zone_value not in mapped_zones:
            raise HTTPException(status_code=404, detail="Tag-zone mapping not found")

        mapped_zones.discard(zone_value)
        zone_tags = _ZONE_TAG_MAP.get(zone_value)
        if zone_tags:
            zone_tags.discard(tag_id)
            if not zone_tags:
                _ZONE_TAG_MAP.pop(zone_value, None)

    return {"ok": True, "tag_id": tag_id, "zone_type": zone_value, "removed": True}


@router.post("/assignments", response_model=TagEntityAssignmentResponse, status_code=201)
async def assign_tag_to_entity(request: TagEntityAssignmentRequest) -> TagEntityAssignmentResponse:
    """Assign a tag to an entity."""
    return _assign_tag_to_entity(request)


@router.post("/entity-assignment", response_model=TagEntityAssignmentResponse, status_code=201)
async def assign_tag_to_entity_alias(request: TagEntityAssignmentRequest) -> TagEntityAssignmentResponse:
    """Backward-compatible alias for single entity assignment."""
    return _assign_tag_to_entity(request)


@router.post("/{tag_id}/entities", response_model=TagEntityAssignmentResponse, status_code=201)
async def assign_tag_to_entity_scoped(tag_id: str, request: TagEntityAssignmentRequest) -> TagEntityAssignmentResponse:
    """Convenience endpoint for tag-scoped entity assignment."""
    if request.tag_id != tag_id:
        request = request.model_copy(update={"tag_id": tag_id})
    return _assign_tag_to_entity(request)


@router.get("/assignments", response_model=list[TagEntityAssignmentResponse])
async def list_entity_assignments(
    tag_id: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
) -> list[TagEntityAssignmentResponse]:
    """List entity assignments with optional filters."""
    with _LOCK:
        if tag_id:
            _ensure_tag_exists(tag_id)
            assignments = list(_TAG_ENTITY_MAP.get(tag_id, {}).values())
            if entity_id:
                assignments = [a for a in assignments if a.entity_id == entity_id]
            return assignments

        all_assignments: list[TagEntityAssignmentResponse] = []
        for tag_assignments in _TAG_ENTITY_MAP.values():
            all_assignments.extend(tag_assignments.values())

        if entity_id:
            all_assignments = [a for a in all_assignments if a.entity_id == entity_id]

        return all_assignments


@router.get("/{tag_id}/entities", response_model=list[TagEntityAssignmentResponse])
async def list_entities_for_tag(tag_id: str) -> list[TagEntityAssignmentResponse]:
    """List all entity assignments for a tag."""
    with _LOCK:
        _ensure_tag_exists(tag_id)
        return list(_TAG_ENTITY_MAP.get(tag_id, {}).values())


@router.delete("/{tag_id}/entities/{entity_id:path}")
async def delete_entity_assignment(tag_id: str, entity_id: str) -> dict[str, Any]:
    """Remove a single tag->entity assignment."""
    with _LOCK:
        _ensure_tag_exists(tag_id)
        tag_assignments = _TAG_ENTITY_MAP.get(tag_id, {})
        if entity_id not in tag_assignments:
            raise HTTPException(status_code=404, detail="Tag-entity assignment not found")

        tag_assignments.pop(entity_id, None)
        entity_tags = _ENTITY_TAG_MAP.get(entity_id)
        if entity_tags:
            entity_tags.discard(tag_id)
            if not entity_tags:
                _ENTITY_TAG_MAP.pop(entity_id, None)

    return {"ok": True, "tag_id": tag_id, "entity_id": entity_id, "removed": True}


@router.post("/bulk", response_model=BulkTagOperationsResponse)
async def run_bulk_tag_operations(request: BulkTagOperationsRequest) -> BulkTagOperationsResponse:
    """Execute bulk tag operations in one request.

    Order:
      1) create_tags
      2) zone_mappings
      3) entity_assignments
    """
    created_tags = 0
    mapped_zones = 0
    assigned_entities = 0
    errors: list[BulkOperationError] = []

    # 1) Tag creation
    for idx, item in enumerate(request.create_tags):
        try:
            _create_tag(item)
            created_tags += 1
        except Exception as err:  # noqa: BLE001
            errors.append(BulkOperationError(operation="create_tags", index=idx, message=str(err)))
            if not request.continue_on_error:
                return BulkTagOperationsResponse(
                    created_tags=created_tags,
                    mapped_zones=mapped_zones,
                    assigned_entities=assigned_entities,
                    errors=errors,
                )

    # 2) Zone mappings
    for idx, item in enumerate(request.zone_mappings):
        try:
            _map_tag_to_zone(item)
            mapped_zones += 1
        except Exception as err:  # noqa: BLE001
            errors.append(BulkOperationError(operation="zone_mappings", index=idx, message=str(err)))
            if not request.continue_on_error:
                return BulkTagOperationsResponse(
                    created_tags=created_tags,
                    mapped_zones=mapped_zones,
                    assigned_entities=assigned_entities,
                    errors=errors,
                )

    # 3) Entity assignments
    for idx, item in enumerate(request.entity_assignments):
        try:
            _assign_tag_to_entity(item)
            assigned_entities += 1
        except Exception as err:  # noqa: BLE001
            errors.append(BulkOperationError(operation="entity_assignments", index=idx, message=str(err)))
            if not request.continue_on_error:
                return BulkTagOperationsResponse(
                    created_tags=created_tags,
                    mapped_zones=mapped_zones,
                    assigned_entities=assigned_entities,
                    errors=errors,
                )

    return BulkTagOperationsResponse(
        created_tags=created_tags,
        mapped_zones=mapped_zones,
        assigned_entities=assigned_entities,
        errors=errors,
    )


@router.post("/bulk-operations", response_model=BulkTagOperationsResponse)
async def run_bulk_tag_operations_alias(request: BulkTagOperationsRequest) -> BulkTagOperationsResponse:
    """Backward-compatible alias for bulk operations."""
    return await run_bulk_tag_operations(request)


@router.get("/stats")
async def get_tag_stats() -> dict[str, Any]:
    """Quick aggregate stats for dashboards/debugging."""
    with _LOCK:
        return {
            "total_tags": len(_TAGS),
            "total_zone_mappings": sum(len(v) for v in _TAG_ZONE_MAP.values()),
            "total_entity_assignments": sum(len(v) for v in _TAG_ENTITY_MAP.values()),
            "zones_with_tags": sorted([z for z, tags in _ZONE_TAG_MAP.items() if tags]),
            "entities_with_tags": len(_ENTITY_TAG_MAP),
            "raum_registry_size": len(RAUM_REGISTRY),
        }


@router.get("/{tag_id}", response_model=dict[str, Any])
async def get_tag(tag_id: str) -> dict[str, Any]:
    """Get one tag with linked zones/entities."""
    with _LOCK:
        tag = _ensure_tag_exists(tag_id)
        return _serialize_tag_with_links(tag)


@router.delete("/{tag_id}")
async def delete_tag(tag_id: str) -> dict[str, Any]:
    """Delete a tag and all mappings/assignments."""
    with _LOCK:
        _ensure_tag_exists(tag_id)

        zones = _TAG_ZONE_MAP.pop(tag_id, set())
        for zone in zones:
            zone_tags = _ZONE_TAG_MAP.get(zone)
            if not zone_tags:
                continue
            zone_tags.discard(tag_id)
            if not zone_tags:
                _ZONE_TAG_MAP.pop(zone, None)

        entities = list(_TAG_ENTITY_MAP.pop(tag_id, {}).keys())
        for entity_id in entities:
            tags = _ENTITY_TAG_MAP.get(entity_id)
            if not tags:
                continue
            tags.discard(tag_id)
            if not tags:
                _ENTITY_TAG_MAP.pop(entity_id, None)

        _TAGS.pop(tag_id, None)

    return {
        "ok": True,
        "deleted": tag_id,
        "zones_removed": len(zones),
        "entity_assignments_removed": len(entities),
    }
