"""Cross-Home Sharing API - Flask blueprint for sync and discovery endpoints."""

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_api_key

sharing_bp = Blueprint('sharing', __name__)

# Module-level service references (set by init_sharing_api)
_sync_service = None
_registry = None
_discovery = None


def init_sharing_api(sync_service=None, registry=None, discovery=None):
    """Initialize the sharing API with service instances."""
    global _sync_service, _registry, _discovery
    _sync_service = sync_service
    _registry = registry
    _discovery = discovery


def _get_registry():
    """Get the shared registry."""
    if _registry is not None:
        return _registry
    # Try to get singleton from core/sharing
    try:
        from sharing import get_registry
        return get_registry()
    except ImportError:
        return None


def _get_sync():
    """Get the sync service."""
    return _sync_service


def _get_discovery():
    """Get the discovery service."""
    return _discovery


# ==================== Registry Endpoints ====================

@sharing_bp.route('/api/v1/sharing/entities', methods=['GET'])
@require_api_key
def get_entities():
    """Get all registered shared entities."""
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    entities = registry.get_all()
    return jsonify({
        'count': len(entities),
        'entities': {k: v.to_dict() for k, v in entities.items()}
    })


@sharing_bp.route('/api/v1/sharing/entities/shared', methods=['GET'])
@require_api_key
def get_shared_entities():
    """Get all shared entities (filtered)."""
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    entities = registry.get_shared()
    return jsonify({
        'count': len(entities),
        'entities': {k: v.to_dict() for k, v in entities.items()}
    })


@sharing_bp.route('/api/v1/sharing/entities/<entity_id>', methods=['GET'])
@require_api_key
def get_entity(entity_id: str):
    """Get a specific shared entity."""
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    entity = registry.get(entity_id)
    if entity is None:
        return jsonify({'error': 'Entity not found'}), 404
    
    return jsonify(entity.to_dict())


@sharing_bp.route('/api/v1/sharing/entities', methods=['POST'])
@require_api_key
def register_entity():
    """Register an entity for sharing."""
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    data = request.get_json(silent=True) or {}
    entity_id = data.get('entity_id')
    shared = data.get('shared', True)
    home_id = data.get('home_id')
    metadata = data.get('metadata', {})
    
    if not entity_id:
        return jsonify({'error': 'entity_id required'}), 400
    
    entity = registry.register(entity_id, shared=shared, home_id=home_id, **metadata)
    return jsonify({
        'ok': True,
        'entity': entity.to_dict()
    })


@sharing_bp.route('/api/v1/sharing/entities/<entity_id>', methods=['PUT'])
@require_api_key
def update_entity(entity_id: str):
    """Update an entity's sharing configuration."""
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    data = request.get_json(silent=True) or {}
    shared = data.get('shared')
    metadata = {k: v for k, v in data.items() if k not in ['shared']}
    
    try:
        entity = registry.update(entity_id, shared=shared, **metadata)
        return jsonify({
            'ok': True,
            'entity': entity.to_dict()
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@sharing_bp.route('/api/v1/sharing/entities/<entity_id>', methods=['DELETE'])
@require_api_key
def unregister_entity(entity_id: str):
    """Unregister an entity from sharing."""
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    registry.unregister(entity_id)
    return jsonify({'ok': True, 'entity_id': entity_id})


@sharing_bp.route('/api/v1/sharing/entities/<entity_id>/share-with', methods=['POST'])
@require_api_key
def share_with_home(entity_id: str):
    """Share an entity with another home."""
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    data = request.get_json(silent=True) or {}
    home_id = data.get('home_id')
    
    if not home_id:
        return jsonify({'error': 'home_id required'}), 400
    
    try:
        registry.share_with(entity_id, home_id)
        return jsonify({'ok': True, 'entity_id': entity_id, 'home_id': home_id})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@sharing_bp.route('/api/v1/sharing/entities/<entity_id>/stop-sharing/<home_id>', methods=['POST'])
@require_api_key
def stop_sharing_with_home(entity_id: str, home_id: str):
    """Stop sharing an entity with a specific home."""
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    registry.stop_sharing_with(entity_id, home_id)
    return jsonify({'ok': True, 'entity_id': entity_id, 'home_id': home_id})


@sharing_bp.route('/api/v1/sharing/entities/<entity_id>/shared-with', methods=['GET'])
@require_api_key
def get_shared_with(entity_id: str):
    """Get list of homes this entity is shared with."""
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    home_ids = registry.get_shared_with(entity_id)
    return jsonify({
        'entity_id': entity_id,
        'shared_with': list(home_ids),
        'count': len(home_ids)
    })


# ==================== Sync Endpoints ====================

@sharing_bp.route('/api/v1/sharing/sync/status', methods=['GET'])
@require_api_key
def get_sync_status():
    """Get sync service status."""
    sync = _get_sync()
    if sync is None:
        return jsonify({'error': 'Sync service not initialized', 'active': False}), 503
    
    return jsonify({
        'active': sync._running,
        'peer_id': sync.peer_id,
        'connected_peers': len(sync._clients),
        'synchronized_peers': list(sync.get_synchronized_peers()),
        'entity_count': len(sync._entities)
    })


@sharing_bp.route('/api/v1/sharing/sync/entities', methods=['GET'])
@require_api_key
def get_synced_entities():
    """Get all synchronized entities from sync service."""
    sync = _get_sync()
    if sync is None:
        return jsonify({'error': 'Sync service not initialized'}), 503
    
    entities = sync.get_all_entities()
    return jsonify({
        'count': len(entities),
        'entities': entities
    })


@sharing_bp.route('/api/v1/sharing/sync/entities/<entity_id>', methods=['GET'])
@require_api_key
def get_synced_entity(entity_id: str):
    """Get a specific synchronized entity."""
    sync = _get_sync()
    if sync is None:
        return jsonify({'error': 'Sync service not initialized'}), 503
    
    entity = sync.get_entity(entity_id)
    if entity is None:
        return jsonify({'error': 'Entity not found'}), 404
    
    return jsonify(entity)


@sharing_bp.route('/api/v1/sharing/sync/peers', methods=['GET'])
@require_api_key
def get_sync_peers():
    """Get list of synchronized peers."""
    sync = _get_sync()
    if sync is None:
        return jsonify({'error': 'Sync service not initialized'}), 503
    
    return jsonify({
        'synchronized_peers': list(sync.get_synchronized_peers()),
        'count': len(sync.get_synchronized_peers())
    })


# ==================== Discovery Endpoints ====================

@sharing_bp.route('/api/v1/sharing/discovery/peers', methods=['GET'])
@require_api_key
def get_discovered_peers():
    """Get discovered CoPilot peers."""
    discovery = _get_discovery()
    if discovery is None:
        return jsonify({'error': 'Discovery service not initialized'}), 503
    
    peers = discovery.get_peers()
    return jsonify({
        'count': len(peers),
        'peers': peers
    })


@sharing_bp.route('/api/v1/sharing/discovery/local', methods=['GET'])
@require_api_key
def get_local_peer_info():
    """Get local peer information."""
    discovery = _get_discovery()
    if discovery is None:
        return jsonify({'error': 'Discovery service not initialized'}), 503
    
    return jsonify(discovery.get_local_peer_info())


# ==================== Combined Status ====================

@sharing_bp.route('/api/v1/sharing', methods=['GET'])
@require_api_key
def get_sharing_status():
    """Get overall sharing system status."""
    registry = _get_registry()
    sync = _get_sync()
    discovery = _get_discovery()
    
    status = {
        'registry': {
            'initialized': registry is not None,
            'entity_count': len(registry.get_all()) if registry else 0,
            'shared_count': len(registry.get_shared()) if registry else 0
        },
        'sync': {
            'initialized': sync is not None,
            'active': sync._running if sync else False,
            'peer_count': len(sync._clients) if sync else 0
        },
        'discovery': {
            'initialized': discovery is not None,
            'peer_count': len(discovery.get_peers()) if discovery else 0
        }
    }
    
    return jsonify(status)