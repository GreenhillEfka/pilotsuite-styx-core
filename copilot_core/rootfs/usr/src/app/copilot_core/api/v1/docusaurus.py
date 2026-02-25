from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
docusaurus_bp = Blueprint("docusaurus", __name__, url_prefix="/api/v1/docusaurus")
@docusaurus_bp.route("", methods=["GET"])
@require_token
def docusaurus(): return jsonify({"ok": True})
