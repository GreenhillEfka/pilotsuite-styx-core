"""Comfort Index API endpoints (v5.7.0)."""

from flask import Blueprint, jsonify, request

from ..api.security import require_api_key
from .index import calculate_comfort_index, get_lighting_suggestion

comfort_bp = Blueprint("comfort", __name__)


@comfort_bp.route("/api/v1/comfort", methods=["GET"])
@require_api_key
def get_comfort():
    """Get comfort index for a zone.

    Query params:
        temperature: Temperature in Celsius
        humidity: Relative humidity %
        co2: CO2 ppm
        lux: Light level in lux
        zone: Zone ID
    """
    temp = request.args.get("temperature", type=float)
    humidity = request.args.get("humidity", type=float)
    co2 = request.args.get("co2", type=float)
    lux = request.args.get("lux", type=float)
    zone_id = request.args.get("zone")

    index = calculate_comfort_index(
        temperature_c=temp,
        humidity_pct=humidity,
        co2_ppm=co2,
        light_lux=lux,
        zone_id=zone_id,
    )

    return jsonify({
        "ok": True,
        "score": index.score,
        "grade": index.grade,
        "zone_id": index.zone_id,
        "readings": [
            {
                "factor": r.factor,
                "raw_value": r.raw_value,
                "score": round(r.score, 1),
                "weight": r.weight,
                "status": r.status,
            }
            for r in index.readings
        ],
        "suggestions": index.suggestions,
        "timestamp": index.timestamp,
    })


@comfort_bp.route("/api/v1/comfort/lighting", methods=["GET"])
@require_api_key
def get_lighting():
    """Get adaptive lighting suggestion.

    Query params:
        lux: Current light level
        cloud_cover: Cloud cover % (0-100)
        area: Room/area name
    """
    lux = request.args.get("lux", type=float)
    cloud = request.args.get("cloud_cover", 50.0, type=float)
    area = request.args.get("area", "Wohnzimmer")

    suggestion = get_lighting_suggestion(
        current_lux=lux,
        cloud_cover_pct=cloud,
        area=area,
    )

    return jsonify({
        "ok": True,
        "area": suggestion.area,
        "current_lux": suggestion.current_lux,
        "target_lux": suggestion.target_lux,
        "brightness_percent": suggestion.brightness_percent,
        "color_temp_kelvin": suggestion.color_temp_kelvin,
        "reason": suggestion.reason,
    })
