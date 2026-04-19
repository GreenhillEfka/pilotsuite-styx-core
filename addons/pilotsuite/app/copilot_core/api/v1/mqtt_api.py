"""MQTT Status API — F8.5.

GET /api/v1/mqtt/status — return MQTT client connection and broker status.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

from copilot_core.api.security import require_token
from copilot_core.mqtt_client import get_mqtt_client

bp = Blueprint("mqtt_v1", __name__, url_prefix="/api/v1/mqtt")


@bp.route("/status", methods=["GET"])
@require_token
def mqtt_status():
    """Return MQTT client status summary."""
    client = get_mqtt_client()
    summary = client.status_summary()
    return jsonify({
        "ok": True,
        "version": 1,
        "status": summary,
    })