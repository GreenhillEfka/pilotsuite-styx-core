from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
katello_bp = Blueprint("katello", __name__, url_prefix="/api/v1/katello")
@katello_bp.route("", methods=["GET"])
@require_token
def katello(): return jsonify({"ok": True})
