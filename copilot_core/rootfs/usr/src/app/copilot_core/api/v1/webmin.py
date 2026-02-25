from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
webmin_bp = Blueprint("webmin", __name__, url_prefix="/api/v1/webmin")
@webmin_bp.route("", methods=["GET"])
@require_token
def webmin(): return jsonify({"ok": True})
