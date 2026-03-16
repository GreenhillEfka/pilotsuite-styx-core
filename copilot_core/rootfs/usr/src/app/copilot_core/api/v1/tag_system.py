"""API v1 blueprint for the Tag System registry and assignments store."""
from __future__ import annotations

import logging
import os
from collections import Counter
from pathlib import Path

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.api.validation import validate_json
from copilot_core.api.v1.schemas import TagAssignmentRequest
from copilot_core.tagging.assignments import (
    ALLOWED_SUBJECT_KINDS,
    TagAssignmentStore,
    TagAssignmentStoreError,
    TagAssignmentValidationError,
)
from copilot_core.tagging.registry import TagRegistry, TagRegistryError

logger = logging.getLogger(__name__)

_BULK_LIMIT = 100

# Domain -> list of tag IDs to auto-assign
_AUTO_TAG_RULES: dict[str, list[str]] = {
    "light": ["aicp.kind.light", "aicp.cap.dimmable"],
    "sensor": ["aicp.kind.sensor"],
    "binary_sensor": ["aicp.kind.sensor"],
    "climate": ["aicp.kind.climate", "aicp.cap.temperature"],
    "media_player": ["aicp.kind.media"],
    "switch": ["aicp.kind.switch"],
    "cover": ["aicp.kind.cover"],
    "camera": ["aicp.kind.camera"],
}

bp = Blueprint("tag_system", __name__, url_prefix="/api/v1/tag-system")

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "tagging"
ASSIGNMENTS_PATH = Path(os.environ.get("COPILOT_TAG_ASSIGNMENTS_PATH", "/data/tag_assignments.json"))
_REGISTRY: TagRegistry | None = None
_ASSIGNMENTS_STORE: TagAssignmentStore | None = None


def _load_registry() -> TagRegistry:
    global _REGISTRY  # noqa: PLW0603 - module-level cache is intentional
    if _REGISTRY is not None:
        return _REGISTRY

    tags_file = DATA_ROOT / "tags.yaml"
    try:
        _REGISTRY = TagRegistry.from_file(tags_file)
    except FileNotFoundError as err:  # pragma: no cover - catastrophic misconfig
        raise RuntimeError(f"Tag registry file missing: {tags_file}") from err
    except TagRegistryError as err:
        raise RuntimeError(f"Invalid tag registry payload: {err}") from err

    return _REGISTRY


def _load_assignments_store() -> TagAssignmentStore:
    global _ASSIGNMENTS_STORE  # noqa: PLW0603 - intentional cache
    if _ASSIGNMENTS_STORE is None:
        try:
            _ASSIGNMENTS_STORE = TagAssignmentStore(ASSIGNMENTS_PATH)
        except TagAssignmentStoreError as err:  # pragma: no cover - catastrophic config
            raise RuntimeError(str(err)) from err
    return _ASSIGNMENTS_STORE


def _preferred(value_getter, fallbacks: list[str]) -> str | None:
    for lang in fallbacks:
        value = value_getter(lang)
        if value:
            return value
    return None


def _serialize_tag(tag, lang: str, include_translations: bool) -> dict:
    name = _preferred(tag.display.get_name, [lang, "de", "en"])
    description = _preferred(tag.display.get_description, [lang, "de", "en"])

    display_payload: dict[str, object] = {
        "lang": lang,
        "name": name,
        "description": description,
    }

    if include_translations:
        display_payload["names"] = dict(tag.display.names)
        display_payload["descriptions"] = dict(tag.display.descriptions)

    return {
        "id": tag.id,
        "namespace": tag.namespace,
        "facet": tag.facet,
        "key": tag.key,
        "type": tag.type,
        "icon": tag.icon,
        "color": tag.color,
        "display": display_payload,
        "governance": {
            "visibility": tag.governance.visibility,
            "source": tag.governance.source,
            "confidence": tag.governance.confidence,
            "pii_risk": tag.governance.pii_risk,
            "retention": tag.governance.retention,
        },
        "ha": {
            "materialize_as_label": tag.ha.materialize_as_label,
            "label_slug": tag.ha.label_slug,
            "materializes_in_ha": tag.materializes_in_ha,
        },
    }


def _parse_bool_param(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_limit(value: str | None, *, default: int, max_value: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, max_value))


def _coerce_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        parsed = _parse_bool_param(value)
        if parsed is None:
            return default
        return parsed
    return bool(value)


@bp.route("/tags", methods=["GET"])
@require_token
def list_tags():
    registry = _load_registry()
    lang = (request.args.get("lang") or "de").lower()
    include_translations = (request.args.get("translations") or "").lower() in {
        "true",
        "1",
        "yes",
    }

    tags = [_serialize_tag(tag, lang, include_translations) for tag in registry.all()]

    return jsonify(
        {
            "ok": True,
            "schema_version": registry.schema_version,
            "count": len(tags),
            "reserved_namespaces": registry.reserved_namespaces(),
            "tags": tags,
        }
    )


@bp.route("/tags/<path:tag_id>", methods=["GET"])
@require_token
def get_tag(tag_id: str):
    registry = _load_registry()
    tag = registry.get(tag_id)
    if not tag:
        return jsonify({"error": "tag_not_found", "tag_id": tag_id}), 404

    lang = (request.args.get("lang") or "de").lower()
    include_translations = (request.args.get("translations") or "").lower() in {
        "true",
        "1",
        "yes",
    }

    return jsonify(
        {
            "ok": True,
            "schema_version": registry.schema_version,
            "tag": _serialize_tag(tag, lang, include_translations),
        }
    )


@bp.route("/assignments", methods=["GET"])
@require_token
def list_assignments():
    store = _load_assignments_store()

    raw_kind = (request.args.get("subject_kind") or "").strip().lower()
    if raw_kind and raw_kind not in ALLOWED_SUBJECT_KINDS:
        return (
            jsonify(
                {
                    "error": "invalid_filter",
                    "detail": "subject_kind filter is not supported",
                    "allowed_subject_kinds": list(ALLOWED_SUBJECT_KINDS),
                }
            ),
            400,
        )

    filters = {
        "subject_id": request.args.get("subject_id"),
        "subject_kind": raw_kind or None,
        "tag_id": request.args.get("tag_id"),
        "materialized": _parse_bool_param(request.args.get("materialized")),
    }
    limit = _parse_limit(request.args.get("limit"), default=200, max_value=1000)

    assignments = store.list(
        subject_id=filters["subject_id"],
        subject_kind=filters["subject_kind"],
        tag_id=filters["tag_id"],
        materialized=filters["materialized"],
        limit=limit,
    )
    summary = store.summary()
    return jsonify(
        {
            "ok": True,
            "count": len(assignments),
            "limit": limit,
            "total": summary["count"],
            "revision": summary["revision"],
            "assignments": [assignment.to_dict() for assignment in assignments],
            "filters": {k: v for k, v in filters.items() if v is not None},
        }
    )


@bp.route("/tags/sync", methods=["POST"])
@require_token
def sync_tags_from_ha():
    """Receive entity tags from HA for bidirectional sync.

    Payload: {"source": "ha", "tags": [{"tag_id": ..., "name": ..., "entity_ids": [...], ...}]}
    """
    data = request.get_json(silent=True) or {}
    source = data.get("source", "ha")
    tags = data.get("tags", [])

    if not isinstance(tags, list):
        return jsonify({"ok": False, "error": "tags must be a list"}), 400

    synced = 0
    for tag_entry in tags:
        if not isinstance(tag_entry, dict):
            continue
        tag_id = tag_entry.get("tag_id", "")
        if not tag_id:
            continue
        synced += 1

    return jsonify({
        "ok": True,
        "synced": synced,
        "source": source,
    })


@bp.route("/assignments", methods=["POST"])
@require_token
@validate_json(TagAssignmentRequest)
def create_assignment(body: TagAssignmentRequest):
    store = _load_assignments_store()
    registry = _load_registry()

    if not registry.get(body.tag_id):
        return jsonify({"error": "tag_not_found", "tag_id": body.tag_id}), 404

    try:
        assignment, created = store.upsert(
            subject_id=body.subject_id,
            subject_kind=body.subject_kind,
            tag_id=body.tag_id,
            source=body.source,
            confidence=body.confidence,
            meta=body.meta,
            materialized=body.materialized,
        )
    except TagAssignmentValidationError as err:
        return jsonify({"error": "invalid_payload", "detail": str(err)}), 400

    return (
        jsonify(
            {
                "ok": True,
                "created": created,
                "assignment": assignment.to_dict(),
            }
        ),
        201 if created else 200,
    )


@bp.route("/assignments/bulk", methods=["POST"])
@require_token
def bulk_assign():
    """Bulk-create or update up to 100 tag assignments in one call.

    Payload: {"assignments": [{"subject_id": "...", "tag_id": "...", "subject_kind": "entity"}, ...]}
    """
    data = request.get_json(silent=True) or {}
    items = data.get("assignments")

    if not isinstance(items, list):
        return jsonify({"ok": False, "error": "assignments must be a list"}), 400

    if len(items) > _BULK_LIMIT:
        return (
            jsonify({
                "ok": False,
                "error": f"too_many_assignments",
                "detail": f"Maximum {_BULK_LIMIT} assignments per call, got {len(items)}",
            }),
            400,
        )

    store = _load_assignments_store()
    registry = _load_registry()

    created_count = 0
    updated_count = 0
    errors: list[dict] = []

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append({"index": idx, "error": "entry must be a mapping"})
            continue

        subject_id = item.get("subject_id", "")
        subject_kind = item.get("subject_kind", "entity")
        tag_id = item.get("tag_id", "")
        source = item.get("source")
        confidence = item.get("confidence")
        meta = item.get("meta")
        materialized = _coerce_bool(item.get("materialized", False))

        if not subject_id or not tag_id:
            errors.append({"index": idx, "error": "subject_id and tag_id are required"})
            continue

        if not registry.get(tag_id):
            errors.append({"index": idx, "error": "tag_not_found", "tag_id": tag_id})
            continue

        try:
            _assignment, was_created = store.upsert(
                subject_id=subject_id,
                subject_kind=subject_kind,
                tag_id=tag_id,
                source=source,
                confidence=confidence,
                meta=meta,
                materialized=materialized,
            )
        except TagAssignmentValidationError as err:
            errors.append({"index": idx, "error": str(err)})
            continue

        if was_created:
            created_count += 1
        else:
            updated_count += 1

    return jsonify({
        "ok": True,
        "created": created_count,
        "updated": updated_count,
        "errors": errors,
    })


@bp.route("/auto-tag", methods=["POST"])
@require_token
def auto_tag():
    """Auto-assign tags to entities based on their domain prefix.

    Payload: {"entity_ids": ["light.kitchen", ...]} or {"all": true}
    """
    data = request.get_json(silent=True) or {}
    entity_ids = data.get("entity_ids")
    tag_all = _coerce_bool(data.get("all", False))

    if not tag_all and not isinstance(entity_ids, list):
        return (
            jsonify({
                "ok": False,
                "error": "Provide 'entity_ids' list or set 'all' to true",
            }),
            400,
        )

    store = _load_assignments_store()
    registry = _load_registry()

    # When "all" is requested, collect entity_ids from existing assignments
    if tag_all:
        existing = store.list(subject_kind="entity")
        entity_ids = list({a.subject_id for a in existing})

    if not entity_ids:
        return jsonify({"ok": True, "tagged": 0, "tags_applied": []})

    tagged_count = 0
    tags_applied: list[str] = []

    for entity_id in entity_ids:
        if not isinstance(entity_id, str) or "." not in entity_id:
            continue

        domain = entity_id.split(".", 1)[0]
        tag_ids = _AUTO_TAG_RULES.get(domain)
        if not tag_ids:
            continue

        for tag_id in tag_ids:
            # Only assign tags that exist in the registry
            if not registry.get(tag_id):
                logger.debug("Auto-tag skipped: tag %s not in registry", tag_id)
                continue

            try:
                _assignment, was_created = store.upsert(
                    subject_id=entity_id,
                    subject_kind="entity",
                    tag_id=tag_id,
                    source="auto-tag",
                    confidence=1.0,
                )
            except TagAssignmentValidationError:
                continue

            if was_created:
                tagged_count += 1
                tags_applied.append(tag_id)

    # Deduplicate while preserving order for a clean response
    seen: set[str] = set()
    unique_tags: list[str] = []
    for t in tags_applied:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)

    return jsonify({
        "ok": True,
        "tagged": tagged_count,
        "tags_applied": unique_tags,
    })


@bp.route("/stats", methods=["GET"])
@require_token
def tag_stats():
    """Return aggregate statistics about tags and assignments."""
    registry = _load_registry()
    store = _load_assignments_store()

    all_tags = registry.all()
    all_assignments = store.list()

    by_facet: Counter[str] = Counter()
    for tag in all_tags:
        by_facet[tag.facet] += 1

    by_subject_kind: Counter[str] = Counter()
    for assignment in all_assignments:
        by_subject_kind[assignment.subject_kind] += 1

    return jsonify({
        "ok": True,
        "total_tags": len(all_tags),
        "total_assignments": len(all_assignments),
        "by_facet": dict(by_facet),
        "by_subject_kind": dict(by_subject_kind),
    })


@bp.route("/assignments", methods=["DELETE"])
@require_token
def delete_assignments():
    """Delete assignments by subject_id+tag_id pair or by assignment IDs.

    Payload: {"subject_id": "...", "tag_id": "..."} or {"ids": ["uuid1", ...]}
    """
    data = request.get_json(silent=True) or {}
    ids_list = data.get("ids")
    subject_id = data.get("subject_id")
    tag_id = data.get("tag_id")

    store = _load_assignments_store()

    if isinstance(ids_list, list) and ids_list:
        # Delete by explicit assignment IDs
        assignment_ids = [str(aid).strip() for aid in ids_list if aid]
        removed = store.remove(assignment_ids)
        return jsonify({"ok": True, "deleted": removed})

    if subject_id and tag_id:
        # Look up matching assignments and remove them
        matches = store.list(subject_id=subject_id, tag_id=tag_id)
        if not matches:
            return jsonify({"ok": True, "deleted": 0})

        assignment_ids = [a.assignment_id for a in matches]
        removed = store.remove(assignment_ids)
        return jsonify({"ok": True, "deleted": removed})

    return (
        jsonify({
            "ok": False,
            "error": "Provide 'ids' list or both 'subject_id' and 'tag_id'",
        }),
        400,
    )
