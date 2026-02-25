from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
puppet_bp = Blueprint("puppet", __name__, url_prefix="/api/v1/puppet")
@puppet_bp.route("", methods=["GET"])
@require_token
def puppet(): return jsonify({"ok": True})
