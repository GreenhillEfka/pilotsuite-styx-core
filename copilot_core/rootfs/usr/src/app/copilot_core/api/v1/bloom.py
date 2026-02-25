from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
bloom_bp = Blueprint("bloom", __name__, url_prefix="/api/v1/bloom")
@bloom_bp.route("", methods=["GET"])
@require_token
def bloom(): return jsonify({"ok": True})
