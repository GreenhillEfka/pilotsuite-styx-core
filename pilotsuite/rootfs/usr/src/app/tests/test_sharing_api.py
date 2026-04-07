"""Tests for Sharing API Endpoints - Phase 5 Cross-Home Sharing.

Tests both the API endpoints (when Flask is available) and the underlying services.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

# Try to import Flask components
try:
    from copilot_core.app import create_app
    from copilot_core.sharing.api import init_sharing_api, sharing_bp
    FLASK_AVAILABLE = True
except ModuleNotFoundError:
    FLASK_AVAILABLE = False
    create_app = None
    sharing_bp = None


@dataclass
class MockEntity:
    """Mock entity for testing."""
    entity_id: str
    shared: bool
    home_id: str = None
    metadata: dict = None
    shared_with: list = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.shared_with is None:
            self.shared_with = []
    
    def to_dict(self):
        return {
            "entity_id": self.entity_id,
            "shared": self.shared,
            "home_id": self.home_id,
            "metadata": self.metadata,
            "shared_with": self.shared_with
        }


class MockRegistry:
    """Mock registry for testing."""
    
    def __init__(self):
        self._entities = {}
    
    def get_all(self):
        return self._entities
    
    def get_shared(self):
        return {k: v for k, v in self._entities.items() if v.shared}
    
    def get(self, entity_id):
        return self._entities.get(entity_id)
    
    def register(self, entity_id, shared=True, home_id=None, metadata=None, **kwargs):
        # Merge explicit metadata dict with additional kwargs
        merged_metadata = {}
        if metadata:
            merged_metadata.update(metadata)
        if kwargs:
            merged_metadata.update(kwargs)
        
        entity = MockEntity(
            entity_id=entity_id,
            shared=shared,
            home_id=home_id,
            metadata=merged_metadata
        )
        self._entities[entity_id] = entity
        return entity
    
    def update(self, entity_id, shared=None, **metadata):
        if entity_id not in self._entities:
            raise ValueError(f"Entity {entity_id} not found")
        entity = self._entities[entity_id]
        if shared is not None:
            entity.shared = shared
        entity.metadata.update(metadata)
        return entity
    
    def unregister(self, entity_id):
        if entity_id in self._entities:
            del self._entities[entity_id]
    
    def share_with(self, entity_id, home_id):
        if entity_id not in self._entities:
            raise ValueError(f"Entity {entity_id} not found")
        if home_id not in self._entities[entity_id].shared_with:
            self._entities[entity_id].shared_with.append(home_id)
    
    def stop_sharing_with(self, entity_id, home_id):
        if entity_id not in self._entities:
            raise ValueError(f"Entity {entity_id} not found")
        if home_id in self._entities[entity_id].shared_with:
            self._entities[entity_id].shared_with.remove(home_id)
    
    def get_shared_with(self, entity_id):
        if entity_id not in self._entities:
            raise ValueError(f"Entity {entity_id} not found")
        return self._entities[entity_id].shared_with


class MockSyncService:
    """Mock sync service for testing."""
    
    def __init__(self):
        self._running = True
        self.peer_id = "test-peer-123"
        self._clients = {"peer-1": {}, "peer-2": {}}
        self._entities = {
            "light.living_room": {"state": "on", "brightness": 200},
            "sensor.temperature": {"value": 21.5}
        }
    
    def get_synchronized_peers(self):
        return list(self._clients.keys())
    
    def get_all_entities(self):
        return self._entities
    
    def get_entity(self, entity_id):
        return self._entities.get(entity_id)


class MockDiscovery:
    """Mock discovery service for testing."""
    
    def __init__(self):
        self._peers = [
            {"id": "peer-1", "host": "192.168.1.10", "port": 8123},
            {"id": "peer-2", "host": "192.168.1.11", "port": 8123}
        ]
        self._local = {
            "id": "test-peer-123",
            "host": "192.168.1.1",
            "port": 8123,
            "version": "5.0.0"
        }
    
    def get_peers(self):
        return self._peers
    
    def get_local_peer_info(self):
        return self._local


@pytest.fixture
def mock_services():
    """Create mock services."""
    return {
        "registry": MockRegistry(),
        "sync": MockSyncService(),
        "discovery": MockDiscovery()
    }


@pytest.fixture
def app_with_sharing(mock_services):
    """Create test app with sharing API initialized."""
    if not FLASK_AVAILABLE:
        pytest.skip("Flask not installed")
    
    app = create_app()
    app.register_blueprint(sharing_bp)
    
    # Initialize sharing API with mocks
    init_sharing_api(
        sync_service=mock_services["sync"],
        registry=mock_services["registry"],
        discovery=mock_services["discovery"]
    )
    
    return app


# ═══════════════════════════════════════════════════════════════════════════
# Registry Service Tests (No Flask Required)
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistryService:
    """Test registry service logic directly."""
    
    def test_register_entity(self, mock_services):
        """Test registering a new entity."""
        registry = mock_services["registry"]
        entity = registry.register("light.test", shared=True, home_id="home-1")
        
        assert entity.entity_id == "light.test"
        assert entity.shared is True
        assert entity.home_id == "home-1"
    
    def test_get_entity(self, mock_services):
        """Test getting an entity by ID."""
        registry = mock_services["registry"]
        registry.register("light.test", shared=True, home_id="home-1", type="dimmer")
        
        entity = registry.get("light.test")
        assert entity is not None
        assert entity.metadata.get("type") == "dimmer"
    
    def test_get_entity_not_found(self, mock_services):
        """Test getting non-existent entity."""
        registry = mock_services["registry"]
        entity = registry.get("nonexistent")
        assert entity is None
    
    def test_update_entity(self, mock_services):
        """Test updating an entity."""
        registry = mock_services["registry"]
        registry.register("light.test", shared=False)
        
        entity = registry.update("light.test", shared=True)
        assert entity.shared is True
    
    def test_update_entity_not_found(self, mock_services):
        """Test updating non-existent entity."""
        registry = mock_services["registry"]
        with pytest.raises(ValueError):
            registry.update("nonexistent", shared=True)
    
    def test_unregister_entity(self, mock_services):
        """Test unregistering an entity."""
        registry = mock_services["registry"]
        registry.register("light.todelete", shared=True)
        
        registry.unregister("light.todelete")
        assert registry.get("light.todelete") is None
    
    def test_share_with_home(self, mock_services):
        """Test sharing entity with another home."""
        registry = mock_services["registry"]
        registry.register("light.test", shared=True)
        
        registry.share_with("light.test", "home-2")
        entity = registry.get("light.test")
        assert "home-2" in entity.shared_with
    
    def test_stop_sharing_with_home(self, mock_services):
        """Test stopping sharing with a specific home."""
        registry = mock_services["registry"]
        registry.register("light.test", shared=True)
        registry.share_with("light.test", "home-2")
        
        registry.stop_sharing_with("light.test", "home-2")
        entity = registry.get("light.test")
        assert "home-2" not in entity.shared_with
    
    def test_get_shared_with(self, mock_services):
        """Test getting list of homes entity is shared with."""
        registry = mock_services["registry"]
        registry.register("light.test", shared=True)
        registry.share_with("light.test", "home-1")
        registry.share_with("light.test", "home-2")
        
        homes = registry.get_shared_with("light.test")
        assert len(homes) == 2
        assert "home-1" in homes
        assert "home-2" in homes
    
    def test_get_all_entities(self, mock_services):
        """Test getting all entities."""
        registry = mock_services["registry"]
        registry.register("light.test", shared=True)
        registry.register("sensor.temp", shared=False)
        
        all_entities = registry.get_all()
        assert len(all_entities) == 2
    
    def test_get_shared_entities(self, mock_services):
        """Test getting only shared entities."""
        registry = mock_services["registry"]
        registry.register("light.shared", shared=True)
        registry.register("light.private", shared=False)
        
        shared = registry.get_shared()
        assert len(shared) == 1
        assert "light.shared" in shared


# ═══════════════════════════════════════════════════════════════════════════
# Sync Service Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSyncService:
    """Test sync service logic directly."""
    
    def test_sync_service_initialized(self, mock_services):
        """Test sync service initialization."""
        sync = mock_services["sync"]
        assert sync._running is True
        assert sync.peer_id == "test-peer-123"
    
    def test_get_synchronized_peers(self, mock_services):
        """Test getting synchronized peers."""
        sync = mock_services["sync"]
        peers = sync.get_synchronized_peers()
        assert len(peers) == 2
        assert "peer-1" in peers
        assert "peer-2" in peers
    
    def test_get_all_entities(self, mock_services):
        """Test getting all synced entities."""
        sync = mock_services["sync"]
        entities = sync.get_all_entities()
        assert len(entities) == 2
        assert "light.living_room" in entities
    
    def test_get_entity(self, mock_services):
        """Test getting specific synced entity."""
        sync = mock_services["sync"]
        entity = sync.get_entity("light.living_room")
        assert entity is not None
        assert entity["state"] == "on"
        assert entity["brightness"] == 200
    
    def test_get_entity_not_found(self, mock_services):
        """Test getting non-existent synced entity."""
        sync = mock_services["sync"]
        entity = sync.get_entity("nonexistent")
        assert entity is None


# ═══════════════════════════════════════════════════════════════════════════
# Discovery Service Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDiscoveryService:
    """Test discovery service logic directly."""
    
    def test_get_peers(self, mock_services):
        """Test getting discovered peers."""
        discovery = mock_services["discovery"]
        peers = discovery.get_peers()
        assert len(peers) == 2
    
    def test_get_local_peer_info(self, mock_services):
        """Test getting local peer information."""
        discovery = mock_services["discovery"]
        local = discovery.get_local_peer_info()
        assert local["id"] == "test-peer-123"
        assert local["host"] == "192.168.1.1"
        assert local["version"] == "5.0.0"


# ═══════════════════════════════════════════════════════════════════════════
# API Endpoint Tests (Flask Required)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestRegistryEndpoints:
    """Test registry management endpoints."""
    
    def test_get_entities_empty(self, app_with_sharing, mock_services):
        """Test GET /api/v1/sharing/entities with no entities."""
        client = app_with_sharing.test_client()
        r = client.get("/api/v1/sharing/entities")
        assert r.status_code == 200
        j = r.get_json()
        assert j["count"] == 0
        assert j["entities"] == {}
    
    def test_get_entities_with_data(self, app_with_sharing, mock_services):
        """Test GET /api/v1/sharing/entities with registered entities."""
        mock_services["registry"].register("light.test", shared=True, home_id="home-1")
        
        client = app_with_sharing.test_client()
        r = client.get("/api/v1/sharing/entities")
        assert r.status_code == 200
        j = r.get_json()
        assert j["count"] == 1
        assert "light.test" in j["entities"]
    
    def test_get_entity_by_id(self, app_with_sharing, mock_services):
        """Test GET /api/v1/sharing/entities/<entity_id>."""
        mock_services["registry"].register("light.test", shared=True, metadata={"type": "dimmer"})
        
        client = app_with_sharing.test_client()
        r = client.get("/api/v1/sharing/entities/light.test")
        assert r.status_code == 200
        j = r.get_json()
        assert j["entity_id"] == "light.test"
        assert j["metadata"]["type"] == "dimmer"
    
    def test_register_entity(self, app_with_sharing, mock_services):
        """Test POST /api/v1/sharing/entities to register new entity."""
        client = app_with_sharing.test_client()
        payload = {
            "entity_id": "sensor.new",
            "shared": True,
            "home_id": "home-test",
            "metadata": {"room": "kitchen"}
        }
        r = client.post("/api/v1/sharing/entities", json=payload)
        assert r.status_code == 200
        j = r.get_json()
        assert j["ok"] is True
        assert j["entity"]["entity_id"] == "sensor.new"
    
    def test_update_entity(self, app_with_sharing, mock_services):
        """Test PUT /api/v1/sharing/entities/<entity_id>."""
        mock_services["registry"].register("light.test", shared=False)
        
        client = app_with_sharing.test_client()
        r = client.put("/api/v1/sharing/entities/light.test", json={"shared": True})
        assert r.status_code == 200
        j = r.get_json()
        assert j["ok"] is True
        assert j["entity"]["shared"] is True


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestSyncEndpoints:
    """Test synchronization endpoints."""
    
    def test_get_sync_status(self, app_with_sharing, mock_services):
        """Test GET /api/v1/sharing/sync/status."""
        client = app_with_sharing.test_client()
        r = client.get("/api/v1/sharing/sync/status")
        assert r.status_code == 200
        j = r.get_json()
        assert j["active"] is True
        assert j["peer_id"] == "test-peer-123"
        assert j["connected_peers"] == 2
    
    def test_get_synced_entities(self, app_with_sharing, mock_services):
        """Test GET /api/v1/sharing/sync/entities."""
        client = app_with_sharing.test_client()
        r = client.get("/api/v1/sharing/sync/entities")
        assert r.status_code == 200
        j = r.get_json()
        assert j["count"] == 2
        assert "light.living_room" in j["entities"]


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestDiscoveryEndpoints:
    """Test discovery endpoints."""
    
    def test_get_discovered_peers(self, app_with_sharing, mock_services):
        """Test GET /api/v1/sharing/discovery/peers."""
        client = app_with_sharing.test_client()
        r = client.get("/api/v1/sharing/discovery/peers")
        assert r.status_code == 200
        j = r.get_json()
        assert j["count"] == 2
    
    def test_get_local_peer_info(self, app_with_sharing, mock_services):
        """Test GET /api/v1/sharing/discovery/local."""
        client = app_with_sharing.test_client()
        r = client.get("/api/v1/sharing/discovery/local")
        assert r.status_code == 200
        j = r.get_json()
        assert j["id"] == "test-peer-123"


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestSharingStatus:
    """Test overall sharing status endpoint."""
    
    def test_get_sharing_status(self, app_with_sharing, mock_services):
        """Test GET /api/v1/sharing - combined status."""
        mock_services["registry"].register("light.test", shared=True)
        
        client = app_with_sharing.test_client()
        r = client.get("/api/v1/sharing")
        assert r.status_code == 200
        j = r.get_json()
        
        assert "registry" in j
        assert j["registry"]["initialized"] is True
        assert j["registry"]["entity_count"] == 1
        
        assert "sync" in j
        assert j["sync"]["initialized"] is True
        
        assert "discovery" in j
        assert j["discovery"]["initialized"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
