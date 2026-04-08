"""Collective Intelligence API - Flask blueprint for federated learning endpoints."""

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_api_key

federated_bp = Blueprint('federated', __name__)

# Module-level service reference (set by init_federated_api)
_service = None


def init_federated_api(service):
    """Initialize the federated API with a service instance."""
    global _service
    _service = service


def _get_service():
    """Get the CollectiveIntelligence service, falling back to global."""
    if _service is not None:
        return _service
    from copilot_core import get_federated_service
    return get_federated_service()


@federated_bp.route('/api/v1/federated', methods=['GET'])
@require_api_key
def get_status():
    """Get federated learning system status."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    status = service.get_status()
    return jsonify(status.to_dict())


@federated_bp.route('/api/v1/federated/start', methods=['POST'])
@require_api_key
def start_service():
    """Start the federated learning service."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    service.start()
    return jsonify({'ok': True, 'message': 'Federated service started'})


@federated_bp.route('/api/v1/federated/stop', methods=['POST'])
@require_api_key
def stop_service():
    """Stop the federated learning service."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    service.stop()
    return jsonify({'ok': True, 'message': 'Federated service stopped'})


@federated_bp.route('/api/v1/federated/register', methods=['POST'])
@require_api_key
def register_node():
    """Register a new home node for federated learning."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data = request.get_json(silent=True) or {}
    node_id = data.get('node_id')
    max_epsilon = data.get('max_epsilon', 1.0)
    
    if not node_id:
        return jsonify({'error': 'node_id required'}), 400
    
    success = service.register_node(node_id, max_epsilon)
    return jsonify({
        'ok': success,
        'node_id': node_id,
        'message': 'Node registered' if success else 'Failed to register node'
    })


@federated_bp.route('/api/v1/federated/update', methods=['POST'])
@require_api_key
def submit_update():
    """Submit a local model update from a node."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data = request.get_json(silent=True) or {}
    node_id = data.get('node_id')
    weights = data.get('weights')
    metrics = data.get('metrics')
    
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


@federated_bp.route('/api/v1/federated/round', methods=['POST'])
@require_api_key
def start_round():
    """Start a new federated learning round."""
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


@federated_bp.route('/api/v1/federated/aggregate', methods=['POST'])
@require_api_key
def execute_aggregation():
    """Execute aggregation for a round."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data = request.get_json(silent=True) or {}
    round_id = data.get('round_id')
    
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


@federated_bp.route('/api/v1/federated/knowledge', methods=['POST'])
@require_api_key
def extract_knowledge():
    """Extract knowledge from a node for transfer."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data = request.get_json(silent=True) or {}
    node_id = data.get('node_id')
    knowledge_type = data.get('knowledge_type')
    payload = data.get('payload')
    confidence = data.get('confidence', 1.0)
    
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


@federated_bp.route('/api/v1/federated/knowledge/<knowledge_id>/transfer', methods=['POST'])
@require_api_key
def transfer_knowledge(knowledge_id: str):
    """Transfer knowledge to another node."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data = request.get_json(silent=True) or {}
    target_node_id = data.get('target_node_id')
    
    if not target_node_id:
        return jsonify({'error': 'target_node_id required'}), 400
    
    success = service.transfer_knowledge(knowledge_id, target_node_id)
    
    return jsonify({
        'ok': success,
        'knowledge_id': knowledge_id,
        'target_node_id': target_node_id
    })


@federated_bp.route('/api/v1/federated/rounds', methods=['GET'])
@require_api_key
def get_round_history():
    """Get history of federated rounds."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    rounds = service.get_federated_round_history()
    
    return jsonify({
        'count': len(rounds),
        'rounds': [r.to_dict() for r in rounds]
    })


@federated_bp.route('/api/v1/federated/models', methods=['GET'])
@require_api_key
def get_aggregated_models():
    """Get all aggregated models."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    models = service.get_aggregated_models()
    
    return jsonify({
        'count': len(models),
        'models': {k: v.to_dict() for k, v in models.items()}
    })


@federated_bp.route('/api/v1/federated/knowledge-base', methods=['GET'])
@require_api_key
def get_knowledge_base():
    """Get the knowledge transfer base."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    knowledge = service.get_knowledge_base()
    
    return jsonify({
        'count': len(knowledge),
        'items': {k: v.to_dict() for k, v in knowledge.items()}
    })


@federated_bp.route('/api/v1/federated/statistics', methods=['GET'])
@require_api_key
def get_statistics():
    """Get comprehensive federated learning statistics."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    return jsonify(service.get_statistics())


@federated_bp.route('/api/v1/federated/save', methods=['POST'])
@require_api_key
def save_state():
    """Save system state to file."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data = request.get_json(silent=True) or {}
    path = data.get('path', '/config/.copilot/federated_state.json')
    
    success = service.save_state(path)
    return jsonify({
        'ok': success,
        'path': path
    })


@federated_bp.route('/api/v1/federated/load', methods=['POST'])
@require_api_key
def load_state():
    """Load system state from file."""
    service = _get_service()
    if service is None:
        return jsonify({'error': 'Federated service not initialized'}), 503
    
    data = request.get_json(silent=True) or {}
    path = data.get('path', '/config/.copilot/federated_state.json')
    
    success = service.load_state(path)
    return jsonify({
        'ok': success,
        'path': path
    })