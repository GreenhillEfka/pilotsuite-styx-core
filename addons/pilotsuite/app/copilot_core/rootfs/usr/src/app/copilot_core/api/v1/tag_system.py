"""API v1 blueprint for the Tag System registry and assignments store."""
from __future__ import annotations

import os
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
