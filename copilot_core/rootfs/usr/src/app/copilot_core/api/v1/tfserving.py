from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tfserving_bp = Blueprint("tfserving", __name__, url_prefix="/api/v1/tfserving")
@tfserving_bp.route("", methods=["GET"])
@require_token
def tfserving(): return jsonify({"ok": True})
