"""REST API endpoints for dev surface observability."""
from flask import Blueprint, request, jsonify

from copilot_core.api.security import require_api_key
from .service import dev_surface


dev_surface_bp = Blueprint('dev_surface', __name__, url_prefix='/api/v1/dev')


@dev_surface_bp.route('/logs', methods=['GET'])
@require_api_key
def get_logs():
    """Get recent log entries with optional filtering."""
    try:
        limit = request.args.get('limit', type=int)
        level = request.args.get('level')
        
        logs = dev_surface.get_recent_logs(limit=limit, level_filter=level)
        
        return jsonify({
            "status": "success",
            "logs": logs,
            "total": len(logs)
        })
    
    except Exception as e:
        return jsonify({
            "status": "error", 
            "error": str(e)
        }), 500


@dev_surface_bp.route('/errors', methods=['GET'])
@require_api_key 
def get_error_summary():
    """Get error summary and statistics."""
    try:
        summary = dev_surface.get_error_summary()
        
        return jsonify({
            "status": "success",
            "error_summary": summary.to_dict()
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e) 
        }), 500


@dev_surface_bp.route('/health', methods=['GET'])
@require_api_key
def get_health():
    """Get system health snapshot."""
    try:
        # Try to get brain graph service from app context
        brain_graph_service = getattr(get_health, '_brain_graph_service', None)
        
        health = dev_surface.get_system_health(brain_graph_service)
        
        return jsonify({
            "status": "success",
            "health": health.to_dict()
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@dev_surface_bp.route('/diagnostics', methods=['GET'])
@require_api_key
def export_diagnostics():
    """Export comprehensive diagnostics data."""
    try:
        diagnostics = dev_surface.export_diagnostics()
        
        return jsonify({
            "status": "success",
            "diagnostics": diagnostics
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@dev_surface_bp.route('/clear', methods=['POST'])
@require_api_key
def clear_logs():
    """Clear all log entries and reset counters."""
    try:
        dev_surface.clear_logs()
        
        return jsonify({
            "status": "success",
            "message": "Logs and counters cleared"
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


def init_dev_surface_api(brain_graph_service=None):
    """Initialize the dev surface API with dependencies."""
    # Store brain graph service for health endpoint
    get_health._brain_graph_service = brain_graph_service