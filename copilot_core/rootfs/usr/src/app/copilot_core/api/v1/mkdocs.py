from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mkdocs_bp = Blueprint("mkdocs", __name__, url_prefix="/api/v1/mkdocs")
@mkdocs_bp.route("", methods=["GET"])
@require_token
def mkdocs(): return jsonify({"ok": True})
