from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
openebs_bp = Blueprint("openebs", __name__, url_prefix="/api/v1/openebs")
@openebs_bp.route("", methods=["GET"])
@require_token
def openebs(): return jsonify({"ok": True})
