from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
php_bp = Blueprint("php", __name__, url_prefix="/api/v1/php")
@php_bp.route("", methods=["GET"])
@require_token
def php(): return jsonify({"ok": True})
