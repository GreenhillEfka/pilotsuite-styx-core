from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pirsch_bp = Blueprint("pirsch", __name__, url_prefix="/api/v1/pirsch")
@pirsch_bp.route("", methods=["GET"])
@require_token
def pirsch(): return jsonify({"ok": True})
