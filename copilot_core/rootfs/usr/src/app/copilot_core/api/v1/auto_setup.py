"""Auto-setup API endpoints for PilotSuite.

Provides endpoints for:
- Zone suggestion from HA entity data
- Auto-tagging entities by device class
- Setup status and summary
"""
from datetime import datetime, timezone

import logging

from flask import Blueprint, request, jsonify

from ..security import validate_token

_LOGGER = logging.getLogger(__name__)

auto_setup_bp = Blueprint("auto_setup", __name__)
_tag_service = None
_setup_history = []


def init_auto_setup_api(tag_service=None):
    """Initialize auto-setup API with required services."""
    global _tag_service
    _tag_service = tag_service


@auto_setup_bp.route("/api/v1/auto-setup/suggest-zones", methods=["POST"])
def suggest_zones():
    """Suggest zones from HA area/entity data.

    Expects JSON body:
    {
        "areas": [{"area_id": "...", "name": "...", "entity_count": N}],
        "entities": [{"entity_id": "...", "domain": "...", "area_id": "...", "device_class": "..."}]
    }

    Returns zone suggestions with entity role assignments.
    """
    auth_error = validate_token(request)
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    areas = data.get("areas", [])
    entities = data.get("entities", [])

    if not areas:
        return jsonify({
            "zones": [],
            "total_areas": 0,
            "total_entities": len(entities),
            "suggested_count": 0,
            "message": "No areas provided",
        }), 200

    # Build entity lookup by area
    area_entities: dict[str, list[dict]] = {}
    for entity in entities:
        area_id = entity.get("area_id")
        if area_id:
            area_entities.setdefault(area_id, []).append(entity)

    # Zone templates (DE + EN names)
    zone_templates = {
        "wohnzimmer": {"icon": "mdi:sofa", "keywords": ["wohn", "living", "lounge"]},
        "schlafzimmer": {"icon": "mdi:bed", "keywords": ["schlaf", "bed", "sleep"]},
        "kueche": {"icon": "mdi:stove", "keywords": ["küch", "kuch", "kitchen"]},
        "bad": {"icon": "mdi:shower", "keywords": ["bad", "bath", "dusch", "wc"]},
        "buero": {"icon": "mdi:desk", "keywords": ["büro", "buero", "office", "arbeit"]},
        "flur": {"icon": "mdi:door-open", "keywords": ["flur", "hall", "corridor"]},
        "kinderzimmer": {"icon": "mdi:baby-face-outline", "keywords": ["kind", "child", "nursery"]},
        "garten": {"icon": "mdi:flower", "keywords": ["garten", "garden", "terrasse", "balkon"]},
        "keller": {"icon": "mdi:home-floor-negative-1", "keywords": ["keller", "basement"]},
        "garage": {"icon": "mdi:garage", "keywords": ["garage", "carport"]},
    }

    # Role classification by domain + device_class
    role_map = {
        ("light", None): "lights",
        ("binary_sensor", "motion"): "presence",
        ("binary_sensor", "presence"): "presence",
        ("binary_sensor", "occupancy"): "presence",
        ("binary_sensor", "door"): "doors",
        ("binary_sensor", "window"): "windows",
        ("sensor", "temperature"): "temperature",
        ("sensor", "humidity"): "humidity",
        ("sensor", "illuminance"): "brightness",
        ("sensor", "carbon_dioxide"): "co2",
        ("sensor", "power"): "energy",
        ("sensor", "energy"): "energy",
        ("media_player", None): "media",
        ("climate", None): "climate",
        ("cover", None): "covers",
        ("camera", None): "cameras",
        ("fan", None): "fans",
        ("lock", None): "locks",
    }

    suggested_zones = []
    for area in areas:
        area_id = area.get("area_id", "")
        area_name = area.get("name", area_id)
        area_name_lower = area_name.lower()

        # Match template
        matched_icon = "mdi:home-circle"
        for tpl_key, tpl in zone_templates.items():
            if any(kw in area_name_lower for kw in tpl["keywords"]):
                matched_icon = tpl["icon"]
                break

        # Classify entities in this area
        entity_roles: dict[str, list[str]] = {}
        area_ents = area_entities.get(area_id, [])

        for ent in area_ents:
            domain = ent.get("domain", "")
            device_class = ent.get("device_class")
            entity_id = ent.get("entity_id", "")

            # Try specific match first, then domain-only
            role = role_map.get((domain, device_class))
            if not role:
                role = role_map.get((domain, None))
            if not role:
                continue

            entity_roles.setdefault(role, []).append(entity_id)

        # Only suggest zones with at least 1 meaningful entity
        if entity_roles:
            suggested_zones.append({
                "zone_id": area_id,
                "name": area_name,
                "icon": matched_icon,
                "entity_count": len(area_ents),
                "roles": entity_roles,
                "confidence": min(0.95, 0.5 + len(entity_roles) * 0.1),
            })

    # Sort by confidence descending
    suggested_zones.sort(key=lambda z: -z["confidence"])

    return jsonify({
        "zones": suggested_zones,
        "total_areas": len(areas),
        "total_entities": len(entities),
        "suggested_count": len(suggested_zones),
    }), 200


@auto_setup_bp.route("/api/v1/auto-setup/auto-tag", methods=["POST"])
def auto_tag_entities():
    """Auto-tag entities by domain and device class.

    Expects JSON body:
    {
        "entities": [{"entity_id": "...", "domain": "...", "device_class": "...", "area_name": "..."}]
    }

    Returns tagging results.
    """
    auth_error = validate_token(request)
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    entities = data.get("entities", [])

    # Domain to tag mapping
    domain_tag_map = {
        "light": {"tag_id": "licht", "name": "Licht", "color": "#fbbf24", "icon": "mdi:lightbulb"},
        "binary_sensor": {"tag_id": "sensor", "name": "Sensor", "color": "#60a5fa", "icon": "mdi:motion-sensor"},
        "sensor": {"tag_id": "sensor", "name": "Sensor", "color": "#60a5fa", "icon": "mdi:thermometer"},
        "media_player": {"tag_id": "media", "name": "Media", "color": "#a78bfa", "icon": "mdi:speaker"},
        "climate": {"tag_id": "klima", "name": "Klima", "color": "#34d399", "icon": "mdi:thermostat"},
        "cover": {"tag_id": "beschattung", "name": "Beschattung", "color": "#fb923c", "icon": "mdi:window-shutter"},
        "switch": {"tag_id": "schalter", "name": "Schalter", "color": "#6366f1", "icon": "mdi:toggle-switch"},
        "camera": {"tag_id": "kamera", "name": "Kamera", "color": "#f472b6", "icon": "mdi:cctv"},
        "person": {"tag_id": "person", "name": "Person", "color": "#a78bfa", "icon": "mdi:account"},
    }

    # Device class specific tags (more precise than domain)
    device_class_tags = {
        "motion": {"tag_id": "bewegung", "name": "Bewegung", "color": "#f87171", "icon": "mdi:motion-sensor"},
        "temperature": {"tag_id": "temperatur", "name": "Temperatur", "color": "#f97316", "icon": "mdi:thermometer"},
        "humidity": {"tag_id": "feuchtigkeit", "name": "Feuchtigkeit", "color": "#06b6d4", "icon": "mdi:water-percent"},
        "illuminance": {"tag_id": "helligkeit", "name": "Helligkeit", "color": "#eab308", "icon": "mdi:brightness-7"},
        "energy": {"tag_id": "energie", "name": "Energie", "color": "#22c55e", "icon": "mdi:flash"},
        "power": {"tag_id": "energie", "name": "Energie", "color": "#22c55e", "icon": "mdi:flash"},
        "door": {"tag_id": "tuer", "name": "Tür", "color": "#8b5cf6", "icon": "mdi:door"},
        "window": {"tag_id": "fenster", "name": "Fenster", "color": "#0ea5e9", "icon": "mdi:window-open"},
        "smoke": {"tag_id": "sicherheit", "name": "Sicherheit", "color": "#ef4444", "icon": "mdi:smoke-detector"},
        "battery": {"tag_id": "batterie", "name": "Batterie", "color": "#84cc16", "icon": "mdi:battery"},
    }

    tags_created: dict[str, dict] = {}
    assignments: list[dict] = []

    for ent in entities:
        entity_id = ent.get("entity_id", "")
        domain = ent.get("domain", "")
        device_class = ent.get("device_class")

        # Prefer device_class tag, fall back to domain tag
        tag_info = None
        if device_class and device_class in device_class_tags:
            tag_info = device_class_tags[device_class]
        elif domain in domain_tag_map:
            tag_info = domain_tag_map[domain]

        if tag_info:
            tag_id = tag_info["tag_id"]
            tags_created[tag_id] = tag_info
            assignments.append({
                "entity_id": entity_id,
                "tag_id": tag_id,
                "source": "auto_setup",
                "confidence": 0.9 if device_class else 0.7,
            })

    # Store in tag service if available
    if _tag_service:
        for tag_id, info in tags_created.items():
            try:
                _tag_service.upsert_tag(
                    tag_id=tag_id,
                    title=info["name"],
                    icon=info.get("icon"),
                    color=info.get("color"),
                    status="confirmed",
                )
            except Exception as err:
                _LOGGER.warning("Failed to create tag %s: %s", tag_id, err)

    # Record setup history
    _setup_history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "auto_tag",
        "tags_created": len(tags_created),
        "assignments": len(assignments),
    })

    return jsonify({
        "tags_created": list(tags_created.values()),
        "assignments": assignments,
        "total_tagged": len(assignments),
        "total_entities": len(entities),
    }), 200


@auto_setup_bp.route("/api/v1/auto-setup/status", methods=["GET"])
def auto_setup_status():
    """Return auto-setup history and status."""
    auth_error = validate_token(request)
    if auth_error:
        return auth_error

    return jsonify({
        "history": _setup_history[-10:],  # Last 10 entries
        "total_runs": len(_setup_history),
    }), 200
