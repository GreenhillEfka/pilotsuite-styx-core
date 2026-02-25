from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
graylog_bp = Blueprint("graylog", __name__, url_prefix="/api/v1/graylog")
@graylog_bp.route("", methods=["GET"])
@require_token
def graylog(): return jsonify({"ok": True})
