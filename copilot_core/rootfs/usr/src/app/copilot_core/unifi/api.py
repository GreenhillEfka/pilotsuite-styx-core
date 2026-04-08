"""
UniFi Network Monitoring REST API

Flask blueprint for UniFi neuron endpoints.
Provides network context for PilotSuite suggestions.
"""

import logging
from flask import Blueprint, jsonify, request
from functools import wraps

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

# Global service instance (set during init)
_unifi_service = None


def set_unifi_service(service):
    """Set the global UniFi service instance."""
    global _unifi_service
    _unifi_service = service


def get_unifi_service():
    """Get the global UniFi service instance."""
    return _unifi_service


unifi_bp = Blueprint('unifi', __name__, url_prefix='/api/v1/unifi')


@unifi_bp.route('', methods=['GET'])
@require_token
async def get_unifi():
    """
    Get complete UniFi network snapshot.
    
    Returns:
        JSON with WAN status, clients, roaming events, and baselines.
    """
    if not _unifi_service:
        return jsonify({'error': 'UniFi service not initialized'}), 503
    
    snapshot = await _unifi_service.get_snapshot()
    
    return jsonify({
        'wan': {
            'online': snapshot.wan.online,
            'latency_ms': snapshot.wan.latency_ms,
            'packet_loss_percent': snapshot.wan.packet_loss_percent,
            'uptime_seconds': snapshot.wan.uptime_seconds,
            'ip_address': snapshot.wan.ip_address,
            'last_check': snapshot.wan.last_check
        },
        'clients': [
            {
                'mac': c.mac,
                'name': c.name,
                'ip': c.ip,
                'status': c.status,
                'device_type': c.device_type,
                'connected_ap': c.connected_ap,
                'signal_dbm': c.signal_dbm,
                'roaming': c.roaming,
                'last_seen': c.last_seen
            }
            for c in snapshot.clients
        ],
        'roaming_events': [
            {
                'client_mac': r.client_mac,
                'client_name': r.client_name,
                'from_ap': r.from_ap,
                'to_ap': r.to_ap,
                'timestamp': r.timestamp,
                'signal_strength': r.signal_strength
            }
            for r in snapshot.roaming_events
        ],
        'baselines': {
            'period': snapshot.baselines.period,
            'avg_upload_mbps': snapshot.baselines.avg_upload_mbps,
            'avg_download_mbps': snapshot.baselines.avg_download_mbps,
            'peak_upload_mbps': snapshot.baselines.peak_upload_mbps,
            'peak_download_mbps': snapshot.baselines.peak_download_mbps,
            'total_bytes_up': snapshot.baselines.total_bytes_up,
            'total_bytes_down': snapshot.baselines.total_bytes_down,
            'last_updated': snapshot.baselines.last_updated
        },
        'suppress_suggestions': snapshot.suppress_suggestions,
        'suppression_reason': snapshot.suppression_reason,
        'timestamp': snapshot.timestamp
    })


@unifi_bp.route('/wan', methods=['GET'])
@require_token
async def get_wan_status():
    """
    Get WAN uplink status only.
    
    Returns:
        JSON with WAN status details.
    """
    if not _unifi_service:
        return jsonify({'error': 'UniFi service not initialized'}), 503
    
    wan = await _unifi_service.get_wan_status()
    
    return jsonify({
        'online': wan.online,
        'latency_ms': wan.latency_ms,
        'packet_loss_percent': wan.packet_loss_percent,
        'uptime_seconds': wan.uptime_seconds,
        'ip_address': wan.ip_address,
        'gateway': wan.gateway,
        'dns_servers': wan.dns_servers,
        'last_check': wan.last_check
    })


@unifi_bp.route('/clients', methods=['GET'])
@require_token
async def get_clients():
    """
    Get list of connected clients.
    
    Query params:
        - status: Filter by status (online/offline)
        - type: Filter by device type (phone/laptop/iot/unknown)
    
    Returns:
        JSON array of client devices.
    """
    if not _unifi_service:
        return jsonify({'error': 'UniFi service not initialized'}), 503
    
    clients = await _unifi_service.get_clients()
    
    # Apply filters
    status_filter = request.args.get('status')
    type_filter = request.args.get('type')
    
    if status_filter:
        clients = [c for c in clients if c.status == status_filter]
    if type_filter:
        clients = [c for c in clients if c.device_type == type_filter]
    
    return jsonify([
        {
            'mac': c.mac,
            'name': c.name,
            'ip': c.ip,
            'status': c.status,
            'device_type': c.device_type,
            'connected_ap': c.connected_ap,
            'signal_dbm': c.signal_dbm,
            'roaming': c.roaming,
            'last_seen': c.last_seen
        }
        for c in clients
    ])


@unifi_bp.route('/roaming', methods=['GET'])
@require_token
async def get_roaming():
    """
    Get recent roaming events.
    
    Returns:
        JSON array of roaming events.
    """
    if not _unifi_service:
        return jsonify({'error': 'UniFi service not initialized'}), 503
    
    roams = await _unifi_service.get_roaming_events()
    
    return jsonify([
        {
            'client_mac': r.client_mac,
            'client_name': r.client_name,
            'from_ap': r.from_ap,
            'to_ap': r.to_ap,
            'timestamp': r.timestamp,
            'signal_strength': r.signal_strength
        }
        for r in roams
    ])


@unifi_bp.route('/baselines', methods=['GET'])
@require_token
async def get_baselines():
    """
    Get traffic baselines.
    
    Returns:
        JSON with traffic baseline metrics.
    """
    if not _unifi_service:
        return jsonify({'error': 'UniFi service not initialized'}), 503
    
    baselines = await _unifi_service.get_baselines()
    
    return jsonify({
        'period': baselines.period,
        'avg_upload_mbps': baselines.avg_upload_mbps,
        'avg_download_mbps': baselines.avg_download_mbps,
        'peak_upload_mbps': baselines.peak_upload_mbps,
        'peak_download_mbps': baselines.peak_download_mbps,
        'total_bytes_up': baselines.total_bytes_up,
        'total_bytes_down': baselines.total_bytes_down,
        'last_updated': baselines.last_updated
    })


@unifi_bp.route('/suppress', methods=['GET'])
@require_token
async def get_suppress():
    """
    Check if network context suggests suppressing suggestions.
    
    Returns:
        JSON with suppression status and reason.
    """
    if not _unifi_service:
        return jsonify({'error': 'UniFi service not initialized'}), 503
    
    suppress, reason = await _unifi_service.should_suppress_suggestions()
    
    return jsonify({
        'suppress': suppress,
        'reason': reason
    })


@unifi_bp.route('/health', methods=['GET'])
@require_token
async def health():
    """
    Health check endpoint.
    
    Returns:
        JSON with service status.
    """
    if not _unifi_service:
        return jsonify({
            'status': 'unhealthy',
            'reason': 'UniFi service not initialized'
        }), 503
    
    snapshot = await _unifi_service.get_snapshot()
    
    return jsonify({
        'status': 'healthy' if snapshot.wan.online else 'degraded',
        'wan_online': snapshot.wan.online,
        'client_count': len(snapshot.clients),
        'last_update': snapshot.timestamp
    })
