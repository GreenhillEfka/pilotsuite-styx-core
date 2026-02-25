from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
auditlog_bp = Blueprint("auditlog", __name__, url_prefix="/api/v1/auditlog")
@auditlog_bp.route("", methods=["GET"])
@require_token
def auditlog(): return jsonify({"ok": True})
