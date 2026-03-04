"""Collective Intelligence API - Flask blueprint for federated learning endpoints.

Phase 5: Collective Intelligence / Federated Learning
Provides REST endpoints for federated learning operations across multiple homes.

Endpoints:
- GET /api/v1/federated - Get system status
- POST /api/v1/federated/start - Start federated learning service
- POST /api/v1/federated/stop - Stop federated learning service
- POST /api/v1/federated/register - Register a new home node
- POST /api/v1/federated/update - Submit local model update
- POST /api/v1/federated/round - Start a new federated round
- POST /api/v1/federated/aggregate - Execute aggregation for a round
- POST /api/v1/federated/knowledge - Extract knowledge from a node
- POST /api/v1/federated/knowledge/<id>/transfer - Transfer knowledge to another node
- GET /api/v1/federated/rounds - Get round history
- GET /api/v1/federated/models - Get aggregated models
- GET /api/v1/federated/knowledge-base - Get knowledge transfer base
- GET /api/v1/federated/statistics - Get comprehensive statistics
- POST /api/v1/federated/save - Save system state to file
- POST /api/v1/federated/load - Load system state from file

All endpoints require API key authentication via @require_api_key decorator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from flask import Blueprint, Request, jsonify, request

if TYPE_CHECKING:
    from copilot_core.collective_intelligence.service import CollectiveIntelligenceService

from copilot_core.api.security import require_api_key

federated_bp = Blueprint('federated', __name__)

# Module-level service reference (set by init_federated_api)
_service: Optional[CollectiveIntelligenceService] = None


def init_federated_api(service: CollectiveIntelligenceService) -> None:
    """Initialize the federated API with a service instance.
    
    Args:
        service: CollectiveIntelligenceService instance for federated learning.
    """
    global _service
    _service = service


def _get_service() -> Optional[CollectiveIntelligenceService]:
    """Get the CollectiveIntelligence service, falling back to global.
    
    Returns:
        Optional[CollectiveIntelligenceService]: Service instance or None if not available.
    """
    if _service is not None:
        return _service
    from copilot_core import get_federated_service
    return get_federated_service()


@federated_bp.route('/federated', methods=['GET'])
@require_api_key
def get_status() -> Tuple[Dict[str, Any], int]:
    """Get federated learning system status.
    
    Returns:
        Tuple[Dict[str, Any], int]: Status dictionary and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    status = service.get_status()
    return jsonify(status.to_dict())


@federated_bp.route('/federated/start', methods=['POST'])
@require_api_key
def start_service() -> Tuple[Dict[str, Any], int]:
    """Start the federated learning service.
    
    Returns:
        Tuple[Dict[str, Any], int]: Success response and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    service.start()
    return jsonify({'ok': True, 'message': 'Federated service started'})


@federated_bp.route('/federated/stop', methods=['POST'])
@require_api_key
def stop_service() -> Tuple[Dict[str, Any], int]:
    """Stop the federated learning service.
    
    Returns:
        Tuple[Dict[str, Any], int]: Success response and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    service.stop()
    return jsonify({'ok': True, 'message': 'Federated service stopped'})


@federated_bp.route('/federated/register', methods=['POST'])
@require_api_key
def register_node() -> Tuple[Dict[str, Any], int]:
    """Register a new home node for federated learning.
    
    Request body:
        {
            "node_id": str,
            "max_epsilon": float (optional, default 1.0)
        }
    
    Returns:
        Tuple[Dict[str, Any], int]: Registration result and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    node_id: Optional[str] = data.get('node_id')
    max_epsilon: float = data.get('max_epsilon', 1.0)
    
    if not node_id:
        return jsonify({'error': 'node_id required'}), 400
    
    success = service.register_node(node_id, max_epsilon)
    return jsonify({
        'ok': success,
        'node_id': node_id,
        'message': 'Node registered' if success else 'Failed to register node'
    })


@federated_bp.route('/federated/update', methods=['POST'])
@require_api_key
def submit_update() -> Tuple[Dict[str, Any], int]:
    """Submit a local model update from a node.
    
    Request body:
        {
            "node_id": str,
            "weights": dict,
            "metrics": dict (optional)
        }
    
    Returns:
        Tuple[Dict[str, Any], int]: Update result with update_id and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    node_id: Optional[str] = data.get('node_id')
    weights: Optional[Dict[str, Any]] = data.get('weights')
    metrics: Optional[Dict[str, Any]] = data.get('metrics')
    
    if not node_id or not weights:
        return jsonify({'error': 'node_id and weights required'}), 400
    
    update = service.submit_local_update(node_id, weights, metrics)
    
    if update:
        return jsonify({
            'ok': True,
            'update_id': update.update_id,
            'timestamp': update.timestamp
        })
    else:
        return jsonify({'ok': False, 'error': 'Failed to submit update'}), 500


@federated_bp.route('/federated/round', methods=['POST'])
@require_api_key
def start_round() -> Tuple[Dict[str, Any], int]:
    """Start a new federated learning round.
    
    Returns:
        Tuple[Dict[str, Any], int]: Round result with round_id and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    round_id = service.start_federated_round()
    
    if round_id:
        return jsonify({
            'ok': True,
            'round_id': round_id
        })
    else:
        return jsonify({'ok': False, 'error': 'Failed to start round'}), 500


@federated_bp.route('/federated/aggregate', methods=['POST'])
@require_api_key
def execute_aggregation() -> Tuple[Dict[str, Any], int]:
    """Execute aggregation for a round.
    
    Request body:
        {
            "round_id": str
        }
    
    Returns:
        Tuple[Dict[str, Any], int]: Aggregation result with model details and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    round_id: Optional[str] = data.get('round_id')
    
    if not round_id:
        return jsonify({'error': 'round_id required'}), 400
    
    aggregated = service.execute_aggregation(round_id)
    
    if aggregated:
        return jsonify({
            'ok': True,
            'model_version': aggregated.model_version,
            'participants': aggregated.participants,
            'metrics': aggregated.metrics,
            'privacy_loss': aggregated.privacy_loss
        })
    else:
        return jsonify({'ok': False, 'error': 'Failed to aggregate'}), 500


@federated_bp.route('/federated/knowledge', methods=['POST'])
@require_api_key
def extract_knowledge() -> Tuple[Dict[str, Any], int]:
    """Extract knowledge from a node for transfer.
    
    Request body:
        {
            "node_id": str,
            "knowledge_type": str,
            "payload": dict,
            "confidence": float (optional, default 1.0)
        }
    
    Returns:
        Tuple[Dict[str, Any], int]: Knowledge extraction result and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    node_id: Optional[str] = data.get('node_id')
    knowledge_type: Optional[str] = data.get('knowledge_type')
    payload: Optional[Dict[str, Any]] = data.get('payload')
    confidence: float = data.get('confidence', 1.0)
    
    if not node_id or not knowledge_type or not payload:
        return jsonify({'error': 'node_id, knowledge_type, and payload required'}), 400
    
    item = service.extract_knowledge(node_id, knowledge_type, payload, confidence)
    
    if item:
        return jsonify({
            'ok': True,
            'knowledge_id': item.knowledge_id,
            'knowledge_hash': item.knowledge_hash
        })
    else:
        return jsonify({'ok': False, 'error': 'Failed to extract knowledge'}), 500


@federated_bp.route('/federated/knowledge/<knowledge_id>/transfer', methods=['POST'])
@require_api_key
def transfer_knowledge(knowledge_id: str) -> Tuple[Dict[str, Any], int]:
    """Transfer knowledge to another node.
    
    Args:
        knowledge_id: ID of the knowledge item to transfer.
    
    Request body:
        {
            "target_node_id": str
        }
    
    Returns:
        Tuple[Dict[str, Any], int]: Transfer result and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    target_node_id: Optional[str] = data.get('target_node_id')
    
    if not target_node_id:
        return jsonify({'error': 'target_node_id required'}), 400
    
    success = service.transfer_knowledge(knowledge_id, target_node_id)
    
    return jsonify({
        'ok': success,
        'knowledge_id': knowledge_id,
        'target_node_id': target_node_id
    })


@federated_bp.route('/federated/rounds', methods=['GET'])
@require_api_key
def get_round_history() -> Tuple[Dict[str, Any], int]:
    """Get history of federated rounds.
    
    Returns:
        Tuple[Dict[str, Any], int]: Round history list and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    rounds = service.get_federated_round_history()
    
    return jsonify({
        'count': len(rounds),
        'rounds': [r.to_dict() for r in rounds]
    })


@federated_bp.route('/federated/models', methods=['GET'])
@require_api_key
def get_aggregated_models() -> Tuple[Dict[str, Any], int]:
    """Get all aggregated models.
    
    Returns:
        Tuple[Dict[str, Any], int]: Aggregated models dictionary and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    models = service.get_aggregated_models()
    
    return jsonify({
        'count': len(models),
        'models': {k: v.to_dict() for k, v in models.items()}
    })


@federated_bp.route('/federated/knowledge-base', methods=['GET'])
@require_api_key
def get_knowledge_base() -> Tuple[Dict[str, Any], int]:
    """Get the knowledge transfer base.
    
    Returns:
        Tuple[Dict[str, Any], int]: Knowledge base items and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    knowledge = service.get_knowledge_base()
    
    return jsonify({
        'count': len(knowledge),
        'items': {k: v.to_dict() for k, v in knowledge.items()}
    })


@federated_bp.route('/federated/statistics', methods=['GET'])
@require_api_key
def get_statistics() -> Tuple[Dict[str, Any], int]:
    """Get comprehensive federated learning statistics.
    
    Returns:
        Tuple[Dict[str, Any], int]: Statistics dictionary and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    return jsonify(service.get_statistics())


@federated_bp.route('/federated/save', methods=['POST'])
@require_api_key
def save_state() -> Tuple[Dict[str, Any], int]:
    """Save system state to file.
    
    Request body:
        {
            "path": str (optional, default '/config/.copilot/federated_state.json')
        }
    
    Returns:
        Tuple[Dict[str, Any], int]: Save result and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    path: str = data.get('path', '/config/.copilot/federated_state.json')
    
    try:
        success = service.save_state(path)
        return jsonify({
            'ok': success,
            'path': path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@federated_bp.route('/federated/load', methods=['POST'])
@require_api_key
def load_state() -> Tuple[Dict[str, Any], int]:
    """Load system state from file.
    
    Request body:
        {
            "path": str (optional, default '/config/.copilot/federated_state.json')
        }
    
    Returns:
        Tuple[Dict[str, Any], int]: Load result and HTTP status code.
    """
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    path: str = data.get('path', '/config/.copilot/federated_state.json')
    
    success = service.load_state(path)
    return jsonify({
        'ok': success,
        'path': path
    })


__all__ = [
    'federated_bp',
    'init_federated_api',
    'get_status',
    'start_service',
    'stop_service',
    'register_node',
    'submit_update',
    'start_round',
    'execute_aggregation',
    'extract_knowledge',
    'transfer_knowledge',
    'get_round_history',
    'get_aggregated_models',
    'get_knowledge_base',
    'get_statistics',
    'save_state',
    'load_state',
]