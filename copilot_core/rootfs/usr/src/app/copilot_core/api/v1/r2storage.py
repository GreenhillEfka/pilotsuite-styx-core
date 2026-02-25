from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
r2storage_bp = Blueprint("r2storage", __name__, url_prefix="/api/v1/r2storage")
@r2storage_bp.route("", methods=["GET"])
@require_token
def r2storage(): return jsonify({"ok": True})
