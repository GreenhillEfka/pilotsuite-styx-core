from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
splunk_bp = Blueprint("splunk", __name__, url_prefix="/api/v1/splunk")
@splunk_bp.route("", methods=["GET"])
@require_token
def splunk(): return jsonify({"ok": True})
