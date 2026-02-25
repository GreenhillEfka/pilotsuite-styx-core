from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
duplicati_bp = Blueprint("duplicati", __name__, url_prefix="/api/v1/duplicati")
@duplicati_bp.route("", methods=["GET"])
@require_token
def duplicati(): return jsonify({"ok": True})
