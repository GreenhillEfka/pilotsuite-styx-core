# Tag System API v1 - Flask Blueprint
"""
REST API Endpoints für Tag System v0.2 (Flask Blueprint)

Decision Matrix P1 Implementierung:
- HA-Labels materialisieren: nur ausgewählte Facetten (role.*, state.*)
- Learned Tags: NIE automatisch (explizite Bestätigung nötig)
- Alle HA-Label-Typen: entity, device, area, automation, scene, script, helper

FIX: Rewritten from aiohttp.web to Flask Blueprint
FIX: Added auth token validation via @require_token decorator
"""

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.tags import (
    TagRegistry,
    TagFacet,
    SubjectType,
    create_tag_service,
)

bp = Blueprint("tags_v2", __name__, url_prefix="/api/v1")

# Global registry - will be set by main.py
_registry: TagRegistry | None = None


def init_tags_api(registry: TagRegistry):
    """Initialize the tags API with the registry instance."""
    global _registry
    _registry = registry


# === Service Factory ===
def _get_service():
    """Get or create tag service (thread-safe for read-only operations)."""
    if _registry is None:
        raise RuntimeError("Tags API not initialized - call init_tags_api() first")
    return create_tag_service(_registry)


# ── Helper Functions ────────────────────────────────────────────────

def _serialize_tag(tag):
    """Serialize Tag object to JSON-safe dict."""
    return {
        "id": tag.id,
        "facet": tag.facet.value,
        "display_de": tag.metadata.display_de,
        "display_en": tag.metadata.display_en,
        "is_learned": tag.is_learned,
        "is_materialized": tag.is_materialized,
        "provenance": tag.provenance,
        "should_materialize": tag.should_materialize(),
    }


def _serialize_subject(subject):
    """Serialize Subject object to JSON-safe dict."""
    return {
        "id": subject.canonical_id,
        "ha_id": subject.ha_id,
        "ha_type": subject.ha_type.value,
        "name": subject.name,
        "domain": subject.domain,
        "unique_id": subject.unique_id,
        "device_id": subject.device_id,
        "area_id": subject.area_id,
        "tags": [
            t.id for t in _registry.get_subject_tags(subject.canonical_id)
        ] if _registry else [],
    }


# ── Tag Endpoints ───────────────────────────────────────────────────

@bp.route("/tags", methods=["POST"])
@require_token
def create_tag():
    """POST /api/v1/tags — Tag erstellen."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    required = ["id", "facet"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    try:
        service = _get_service()
        result = service["create_tag"](
            tag_id=data["id"],
            facet=data["facet"],
            display_de=data.get("display_de"),
            display_en=data.get("display_en"),
        )
        return jsonify(result), 201
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503


@bp.route("/tags/suggest", methods=["POST"])
@require_token
def suggest_tag():
    """POST /api/v1/tags/suggest — Learned Tag vorschlagen."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    required = ["facet", "key"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    try:
        service = _get_service()
        result = service["suggest_tag"](
            facet=data["facet"],
            key=data["key"],
            namespace=data.get("namespace", "sys"),
            display_de=data.get("display_de"),
        )
        return jsonify(result), 201
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503


@bp.route("/tags/<tag_id>/confirm", methods=["POST"])
@require_token
def confirm_tag(tag_id):
    """POST /api/v1/tags/{tag_id}/confirm — Learned Tag bestätigen."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    try:
        service = _get_service()
        result = service["confirm_tag"](tag_id)
        if result.get("status") == "confirmed":
            return jsonify(result), 200
        return jsonify(result), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503


@bp.route("/tags", methods=["GET"])
@require_token
def list_tags():
    """GET /api/v1/tags — Tags auflisten."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    facet = request.args.get("facet")
    try:
        service = _get_service()
        result = service["list_tags"](facet=facet)
        return jsonify(result), 200
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503


@bp.route("/tags/<tag_id>", methods=["GET"])
@require_token
def get_tag(tag_id):
    """GET /api/v1/tags/{tag_id} — Tag details."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    tag = _registry.get_tag(tag_id)
    if not tag:
        return jsonify({"error": "Tag not found"}), 404

    return jsonify(_serialize_tag(tag)), 200


@bp.route("/tags/<tag_id>", methods=["DELETE"])
@require_token
def delete_tag(tag_id):
    """DELETE /api/v1/tags/{tag_id} — Tag löschen."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    if tag_id in _registry._tags:
        del _registry._tags[tag_id]
        return jsonify({"status": "deleted", "tag_id": tag_id}), 200
    return jsonify({"error": "Tag not found"}), 404


# ── Subject Endpoints ───────────────────────────────────────────────

@bp.route("/subjects", methods=["POST"])
@require_token
def register_subject():
    """POST /api/v1/subjects — Subject registrieren."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    required = ["ha_id", "ha_type"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    try:
        service = _get_service()
        result = service["register_subject"](
            ha_id=data["ha_id"],
            ha_type=data["ha_type"],
            name=data.get("name"),
            domain=data.get("domain"),
            unique_id=data.get("unique_id"),
            device_id=data.get("device_id"),
            area_id=data.get("area_id"),
        )
        return jsonify(result), 201
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503


@bp.route("/subjects", methods=["GET"])
@require_token
def list_subjects():
    """GET /api/v1/subjects — Subjects auflisten."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    ha_type = request.args.get("type")
    subjects = list(_registry._subjects.values())
    if ha_type:
        subjects = [s for s in subjects if s.ha_type.value == ha_type]

    return jsonify({
        "subjects": [
            {
                "id": s.canonical_id,
                "ha_id": s.ha_id,
                "ha_type": s.ha_type.value,
                "name": s.name,
                "domain": s.domain,
            }
            for s in subjects
        ]
    }), 200


@bp.route("/subjects/<subject_id>", methods=["GET"])
@require_token
def get_subject(subject_id):
    """GET /api/v1/subjects/{subject_id} — Subject details."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    subject = _registry.get_subject(subject_id)
    if not subject:
        return jsonify({"error": "Subject not found"}), 404

    return jsonify({
        "ha_id": subject.ha_id,
        "ha_type": subject.ha_type.value,
        "canonical_id": subject.canonical_id,
        "unique_id": subject.unique_id,
        "device_id": subject.device_id,
        "area_id": subject.area_id,
        "name": subject.name,
        "domain": subject.domain,
        "tags": [
            t.id for t in _registry.get_subject_tags(subject.canonical_id)
        ],
    }), 200


@bp.route("/subjects/<subject_id>/tags", methods=["GET"])
@require_token
def get_subject_tags(subject_id):
    """GET /api/v1/subjects/{subject_id}/tags — Tags für Subject."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    tags = _registry.get_subject_tags(subject_id)
    return jsonify({
        "tags": [
            {
                "id": t.id,
                "facet": t.facet.value,
                "is_learned": t.is_learned,
            }
            for t in tags
        ]
    }), 200


# ── Assignment Endpoints ────────────────────────────────────────────

@bp.route("/assignments", methods=["POST"])
@require_token
def assign_tag():
    """POST /api/v1/assignments — Tag zu Subject zuweisen."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    required = ["tag_id", "subject_id"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    try:
        service = _get_service()
        result = service["assign_tag"](
            tag_id=data["tag_id"],
            subject_id=data["subject_id"],
        )
        if result.get("status") == "assigned":
            return jsonify(result), 201
        return jsonify(result), 400
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503


@bp.route("/assignments", methods=["GET"])
@require_token
def list_assignments():
    """GET /api/v1/assignments — Alle Zuweisungen."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    tag_id = request.args.get("tag_id")
    subject_id = request.args.get("subject_id")

    assignments = _registry._assignments
    if tag_id:
        assignments = [a for a in assignments if a.tag_id == tag_id]
    if subject_id:
        assignments = [a for a in assignments if a.subject_canonical_id == subject_id]

    return jsonify({
        "assignments": [
            {
                "tag_id": a.tag_id,
                "subject_id": a.subject_canonical_id,
                "assigned_at": a.assigned_at,
                "assigned_by": a.assigned_by,
            }
            for a in assignments
        ]
    }), 200


@bp.route("/assignments", methods=["DELETE"])
@require_token
def delete_assignment():
    """DELETE /api/v1/assignments — Zuweisung entfernen."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    tag_id = data.get("tag_id")
    subject_id = data.get("subject_id")

    original_count = len(_registry._assignments)
    _registry._assignments = [
        a for a in _registry._assignments
        if not (a.tag_id == tag_id and a.subject_canonical_id == subject_id)
    ]

    if len(_registry._assignments) < original_count:
        return jsonify({
            "status": "deleted",
            "tag_id": tag_id,
            "subject_id": subject_id,
        }), 200
    return jsonify({"error": "Assignment not found"}), 404


@bp.route("/tags/<tag_id>/subjects", methods=["GET"])
@require_token
def get_tag_subjects(tag_id):
    """GET /api/v1/tags/{tag_id}/subjects — Subjects für Tag."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    subjects = _registry.get_tag_subjects(tag_id)
    return jsonify({
        "subjects": [
            {
                "id": s.canonical_id,
                "ha_type": s.ha_type.value,
                "name": s.name,
            }
            for s in subjects
        ]
    }), 200


# ── Habitus Zones Endpoints ─────────────────────────────────────────

@bp.route("/zones", methods=["POST"])
@require_token
def create_zone():
    """POST /api/v1/zones — Habitus-Zone erstellen."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    required = ["id", "name"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    zone = _registry.create_zone(
        zone_id=data["id"],
        name=data["name"],
        policy_ids=data.get("policy_ids", []),
    )
    return jsonify({
        "status": "created",
        "zone_id": zone.id,
    }), 201


@bp.route("/zones", methods=["GET"])
@require_token
def list_zones():
    """GET /api/v1/zones — Zonen auflisten."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    return jsonify({
        "zones": [
            {
                "id": z.id,
                "name": z.name,
                "policy_ids": z.policy_ids,
                "member_count": len(z.member_subject_ids),
                "is_active": z.is_active,
            }
            for z in _registry._zones.values()
        ]
    }), 200


@bp.route("/zones/<zone_id>/members", methods=["POST"])
@require_token
def add_to_zone(zone_id):
    """POST /api/v1/zones/{zone_id}/members — Subject zu Zone hinzufügen."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    subject_id = data.get("subject_id")
    if not subject_id:
        return jsonify({"error": "Missing required field: subject_id"}), 400

    result = _registry.add_to_zone(zone_id, subject_id)
    if result:
        return jsonify({
            "status": "added",
            "zone_id": zone_id,
            "subject_id": subject_id,
        }), 200
    return jsonify({"error": "Zone or subject not found"}), 404


# ── HA Label Export ─────────────────────────────────────────────────

@bp.route("/labels/export", methods=["GET"])
@require_token
def export_labels():
    """GET /api/v1/labels/export — Export für HA Labels Sync."""
    if _registry is None:
        return jsonify({"error": "Tags API not initialized"}), 503

    service = _get_service()
    result = service["export_labels"]()
    return jsonify(result), 200
