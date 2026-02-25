"""
Templates API - PilotSuite v7.28.0
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

templates_bp = Blueprint("templates", __name__, url_prefix="/api/v1/templates")


@templates_bp.route("/render", methods=["POST"])
@require_token
def render_template():
    """Render a Jinja2 template."""
    data = request.get_json() or {}
    template_str = data.get("template")
    
    if not template_str:
        return jsonify({"error": "template string required"}), 400
    
    try:
        from homeassistant.helpers import template
        hass = None
        try:
            from homeassistant.core import HomeAssistant
            hass = HomeAssistant.get()
        except:
            pass
        
        if hass:
            tpl = template.Template(template_str, hass)
            result = tpl.async_render()
        else:
            from jinja2 import Template
            tpl = Template(template_str)
            result = tpl.render()
        
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
