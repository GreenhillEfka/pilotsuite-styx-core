from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
drm_bp = Blueprint("drm", __name__, url_prefix="/api/v1/drm")
@drm_bp.route("", methods=["GET"])
@require_token
def drm(): return jsonify({"ok": True})
