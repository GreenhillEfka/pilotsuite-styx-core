from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cfpages_bp = Blueprint("cfpages", __name__, url_prefix="/api/v1/cfpages")
@cfpages_bp.route("", methods=["GET"])
@require_token
def cfpages(): return jsonify({"ok": True})
