from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gcs_bp = Blueprint("gcs", __name__, url_prefix="/api/v1/gcs")
@gcs_bp.route("", methods=["GET"])
@require_token
def gcs(): return jsonify({"ok": True})
