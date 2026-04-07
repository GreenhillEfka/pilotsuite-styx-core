"""Cross-Home Sharing API - Flask blueprint for sync and discovery endpoints.

Phase 5: Cross-Home Sharing & Collective Intelligence
Provides REST endpoints for:
- Entity Registry: Register, share, and manage cross-home entities
- Sync Service: WebSocket-based synchronization between homes
- Discovery: mDNS/Bonjour discovery of peer CoPilot instances

Endpoints:
- /api/v1/sharing/* - Registry management (10 endpoints)
- /api/v1/sharing/sync/* - Synchronization status (4 endpoints)
- /api/v1/sharing/discovery/* - Peer discovery (2 endpoints)
- /api/v1/sharing - Combined system status
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_api_key

sharing_bp = Blueprint('sharing', __name__)

# Module-level service references (set by init_sharing_api)
_sync_service: Optional[Any] = None
_registry: Optional[Any] = None
_discovery: Optional[Any] = None


def init_sharing_api(
    sync_service: Optional[Any] = None,
    registry: Optional[Any] = None,
    discovery: Optional[Any] = None,
) -> None:
    """Initialize the sharing API with service instances.
    
    Args:
        sync_service: SyncProtocol instance for entity synchronization
        registry: SharedRegistry instance for entity management
        discovery: DiscoveryService instance for peer discovery
    """
    global _sync_service, _registry, _discovery
    _sync_service = sync_service
    _registry = registry
    _discovery = discovery


def _get_registry() -> Optional[Any]:
    """Get the shared registry.
    
    Returns:
        SharedRegistry instance or None if not initialized
    """
    if _registry is not None:
        return _registry
    # Try to get singleton from core/sharing
    try:
        from sharing import get_registry
        return get_registry()
    except ImportError:
        return None


def _get_sync() -> Optional[Any]:
    """Get the sync service.
    
    Returns:
        SyncProtocol instance or None if not initialized
    """
    return _sync_service


def _get_discovery() -> Optional[Any]:
    """Get the discovery service.
    
    Returns:
        DiscoveryService instance or None if not initialized
    """
    return _discovery


# ==================== Registry Endpoints ====================

@sharing_bp.route('/sharing/entities', methods=['GET'])
@require_api_key
def get_entities() -> tuple:
    """Get all registered shared entities.
    
    Returns:
        JSON response with count and entities dict
    """
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    entities = registry.get_all()
    return jsonify({
        'count': len(entities),
        'entities': {k: v.to_dict() for k, v in entities.items()}
    })


@sharing_bp.route('/sharing/entities/shared', methods=['GET'])
@require_api_key
def get_shared_entities() -> tuple:
    """Get all shared entities (filtered).
    
    Returns:
        JSON response with count and shared entities dict
    """
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    entities = registry.get_shared()
    return jsonify({
        'count': len(entities),
        'entities': {k: v.to_dict() for k, v in entities.items()}
    })


@sharing_bp.route('/sharing/entities/<entity_id>', methods=['GET'])
@require_api_key
def get_entity(entity_id: str) -> tuple:
    """Get a specific shared entity.
    
    Args:
        entity_id: The entity identifier
        
    Returns:
        JSON response with entity data
    """
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    entity = registry.get(entity_id)
    if entity is None:
        return jsonify({'error': 'Entity not found'}), 404
    
    return jsonify(entity.to_dict())


@sharing_bp.route('/sharing/entities', methods=['POST'])
@require_api_key
def register_entity() -> tuple:
    """Register an entity for sharing.
    
    Request JSON:
        {
            "entity_id": str,
            "shared": bool (default: true),
            "home_id": str (optional),
            "metadata": dict (optional)
        }
    
    Returns:
        JSON response with ok status and entity data
    """
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


@sharing_bp.route('/sharing/entities/<entity_id>', methods=['PUT'])
@require_api_key
def update_entity(entity_id: str) -> tuple:
    """Update an entity's sharing configuration.
    
    Args:
        entity_id: The entity identifier
        
    Request JSON:
        {
            "shared": bool (optional),
            ...additional metadata fields
        }
    
    Returns:
        JSON response with ok status and updated entity
    """
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


@sharing_bp.route('/sharing/entities/<entity_id>', methods=['DELETE'])
@require_api_key
def unregister_entity(entity_id: str) -> tuple:
    """Unregister an entity from sharing.
    
    Args:
        entity_id: The entity identifier
        
    Returns:
        JSON response with ok status
    """
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    registry.unregister(entity_id)
    return jsonify({'ok': True, 'entity_id': entity_id})


@sharing_bp.route('/sharing/entities/<entity_id>/share-with', methods=['POST'])
@require_api_key
def share_with_home(entity_id: str) -> tuple:
    """Share an entity with another home.
    
    Args:
        entity_id: The entity identifier
        
    Request JSON:
        {"home_id": str}
    
    Returns:
        JSON response with ok status
    """
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


@sharing_bp.route('/sharing/entities/<entity_id>/stop-sharing/<home_id>', methods=['POST'])
@require_api_key
def stop_sharing_with_home(entity_id: str, home_id: str) -> tuple:
    """Stop sharing an entity with a specific home.
    
    Args:
        entity_id: The entity identifier
        home_id: The home to stop sharing with
        
    Returns:
        JSON response with ok status
    """
    registry = _get_registry()
    if registry is None:
        return jsonify({'error': 'Sharing registry not initialized'}), 503
    
    try:
        registry.stop_sharing_with(entity_id, home_id)
        return jsonify({'ok': True, 'entity_id': entity_id, 'home_id': home_id})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@sharing_bp.route('/sharing/entities/<entity_id>/shared-with', methods=['GET'])
@require_api_key
def get_shared_with(entity_id: str) -> tuple:
    """Get list of homes this entity is shared with.
    
    Args:
        entity_id: The entity identifier
        
    Returns:
        JSON response with list of home IDs
    """
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

@sharing_bp.route('/sharing/sync/status', methods=['GET'])
@require_api_key
def get_sync_status() -> tuple:
    """Get sync service status.
    
    Returns:
        JSON response with sync service status
    """
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


@sharing_bp.route('/sharing/sync/entities', methods=['GET'])
@require_api_key
def get_synced_entities() -> tuple:
    """Get all synchronized entities from sync service.
    
    Returns:
        JSON response with synced entities
    """
    sync = _get_sync()
    if sync is None:
        return jsonify({'error': 'Sync service not initialized'}), 503
    
    entities = sync.get_all_entities()
    return jsonify({
        'count': len(entities),
        'entities': entities
    })


@sharing_bp.route('/sharing/sync/entities/<entity_id>', methods=['GET'])
@require_api_key
def get_synced_entity(entity_id: str) -> tuple:
    """Get a specific synchronized entity.
    
    Args:
        entity_id: The entity identifier
        
    Returns:
        JSON response with entity data
    """
    sync = _get_sync()
    if sync is None:
        return jsonify({'error': 'Sync service not initialized'}), 503
    
    entity = sync.get_entity(entity_id)
    if entity is None:
        return jsonify({'error': 'Entity not found'}), 404
    
    return jsonify(entity)


@sharing_bp.route('/sharing/sync/peers', methods=['GET'])
@require_api_key
def get_sync_peers() -> tuple:
    """Get list of synchronized peers.
    
    Returns:
        JSON response with peer list
    """
    sync = _get_sync()
    if sync is None:
        return jsonify({'error': 'Sync service not initialized'}), 503
    
    return jsonify({
        'synchronized_peers': list(sync.get_synchronized_peers()),
        'count': len(sync.get_synchronized_peers())
    })


# ==================== Discovery Endpoints ====================

@sharing_bp.route('/sharing/discovery/peers', methods=['GET'])
@require_api_key
def get_discovered_peers() -> tuple:
    """Get discovered CoPilot peers.
    
    Returns:
        JSON response with discovered peers
    """
    discovery = _get_discovery()
    if discovery is None:
        return jsonify({'error': 'Discovery service not initialized'}), 503
    
    peers = discovery.get_peers()
    return jsonify({
        'count': len(peers),
        'peers': peers
    })


@sharing_bp.route('/sharing/discovery/local', methods=['GET'])
@require_api_key
def get_local_peer_info() -> tuple:
    """Get local peer information.
    
    Returns:
        JSON response with local peer info
    """
    discovery = _get_discovery()
    if discovery is None:
        return jsonify({'error': 'Discovery service not initialized'}), 503
    
    return jsonify(discovery.get_local_peer_info())


# ==================== Combined Status ====================

@sharing_bp.route('/sharing', methods=['GET'])
@require_api_key
def get_sharing_status() -> tuple:
    """Get overall sharing system status.
    
    Returns:
        JSON response with registry, sync, and discovery status
    """
    registry = _get_registry()
    sync = _get_sync()
    discovery = _get_discovery()
    
    status: Dict[str, Any] = {
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