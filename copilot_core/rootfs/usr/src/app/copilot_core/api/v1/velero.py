from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
velero_bp = Blueprint("velero", __name__, url_prefix="/api/v1/velero")
@velero_bp.route("", methods=["GET"])
@require_token
def velero(): return jsonify({"ok": True})
