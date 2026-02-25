from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
storage_bp = Blueprint("storage", __name__, url_prefix="/api/v1/storage")
@storage_bp.route("", methods=["GET"])
@require_token
def storage(): return jsonify({"ok": True})
