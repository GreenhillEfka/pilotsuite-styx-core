from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dockerdesktop_bp = Blueprint("dockerdesktop", __name__, url_prefix="/api/v1/dockerdesktop")
@dockerdesktop_bp.route("", methods=["GET"])
@require_token
def dockerdesktop(): return jsonify({"ok": True})
