from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
portainer_bp = Blueprint("portainer", __name__, url_prefix="/api/v1/portainer")
@portainer_bp.route("", methods=["GET"])
@require_token
def portainer(): return jsonify({"ok": True})
