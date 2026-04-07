"""SystemHealth API - Flask blueprint for system health endpoints."""

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_api_key

system_health_bp = Blueprint('system_health', __name__)

# Module-level service reference (set by init_system_health_api)
_service = None


def init_system_health_api(service):
    """Initialize the system health API with a service instance."""
    global _service
    _service = service


def _get_service():
    """Get the SystemHealth service, falling back to global."""
    if _service is not None:
        return _service
    from copilot_core import get_system_health_service
    return get_system_health_service()


@system_health_bp.route('/api/v1/system_health', methods=['GET'])
@require_api_key
def get_system_health():
    """Get complete system health status."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'SystemHealth service not initialized'}), 503
    return jsonify(service.get_full_health())


@system_health_bp.route('/api/v1/system_health/zigbee', methods=['GET'])
@require_api_key
def get_zigbee_health():
    """Get Zigbee mesh health specifically."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'SystemHealth service not initialized'}), 503
    force = request.args.get('force', 'false').lower() == 'true'
    return jsonify(service.get_zigbee_health(force_refresh=force))


@system_health_bp.route('/api/v1/system_health/zwave', methods=['GET'])
@require_api_key
def get_zwave_health():
    """Get Z-Wave mesh health specifically."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'SystemHealth service not initialized'}), 503
    force = request.args.get('force', 'false').lower() == 'true'
    return jsonify(service.get_zwave_health(force_refresh=force))


@system_health_bp.route('/api/v1/system_health/recorder', methods=['GET'])
@require_api_key
def get_recorder_health():
    """Get Recorder database health specifically."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'SystemHealth service not initialized'}), 503
    force = request.args.get('force', 'false').lower() == 'true'
    return jsonify(service.get_recorder_health(force_refresh=force))


@system_health_bp.route('/api/v1/system_health/updates', methods=['GET'])
@require_api_key
def get_update_status():
    """Get update availability specifically."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'SystemHealth service not initialized'}), 503
    force = request.args.get('force', 'false').lower() == 'true'
    return jsonify(service.get_update_status(force_refresh=force))


@system_health_bp.route('/api/v1/system_health/suppress', methods=['GET'])
@require_api_key
def get_suppress_status():
    """Check if suggestions should be suppressed."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'SystemHealth service not initialized'}), 503
    return jsonify(service.should_suppress_suggestions())
