from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vagrant_bp = Blueprint("vagrant", __name__, url_prefix="/api/v1/vagrant")
@vagrant_bp.route("", methods=["GET"])
@require_token
def vagrant(): return jsonify({"ok": True})
