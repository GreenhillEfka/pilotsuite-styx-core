from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
document_bp = Blueprint("document", __name__, url_prefix="/api/v1/document")
@document_bp.route("", methods=["GET"])
@require_token
def document(): return jsonify({"ok": True})
