from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
openshift_bp = Blueprint("openshift", __name__, url_prefix="/api/v1/openshift")
@openshift_bp.route("", methods=["GET"])
@require_token
def openshift(): return jsonify({"ok": True})
