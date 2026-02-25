from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
weavenet_bp = Blueprint("weavenet", __name__, url_prefix="/api/v1/weavenet")
@weavenet_bp.route("", methods=["GET"])
@require_token
def weavenet(): return jsonify({"ok": True})
