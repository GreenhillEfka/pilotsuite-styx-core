from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
import_bp = Blueprint("import", __name__, url_prefix="/api/v1/import")
@import_bp.route("", methods=["GET"])
@require_token
def import_api(): return jsonify({"ok": True})
