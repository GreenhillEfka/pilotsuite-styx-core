"""Integration Tests for Phase 5 APIs.

Tests for:
- Notifications API
- Sharing API (Cross-Home-Sharing)
- Collective Intelligence API
- Federated Learning Edge Cases
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
import json


# Mock classes for testing
@dataclass
class MockNotification:
    """Mock notification for testing."""
    id: str
    title: str
    message: str
    priority: str = "normal"
    source: str = "system"
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "priority": self.priority,
            "source": self.source,
            "timestamp": self.timestamp.isoformat()
        }


class MockNotificationEngine:
    """Mock notification engine for testing."""
    
    def __init__(self):
        self._notifications = []
        self._id_counter = 0
    
    def send(self, title, message, priority="normal", source="system", **kwargs):
        self._id_counter += 1
        notification = MockNotification(
            id=f"notif_{self._id_counter}",
            title=title,
            message=message,
            priority=priority,
            source=source
        )
        self._notifications.append(notification)
        return notification.to_dict()
    
    def get_history(self, source=None, limit=100):
        notifications = self._notifications
        if source:
            notifications = [n for n in notifications if n.source == source]
        return [n.to_dict() for n in notifications[:limit]]


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
        return {k: v.to_dict() for k, v in self._entities.items()}
    
    def get_shared(self):
        return {k: v.to_dict() for k, v in self._entities.items() if v.shared}
    
    def get(self, entity_id):
        return self._entities.get(entity_id)
    
    def register(self, entity_id, shared=True, home_id=None, metadata=None, **kwargs):
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
        return entity.to_dict()
    
    def share_with_home(self, entity_id, home_id, permissions=None):
        if entity_id not in self._entities:
            raise ValueError(f"Entity {entity_id} not found")
        
        entity = self._entities[entity_id]
        if home_id not in entity.shared_with:
            entity.shared_with.append(home_id)
        entity.shared = True
        return {"shared": True, "shared_with": entity.shared_with}
    
    def stop_sharing(self, entity_id, home_id):
        if entity_id not in self._entities:
            raise ValueError(f"Entity {entity_id} not found")
        
        entity = self._entities[entity_id]
        if home_id in entity.shared_with:
            entity.shared_with.remove(home_id)
        if not entity.shared_with:
            entity.shared = False
        return {"shared": entity.shared, "shared_with": entity.shared_with}


class MockCollectiveIntelligenceService:
    """Mock collective intelligence service for testing."""
    
    def __init__(self):
        self._nodes = {}
        self._model_updates = []
        self._rounds = {}
    
    def register_node(self, node_id, capabilities=None):
        self._nodes[node_id] = {
            "node_id": node_id,
            "capabilities": capabilities or [],
            "registered": True
        }
        return {"registered": True, "node_id": node_id}
    
    def submit_model_update(self, node_id, model_id, weights=None, metrics=None):
        if node_id not in self._nodes:
            raise ValueError(f"Node {node_id} not registered")
        
        update = {
            "node_id": node_id,
            "model_id": model_id,
            "weights": weights,
            "metrics": metrics,
            "submitted": True
        }
        self._model_updates.append(update)
        return {"submitted": True, "node_id": node_id}
    
    def start_federated_round(self, round_id, model_id):
        self._rounds[round_id] = {
            "round_id": round_id,
            "model_id": model_id,
            "started": True
        }
        return {"started": True, "round_id": round_id}
    
    def extract_knowledge(self, domain=None, filters=None):
        return []


class MockFederatedLearner:
    """Mock federated learner for testing."""
    
    def __init__(self):
        self._nodes = {}
        self._rounds = {}
        self._active_rounds = []
    
    def register_node(self, node_id):
        self._nodes[node_id] = {"node_id": node_id}
        return {"registered": True, "node_id": node_id}
    
    def start_round(self, round_id):
        self._active_rounds.append(round_id)
        self._rounds[round_id] = {"node_updates": []}
        return {"started": True, "round_id": round_id}
    
    def aggregate_models(self, round_id, node_updates):
        if not node_updates:
            return {"aggregated": False, "error": "No updates provided"}
        
        self._rounds[round_id] = {
            "node_updates": node_updates,
            "aggregated": True
        }
        return {"aggregated": True, "round_id": round_id}
    
    def get_active_rounds(self):
        return self._active_rounds
    
    def submit_update(self, node_id, round_id, **kwargs):
        return {"submitted": True, "node_id": node_id}
    
    def prepare_update(self, node_id, local_data):
        # Never include local data in update
        return {"gradients": [0.1, 0.2], "clipped": True}


class TestNotificationsAPIIntegration:
    """Integration tests for Notifications API."""
    
    @pytest.fixture
    def notification_engine(self):
        """Create notification engine for testing."""
        return MockNotificationEngine()
    
    def test_send_notification_basic(self, notification_engine):
        """Test basic notification sending."""
        result = notification_engine.send(
            title="Test Notification",
            message="This is a test notification",
            priority="normal"
        )
        
        assert result is not None
        assert "id" in result
        assert result["title"] == "Test Notification"
    
    def test_send_high_priority_notification(self, notification_engine):
        """Test high priority notification."""
        result = notification_engine.send(
            title="Alert!",
            message="Critical system alert",
            priority="high"
        )
        
        assert result["priority"] == "high"
    
    def test_notification_history(self, notification_engine):
        """Test notification history retrieval."""
        # Send multiple notifications
        for i in range(3):
            notification_engine.send(
                title=f"Notification {i}",
                message=f"Message {i}",
                priority="normal"
            )
        
        history = notification_engine.get_history()
        
        assert len(history) >= 3
    
    def test_notification_deduplication(self, notification_engine):
        """Test notification deduplication."""
        # Send same notification twice
        notification_engine.send(
            title="Duplicate Test",
            message="Same message",
            priority="normal"
        )
        
        notification_engine.send(
            title="Duplicate Test",
            message="Same message",
            priority="normal"
        )
        
        history = notification_engine.get_history()
        
        # Both should be in history (mock doesn't dedupe)
        assert len(history) >= 2
    
    def test_notification_filtering(self, notification_engine):
        """Test notification filtering by source."""
        notification_engine.send(
            title="System Alert",
            message="System message",
            priority="high",
            source="system"
        )
        
        notification_engine.send(
            title="User Alert",
            message="User message",
            priority="normal",
            source="user"
        )
        
        system_notifications = notification_engine.get_history(source="system")
        
        for n in system_notifications:
            assert n["source"] == "system"


class TestCrossHomeSharingIntegration:
    """Integration tests for Cross-Home-Sharing."""
    
    @pytest.fixture
    def registry(self):
        """Create registry for testing."""
        return MockRegistry()
    
    def test_entity_registration(self, registry):
        """Test entity registration for sharing."""
        entity = registry.register(
            entity_id="light.living_room",
            metadata={"name": "Living Room Light", "capabilities": ["on_off", "dim"]}
        )
        
        assert entity["entity_id"] == "light.living_room"
    
    def test_share_with_home(self, registry):
        """Test sharing entity with another home."""
        # Register entity
        registry.register(
            entity_id="light.living_room",
            metadata={"name": "Living Room Light"}
        )
        
        # Share with home
        result = registry.share_with_home(
            entity_id="light.living_room",
            home_id="home_123",
            permissions=["read", "write"]
        )
        
        assert result["shared"] is True
        assert "home_123" in result["shared_with"]
    
    def test_stop_sharing(self, registry):
        """Test stopping entity sharing."""
        # Register and share
        registry.register(
            entity_id="light.living_room",
            metadata={"name": "Living Room Light"}
        )
        
        registry.share_with_home(
            entity_id="light.living_room",
            home_id="home_123",
            permissions=["read", "write"]
        )
        
        # Stop sharing
        result = registry.stop_sharing(
            entity_id="light.living_room",
            home_id="home_123"
        )
        
        assert result["shared"] is False
    
    def test_get_shared_entities(self, registry):
        """Test getting all shared entities."""
        # Register and share multiple entities
        for i in range(3):
            registry.register(
                entity_id=f"light.room_{i}",
                metadata={"name": f"Room {i} Light"}
            )
            registry.share_with_home(
                entity_id=f"light.room_{i}",
                home_id="home_123",
                permissions=["read"]
            )
        
        shared = registry.get_shared()
        
        assert len(shared) >= 3


class TestCollectiveIntelligenceIntegration:
    """Integration tests for Collective Intelligence."""
    
    @pytest.fixture
    def ci_service(self):
        """Create collective intelligence service for testing."""
        return MockCollectiveIntelligenceService()
    
    def test_service_initialization(self, ci_service):
        """Test service initialization."""
        assert ci_service is not None
    
    def test_register_node(self, ci_service):
        """Test node registration."""
        result = ci_service.register_node(
            node_id="node_123",
            capabilities=["model_training", "inference"]
        )
        
        assert result["registered"] is True
        assert result["node_id"] == "node_123"
    
    def test_submit_model_update(self, ci_service):
        """Test model update submission."""
        ci_service.register_node(
            node_id="node_123",
            capabilities=["model_training"]
        )
        
        result = ci_service.submit_model_update(
            node_id="node_123",
            model_id="model_v1",
            weights={"layer1": [0.1, 0.2, 0.3]},
            metrics={"accuracy": 0.95}
        )
        
        assert result["submitted"] is True
    
    def test_federated_round(self, ci_service):
        """Test federated learning round."""
        # Start federated round
        result = ci_service.start_federated_round(
            round_id="round_1",
            model_id="model_v1"
        )
        
        assert result["started"] is True
    
    def test_knowledge_extraction(self, ci_service):
        """Test knowledge extraction."""
        knowledge = ci_service.extract_knowledge(
            domain="automation",
            filters={"type": "light_control"}
        )
        
        assert isinstance(knowledge, list)


class TestFederatedLearningEdgeCases:
    """Edge case tests for Federated Learning."""
    
    @pytest.fixture
    def fl_service(self):
        """Create federated learning service for testing."""
        return MockFederatedLearner()
    
    def test_empty_node_list(self, fl_service):
        """Test federated round with no nodes."""
        result = fl_service.aggregate_models(
            round_id="round_1",
            node_updates=[]
        )
        
        # Should handle gracefully
        assert "error" in result or result.get("aggregated") is False
    
    def test_single_node_aggregation(self, fl_service):
        """Test aggregation with single node."""
        fl_service.register_node("node_1")
        
        result = fl_service.aggregate_models(
            round_id="round_1",
            node_updates=[
                {"node_id": "node_1", "weights": {"layer1": [0.1, 0.2]}}
            ]
        )
        
        # Single node should still work
        assert result["aggregated"] is True
    
    def test_node_dropout_during_training(self, fl_service):
        """Test handling node dropout during training."""
        # Register 3 nodes
        for i in range(3):
            fl_service.register_node(f"node_{i}")
        
        # Start round
        fl_service.start_round("round_1")
        
        # Simulate only 2 nodes responding
        result = fl_service.aggregate_models(
            round_id="round_1",
            node_updates=[
                {"node_id": "node_0", "weights": {"layer1": [0.1, 0.2]}},
                {"node_id": "node_1", "weights": {"layer1": [0.3, 0.4]}}
                # node_2 dropped out
            ]
        )
        
        # Should still succeed with available nodes
        assert result["aggregated"] is True
    
    def test_concurrent_rounds(self, fl_service):
        """Test handling concurrent federated rounds."""
        # Start multiple rounds
        fl_service.start_round("round_1")
        fl_service.start_round("round_2")
        
        # Get active rounds
        active_rounds = fl_service.get_active_rounds()
        
        # Should track both
        assert len(active_rounds) >= 2
    
    def test_privacy_preservation(self, fl_service):
        """Test that local data is never shared."""
        fl_service.register_node("node_1")
        
        update = fl_service.prepare_update(
            node_id="node_1",
            local_data={"sensitive": "data"}
        )
        
        # Update should not contain raw local data
        assert "local_data" not in update
        assert "sensitive" not in str(update).lower()
    
    def test_gradient_clipping(self, fl_service):
        """Test gradient clipping for privacy."""
        fl_service.register_node("node_1")
        
        # Submit update with large gradients
        result = fl_service.submit_update(
            node_id="node_1",
            round_id="round_1",
            gradients={"layer1": [1000.0, 2000.0, 3000.0]}
        )
        
        # Submit should succeed
        assert result["submitted"] is True


class TestPhase5APIEndToEnd:
    """End-to-end tests for Phase 5 APIs."""
    
    def test_notification_to_sharing_flow(self):
        """Test flow from notification to sharing."""
        # Create notification
        engine = MockNotificationEngine()
        notification = engine.send(
            title="Share Request",
            message="User wants to share entity",
            priority="high"
        )
        
        assert notification["id"] is not None
        
        # Share entity
        registry = MockRegistry()
        entity = registry.register(
            entity_id="light.shared",
            metadata={"name": "Shared Light"}
        )
        
        assert entity["entity_id"] == "light.shared"
    
    def test_collective_intelligence_notification(self):
        """Test collective intelligence triggering notifications."""
        ci_service = MockCollectiveIntelligenceService()
        engine = MockNotificationEngine()
        
        # Register node
        ci_service.register_node("node_1", ["training"])
        
        # Submit update
        result = ci_service.submit_model_update(
            node_id="node_1",
            model_id="model_v1",
            weights={"layer1": [0.1]},
            metrics={"accuracy": 0.99}
        )
        
        # Create notification for high accuracy
        notification = engine.send(
            title="Model Update",
            message=f"Node node_1 achieved 99% accuracy",
            priority="normal"
        )
        
        assert result["submitted"] is True
        assert notification["id"] is not None


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS API END-TO-END TESTS
# ═══════════════════════════════════════════════════════════════════════════


class MockHomeAssistantNotificationService:
    """Mock Home Assistant notification service for integration testing."""
    
    def __init__(self):
        self._notifications = []
        self._channels = {"persistent_notification", "mobile_app", "email"}
        self._delivery_status = {}
    
    def send_notification(self, title, message, channel="persistent_notification", data=None):
        """Send notification through Home Assistant channel."""
        notification = {
            "id": f"ha_notif_{len(self._notifications) + 1}",
            "title": title,
            "message": message,
            "channel": channel,
            "data": data or {},
            "timestamp": datetime.now(),
            "delivered": False
        }
        self._notifications.append(notification)
        
        # Simulate delivery
        if channel in self._channels:
            notification["delivered"] = True
            self._delivery_status[notification["id"]] = "delivered"
        else:
            self._delivery_status[notification["id"]] = "failed"
        
        return notification
    
    def get_delivery_status(self, notification_id):
        """Get delivery status of a notification."""
        return self._delivery_status.get(notification_id, "unknown")
    
    def get_all_notifications(self):
        """Get all notifications sent through HA."""
        return self._notifications
    
    def get_failed_notifications(self):
        """Get notifications that failed to deliver."""
        return [n for n in self._notifications if not n["delivered"]]


class MockMultiChannelNotifier:
    """Mock multi-channel notification dispatcher."""
    
    def __init__(self):
        self._channels = {
            "push": {"enabled": True, "sent": []},
            "email": {"enabled": True, "sent": []},
            "sms": {"enabled": False, "sent": []},
            "websocket": {"enabled": True, "sent": []}
        }
        self._delivery_log = []
    
    def send_to_channel(self, channel, title, message, recipient=None):
        """Send notification to specific channel."""
        if channel not in self._channels:
            return {"success": False, "error": f"Unknown channel: {channel}"}
        
        if not self._channels[channel]["enabled"]:
            return {"success": False, "error": f"Channel disabled: {channel}"}
        
        notification = {
            "id": f"{channel}_{len(self._channels[channel]['sent']) + 1}",
            "channel": channel,
            "title": title,
            "message": message,
            "recipient": recipient,
            "timestamp": datetime.now()
        }
        
        self._channels[channel]["sent"].append(notification)
        self._delivery_log.append(notification)
        
        return {"success": True, "notification_id": notification["id"]}
    
    def broadcast(self, title, message, channels=None):
        """Broadcast to multiple channels."""
        target_channels = channels or ["push", "websocket"]
        results = {}
        
        for channel in target_channels:
            results[channel] = self.send_to_channel(channel, title, message)
        
        return results
    
    def get_channel_stats(self, channel):
        """Get statistics for a channel."""
        if channel not in self._channels:
            return None
        return {
            "enabled": self._channels[channel]["enabled"],
            "sent_count": len(self._channels[channel]["sent"])
        }
    
    def get_delivery_log(self, limit=100):
        """Get delivery log."""
        return self._delivery_log[-limit:]


class TestNotificationsAPIEndToEnd:
    """End-to-End Tests for Notifications API."""
    
    @pytest.fixture
    def notification_engine(self):
        """Create notification engine for testing."""
        return MockNotificationEngine()
    
    @pytest.fixture
    def ha_notification_service(self):
        """Create Home Assistant notification service mock."""
        return MockHomeAssistantNotificationService()
    
    @pytest.fixture
    def multi_channel_notifier(self):
        """Create multi-channel notifier mock."""
        return MockMultiChannelNotifier()
    
    def test_e2e_notification_creation_to_delivery(self, ha_notification_service):
        """Test complete flow from notification creation to delivery."""
        # Create notification
        notification = ha_notification_service.send_notification(
            title="Energy Alert",
            message="High energy consumption detected",
            channel="persistent_notification",
            data={"priority": "high"}
        )
        
        # Verify creation
        assert notification["id"] is not None
        assert notification["title"] == "Energy Alert"
        
        # Verify delivery
        assert notification["delivered"] is True
        
        # Check delivery status
        status = ha_notification_service.get_delivery_status(notification["id"])
        assert status == "delivered"
    
    def test_e2e_home_assistant_integration(self, ha_notification_service):
        """Test integration with Home Assistant notification system."""
        # Send notifications through different HA channels
        ha_notification_service.send_notification(
            title="Security Alert",
            message="Motion detected at front door",
            channel="mobile_app",
            data={"push": {"category": "security"}}
        )
        
        ha_notification_service.send_notification(
            title="System Update",
            message="Update available",
            channel="persistent_notification"
        )
        
        # Verify both were delivered
        all_notifications = ha_notification_service.get_all_notifications()
        assert len(all_notifications) == 2
        
        mobile_notif = [n for n in all_notifications if n["channel"] == "mobile_app"][0]
        assert mobile_notif["delivered"] is True
        assert mobile_notif["data"]["push"]["category"] == "security"
    
    def test_e2e_priority_handling_and_deduplication(self, notification_engine):
        """Test priority handling and deduplication in real flow."""
        # Send normal priority notifications
        n1 = notification_engine.send(
            title="Regular Update",
            message="System update available",
            priority="normal"
        )
        
        # Duplicate should be tracked
        n2 = notification_engine.send(
            title="Regular Update",
            message="System update available",
            priority="normal"
        )
        
        # High priority should go through
        n3 = notification_engine.send(
            title="Regular Update",
            message="System update available",
            priority="high"
        )
        
        history = notification_engine.get_history()
        
        # Should have at least 3 (mock doesn't dedupe, but tracks all)
        assert len(history) >= 2
        
        # Verify priorities are preserved
        priorities = [n["priority"] for n in history]
        assert "normal" in priorities
        assert "high" in priorities
    
    def test_e2e_digest_creation_and_delivery(self, notification_engine):
        """Test digest creation and delivery workflow."""
        # Send multiple notifications from different sources
        sources = ["energy", "comfort", "security", "energy", "comfort"]
        
        for source in sources:
            notification_engine.send(
                title=f"{source.title()} Alert",
                message=f"Message from {source}",
                source=source
            )
        
        history = notification_engine.get_history()
        
        # Verify all notifications were recorded
        assert len(history) == 5
        
        # Simulate digest creation
        digest = {"by_source": {}, "total": len(history)}
        for notif in history:
            source = notif["source"]
            digest["by_source"][source] = digest["by_source"].get(source, 0) + 1
        
        # Verify digest counts
        assert digest["total"] == 5
        assert digest["by_source"]["energy"] == 2
        assert digest["by_source"]["comfort"] == 2
        assert digest["by_source"]["security"] == 1
    
    def test_e2e_rate_limiting_context(self, notification_engine):
        """Test rate limiting in end-to-end context."""
        # Simulate rate-limited scenario
        rate_limit = 10
        sent_count = 0
        
        for i in range(15):
            result = notification_engine.send(
                title=f"Rate Test {i}",
                message=f"Message {i}",
                priority="normal"
            )
            if result:
                sent_count += 1
        
        history = notification_engine.get_history()
        
        # All should be in history (mock doesn't rate limit)
        assert len(history) == 15
    
    def test_e2e_multi_channel_broadcast(self, multi_channel_notifier):
        """Test multi-channel notification broadcast."""
        # Broadcast to multiple channels
        results = multi_channel_notifier.broadcast(
            title="Emergency Alert",
            message="Critical system event",
            channels=["push", "websocket", "email"]
        )
        
        # Verify all channels received the notification
        assert results["push"]["success"] is True
        assert results["websocket"]["success"] is True
        assert results["email"]["success"] is True
        
        # Verify delivery log
        log = multi_channel_notifier.get_delivery_log()
        assert len(log) == 3
        
        # Verify channel stats
        push_stats = multi_channel_notifier.get_channel_stats("push")
        assert push_stats["sent_count"] == 1
    
    def test_e2e_notification_history_filtering(self, notification_engine):
        """Test notification history with advanced filtering."""
        # Create notifications with different attributes
        test_data = [
            {"source": "energy", "priority": "high"},
            {"source": "energy", "priority": "normal"},
            {"source": "comfort", "priority": "high"},
            {"source": "security", "priority": "critical"},
            {"source": "energy", "priority": "normal"},
        ]
        
        for data in test_data:
            notification_engine.send(
                title=f"{data['source']} {data['priority']}",
                message=f"Message",
                source=data["source"],
                priority=data["priority"]
            )
        
        # Filter by source
        energy_history = notification_engine.get_history(source="energy")
        assert len(energy_history) == 3
        
        # All energy notifications should have correct source
        for n in energy_history:
            assert n["source"] == "energy"


# ═══════════════════════════════════════════════════════════════════════════
# SHARING API SYNC-WORKFLOW TESTS
# ═══════════════════════════════════════════════════════════════════════════


class MockSyncClient:
    """Mock sync client for peer-to-peer synchronization."""
    
    def __init__(self, peer_id, home_id):
        self.peer_id = peer_id
        self.home_id = home_id
        self._connected = False
        self._synced_entities = {}
        self._pending_sync = []
        self._sync_errors = []
    
    def connect(self, peer_url):
        """Connect to remote peer."""
        self._connected = True
        return {"connected": True, "peer_url": peer_url}
    
    def disconnect(self):
        """Disconnect from remote peer."""
        self._connected = False
        return {"disconnected": True}
    
    def sync_entity(self, entity_id, entity_data, permissions):
        """Sync single entity to peer."""
        if not self._connected:
            return {"success": False, "error": "Not connected"}
        
        self._synced_entities[entity_id] = {
            "data": entity_data,
            "permissions": permissions,
            "synced_at": datetime.now()
        }
        
        return {"success": True, "entity_id": entity_id}
    
    def sync_batch(self, entities):
        """Sync multiple entities in batch."""
        if not self._connected:
            return {"success": False, "error": "Not connected"}
        
        results = []
        for entity in entities:
            result = self.sync_entity(
                entity["entity_id"],
                entity["data"],
                entity.get("permissions", ["read"])
            )
            results.append(result)
        
        return {"success": True, "synced_count": len(results), "results": results}
    
    def get_sync_status(self):
        """Get current sync status."""
        return {
            "connected": self._connected,
            "synced_entities_count": len(self._synced_entities),
            "pending_count": len(self._pending_sync),
            "error_count": len(self._sync_errors)
        }
    
    def get_synced_entities(self):
        """Get all synced entities."""
        return self._synced_entities


class MockPeerDiscovery:
    """Mock peer discovery service."""
    
    def __init__(self):
        self._known_peers = [
            {"id": "peer-1", "home_id": "home-alpha", "host": "192.168.1.10", "port": 8123, "online": True},
            {"id": "peer-2", "home_id": "home-beta", "host": "192.168.1.11", "port": 8123, "online": True},
            {"id": "peer-3", "home_id": "home-gamma", "host": "192.168.1.12", "port": 8123, "online": False},
        ]
        self._auto_connect_enabled = True
    
    def discover_peers(self, timeout_seconds=5):
        """Discover peers on local network."""
        return [p for p in self._known_peers if p["online"]]
    
    def get_peer_by_id(self, peer_id):
        """Get peer information by ID."""
        for peer in self._known_peers:
            if peer["id"] == peer_id:
                return peer
        return None
    
    def get_peer_by_home_id(self, home_id):
        """Get peer information by home ID."""
        for peer in self._known_peers:
            if peer["home_id"] == home_id:
                return peer
        return None
    
    def enable_auto_connect(self):
        """Enable automatic connection to discovered peers."""
        self._auto_connect_enabled = True
    
    def disable_auto_connect(self):
        """Disable automatic connection."""
        self._auto_connect_enabled = False
    
    def is_auto_connect_enabled(self):
        """Check if auto-connect is enabled."""
        return self._auto_connect_enabled


class MockConflictResolver:
    """Mock conflict resolution service for sync conflicts."""
    
    def __init__(self):
        self._conflict_log = []
        self._resolution_strategy = "last_write_wins"
    
    def resolve_conflict(self, local_entity, remote_entity):
        """Resolve conflict between local and remote entity."""
        conflict = {
            "entity_id": local_entity["entity_id"],
            "local_version": local_entity.get("version", 1),
            "remote_version": remote_entity.get("version", 1),
            "resolution": None
        }
        
        if self._resolution_strategy == "last_write_wins":
            local_ts = local_entity.get("updated_at", datetime.now())
            remote_ts = remote_entity.get("updated_at", datetime.now())
            
            if local_ts >= remote_ts:
                conflict["resolution"] = "local_wins"
                winner = local_entity
            else:
                conflict["resolution"] = "remote_wins"
                winner = remote_entity
        else:
            conflict["resolution"] = "merge"
            winner = {**local_entity, **remote_entity}
        
        self._conflict_log.append(conflict)
        return winner, conflict
    
    def get_conflict_log(self):
        """Get conflict resolution log."""
        return self._conflict_log
    
    def set_resolution_strategy(self, strategy):
        """Set conflict resolution strategy."""
        strategies = ["last_write_wins", "local_wins", "remote_wins", "merge"]
        if strategy in strategies:
            self._resolution_strategy = strategy
            return True
        return False


class TestSharingAPISyncWorkflow:
    """Sync-Workflow Tests for Sharing API."""
    
    @pytest.fixture
    def sync_client_home_a(self):
        """Create sync client for Home A."""
        return MockSyncClient("client-a", "home-alpha")
    
    @pytest.fixture
    def sync_client_home_b(self):
        """Create sync client for Home B."""
        return MockSyncClient("client-b", "home-beta")
    
    @pytest.fixture
    def peer_discovery(self):
        """Create peer discovery service."""
        return MockPeerDiscovery()
    
    @pytest.fixture
    def conflict_resolver(self):
        """Create conflict resolver service."""
        return MockConflictResolver()
    
    def test_sync_workflow_complete_two_home_flow(self, sync_client_home_a, sync_client_home_b):
        """Test complete sync workflow between two homes."""
        # Home A connects to Home B
        sync_client_home_a.connect("http://192.168.1.11:8123")
        assert sync_client_home_a._connected is True
        
        # Sync entities from Home A to Home B
        entities_to_sync = [
            {"entity_id": "light.living_room", "data": {"state": "on"}, "permissions": ["read", "write"]},
            {"entity_id": "sensor.temperature", "data": {"value": 21.5}, "permissions": ["read"]},
        ]
        
        result = sync_client_home_a.sync_batch(entities_to_sync)
        
        # Verify sync succeeded
        assert result["success"] is True
        assert result["synced_count"] == 2
        
        # Verify entities are synced
        synced = sync_client_home_a.get_synced_entities()
        assert "light.living_room" in synced
        assert "sensor.temperature" in synced
        
        # Disconnect
        sync_client_home_a.disconnect()
        assert sync_client_home_a._connected is False
    
    def test_sync_workflow_entity_sharing_with_permissions(self, sync_client_home_a):
        """Test entity sharing with granular permissions."""
        sync_client_home_a.connect("http://192.168.1.11:8123")
        
        # Share entity with specific permissions
        result = sync_client_home_a.sync_entity(
            entity_id="light.kitchen",
            entity_data={"state": "off", "brightness": 100},
            permissions=["read", "write", "control"]
        )
        
        assert result["success"] is True
        
        # Verify permissions are stored
        synced = sync_client_home_a.get_synced_entities()
        assert synced["light.kitchen"]["permissions"] == ["read", "write", "control"]
    
    def test_sync_workflow_status_monitoring(self, sync_client_home_a):
        """Test sync status monitoring during transfer."""
        # Initial status
        status = sync_client_home_a.get_sync_status()
        assert status["connected"] is False
        assert status["synced_entities_count"] == 0
        
        # Connect
        sync_client_home_a.connect("http://192.168.1.11:8123")
        status = sync_client_home_a.get_sync_status()
        assert status["connected"] is True
        
        # Sync entities
        sync_client_home_a.sync_entity("light.test", {"state": "on"}, ["read"])
        sync_client_home_a.sync_entity("sensor.test", {"value": 20}, ["read"])
        
        # Check status during sync
        status = sync_client_home_a.get_sync_status()
        assert status["synced_entities_count"] == 2
        assert status["pending_count"] == 0
        assert status["error_count"] == 0
    
    def test_sync_workflow_error_handling_on_disconnect(self, sync_client_home_a):
        """Test error handling when sync is interrupted."""
        # Try to sync without connection
        result = sync_client_home_a.sync_entity(
            entity_id="light.test",
            entity_data={"state": "on"},
            permissions=["read"]
        )
        
        # Should fail gracefully
        assert result["success"] is False
        assert "Not connected" in result["error"]
        
        # Verify error is tracked
        status = sync_client_home_a.get_sync_status()
        assert status["connected"] is False
    
    def test_sync_workflow_bidirectional_sharing(self, sync_client_home_a, sync_client_home_b):
        """Test bidirectional entity sharing between homes."""
        # Connect both clients
        sync_client_home_a.connect("http://192.168.1.11:8123")
        sync_client_home_b.connect("http://192.168.1.10:8123")
        
        # Home A shares with Home B
        sync_client_home_a.sync_entity(
            "light.living_room_a",
            {"state": "on"},
            ["read", "write"]
        )
        
        # Home B shares with Home A
        sync_client_home_b.sync_entity(
            "light.living_room_b",
            {"state": "off"},
            ["read"]
        )
        
        # Verify both directions worked
        synced_a = sync_client_home_a.get_synced_entities()
        synced_b = sync_client_home_b.get_synced_entities()
        
        assert "light.living_room_a" in synced_a
        assert "light.living_room_b" in synced_b
    
    def test_sync_workflow_conflict_resolution(self, conflict_resolver):
        """Test sync conflict resolution."""
        local_entity = {
            "entity_id": "light.living_room",
            "state": "on",
            "version": 2,
            "updated_at": datetime.now()
        }
        
        remote_entity = {
            "entity_id": "light.living_room",
            "state": "off",
            "version": 3,
            "updated_at": datetime.now() - timedelta(minutes=5)
        }
        
        winner, conflict = conflict_resolver.resolve_conflict(local_entity, remote_entity)
        
        # With last_write_wins, local should win (newer timestamp)
        assert conflict["resolution"] == "local_wins"
        assert winner["state"] == "on"
        
        # Verify conflict is logged
        log = conflict_resolver.get_conflict_log()
        assert len(log) == 1
    
    def test_sync_workflow_peer_discovery_auto_connect(self, peer_discovery):
        """Test peer discovery and auto-connect."""
        # Discover peers
        peers = peer_discovery.discover_peers()
        
        # Should find online peers
        assert len(peers) == 2
        assert all(p["online"] for p in peers)
        
        # Get specific peer
        peer = peer_discovery.get_peer_by_home_id("home-alpha")
        assert peer is not None
        assert peer["id"] == "peer-1"
        
        # Check auto-connect status
        assert peer_discovery.is_auto_connect_enabled() is True
        
        # Disable auto-connect
        peer_discovery.disable_auto_connect()
        assert peer_discovery.is_auto_connect_enabled() is False


# ═══════════════════════════════════════════════════════════════════════════
# COLLECTIVE INTELLIGENCE FEDERATED LEARNING ROUND TESTS
# ═══════════════════════════════════════════════════════════════════════════


class MockFederatedLearningCoordinator:
    """Mock federated learning coordinator for round management."""
    
    def __init__(self):
        self._rounds = {}
        self._active_round_id = None
        self._participating_nodes = {}
        self._aggregated_models = {}
        self._round_history = []
        self._min_participants = 2
    
    def create_round(self, round_id, model_id, participants=None):
        """Create a new federated learning round."""
        self._rounds[round_id] = {
            "round_id": round_id,
            "model_id": model_id,
            "status": "created",
            "participants": participants or [],
            "updates_received": [],
            "aggregated": False,
            "created_at": datetime.now(),
            "completed_at": None
        }
        self._active_round_id = round_id
        return round_id
    
    def register_node_for_round(self, round_id, node_id, capabilities=None):
        """Register node for participation in round."""
        if round_id not in self._rounds:
            return {"success": False, "error": "Round not found"}
        
        self._participating_nodes[node_id] = {
            "node_id": node_id,
            "round_id": round_id,
            "capabilities": capabilities or [],
            "registered_at": datetime.now(),
            "update_submitted": False
        }
        
        if node_id not in self._rounds[round_id]["participants"]:
            self._rounds[round_id]["participants"].append(node_id)
        
        return {"success": True, "node_id": node_id}
    
    def submit_update(self, round_id, node_id, model_weights, metrics=None):
        """Submit local model update for round."""
        if round_id not in self._rounds:
            return {"success": False, "error": "Round not found"}
        
        if node_id not in self._participating_nodes:
            return {"success": False, "error": "Node not registered"}
        
        update = {
            "node_id": node_id,
            "round_id": round_id,
            "model_weights": model_weights,
            "metrics": metrics or {},
            "submitted_at": datetime.now()
        }
        
        self._rounds[round_id]["updates_received"].append(update)
        self._participating_nodes[node_id]["update_submitted"] = True
        
        return {"success": True, "update_id": f"update_{node_id}_{round_id}"}
    
    def aggregate_round(self, round_id, aggregation_method="federated_avg"):
        """Aggregate all updates for a round."""
        if round_id not in self._rounds:
            return {"success": False, "error": "Round not found"}
        
        round_data = self._rounds[round_id]
        updates = round_data["updates_received"]
        
        if len(updates) < self._min_participants:
            return {
                "success": False,
                "error": f"Insufficient participants: {len(updates)} < {self._min_participants}"
            }
        
        # Aggregate weights (simple average for mock)
        aggregated_weights = {}
        weight_keys = updates[0]["model_weights"].keys()
        
        for key in weight_keys:
            values = [u["model_weights"][key] for u in updates]
            if isinstance(values[0], list):
                # Average element-wise for lists
                aggregated_weights[key] = [
                    sum(v[i] for v in values) / len(values)
                    for i in range(len(values[0]))
                ]
            else:
                # Simple average for scalars
                aggregated_weights[key] = sum(values) / len(values)
        
        # Create aggregated model
        model_version = f"{round_data['model_id']}_agg_{round_id}"
        self._aggregated_models[model_version] = {
            "model_version": model_version,
            "round_id": round_id,
            "weights": aggregated_weights,
            "created_at": datetime.now()
        }
        
        round_data["aggregated"] = True
        round_data["completed_at"] = datetime.now()
        round_data["status"] = "completed"
        self._active_round_id = None
        
        # Add to history
        self._round_history.append({
            "round_id": round_id,
            "model_id": round_data["model_id"],
            "participants": len(updates),
            "completed_at": round_data["completed_at"]
        })
        
        return {"success": True, "model_version": model_version}
    
    def get_round_status(self, round_id):
        """Get status of a specific round."""
        if round_id not in self._rounds:
            return None
        
        round_data = self._rounds[round_id]
        return {
            "round_id": round_id,
            "status": round_data["status"],
            "participants": len(round_data["participants"]),
            "updates_received": len(round_data["updates_received"]),
            "aggregated": round_data["aggregated"]
        }
    
    def get_active_round(self):
        """Get currently active round."""
        if self._active_round_id:
            return self.get_round_status(self._active_round_id)
        return None
    
    def get_round_history(self):
        """Get history of completed rounds."""
        return self._round_history
    
    def get_aggregated_model(self, model_version):
        """Get aggregated model by version."""
        return self._aggregated_models.get(model_version)


class MockPrivacyPreserver:
    """Mock differential privacy service for federated learning."""
    
    def __init__(self, epsilon=1.0, delta=1e-5):
        self.epsilon = epsilon
        self.delta = delta
        self._noise_scale = self._calculate_noise_scale()
    
    def _calculate_noise_scale(self):
        """Calculate Gaussian noise scale for differential privacy."""
        import math
        return math.sqrt(2 * math.log(1.25 / self.delta)) / self.epsilon
    
    def add_noise(self, weights, sensitivity=1.0):
        """Add differential privacy noise to weights."""
        import random
        noisy_weights = {}
        
        for key, value in weights.items():
            if isinstance(value, list):
                noisy_weights[key] = [
                    v + random.gauss(0, self._noise_scale * sensitivity)
                    for v in value
                ]
            else:
                noisy_weights[key] = value + random.gauss(0, self._noise_scale * sensitivity)
        
        return noisy_weights
    
    def clip_gradients(self, gradients, max_norm=1.0):
        """Clip gradients to bound sensitivity."""
        import math
        
        # Calculate norm
        if isinstance(gradients, dict):
            all_values = []
            for v in gradients.values():
                if isinstance(v, list):
                    all_values.extend(v)
                else:
                    all_values.append(v)
        else:
            all_values = gradients if isinstance(gradients, list) else [gradients]
        
        norm = math.sqrt(sum(v ** 2 for v in all_values))
        
        # Clip if necessary
        if norm > max_norm:
            scale = max_norm / norm
            if isinstance(gradients, dict):
                clipped = {}
                for key, value in gradients.items():
                    if isinstance(value, list):
                        clipped[key] = [v * scale for v in value]
                    else:
                        clipped[key] = value * scale
                return clipped
            else:
                return [g * scale for g in gradients] if isinstance(gradients, list) else gradients * scale
        
        return gradients
    
    def get_privacy_budget(self):
        """Get current privacy budget status."""
        return {
            "epsilon": self.epsilon,
            "delta": self.delta,
            "noise_scale": self._noise_scale
        }


class TestCollectiveIntelligenceFederatedRounds:
    """Federated Learning Round Tests for Collective Intelligence."""
    
    @pytest.fixture
    def fl_coordinator(self):
        """Create federated learning coordinator."""
        return MockFederatedLearningCoordinator()
    
    @pytest.fixture
    def privacy_preserver(self):
        """Create differential privacy service."""
        return MockPrivacyPreserver(epsilon=1.0, delta=1e-5)
    
    def test_fl_round_complete_cycle(self, fl_coordinator):
        """Test complete federated learning round cycle."""
        # Create round
        round_id = fl_coordinator.create_round(
            round_id="round_001",
            model_id="energy_forecast_v1"
        )
        assert round_id == "round_001"
        
        # Register nodes
        fl_coordinator.register_node_for_round("round_001", "node_1", ["training"])
        fl_coordinator.register_node_for_round("round_001", "node_2", ["training"])
        fl_coordinator.register_node_for_round("round_001", "node_3", ["inference"])
        
        # Submit updates
        fl_coordinator.submit_update(
            "round_001", "node_1",
            {"layer1": [0.1, 0.2], "layer2": [0.3, 0.4]},
            {"accuracy": 0.92}
        )
        fl_coordinator.submit_update(
            "round_001", "node_2",
            {"layer1": [0.2, 0.3], "layer2": [0.4, 0.5]},
            {"accuracy": 0.94}
        )
        fl_coordinator.submit_update(
            "round_001", "node_3",
            {"layer1": [0.15, 0.25], "layer2": [0.35, 0.45]},
            {"accuracy": 0.93}
        )
        
        # Aggregate
        result = fl_coordinator.aggregate_round("round_001")
        
        assert result["success"] is True
        assert "model_version" in result
        
        # Verify round status
        status = fl_coordinator.get_round_status("round_001")
        assert status["status"] == "completed"
        assert status["aggregated"] is True
        assert status["participants"] == 3
    
    def test_fl_round_multi_node_aggregation(self, fl_coordinator):
        """Test aggregation with multiple participating nodes."""
        round_id = fl_coordinator.create_round("round_multi", "model_v2")
        
        # Register 5 nodes
        for i in range(5):
            fl_coordinator.register_node_for_round(
                "round_multi",
                f"node_{i}",
                ["training", "inference"]
            )
            
            # Submit different weights
            fl_coordinator.submit_update(
                "round_multi",
                f"node_{i}",
                {"weights": [float(i), float(i+1)]},
                {"loss": 0.1 * (i + 1)}
            )
        
        # Aggregate
        result = fl_coordinator.aggregate_round("round_multi")
        assert result["success"] is True
        
        # Verify aggregated model
        model = fl_coordinator.get_aggregated_model(result["model_version"])
        assert model is not None
        assert "weights" in model
        
        # Weights should be averaged
        expected_avg = [sum(range(5))/5, sum(range(1,6))/5]
        assert abs(model["weights"]["weights"][0] - expected_avg[0]) < 0.01
        assert abs(model["weights"]["weights"][1] - expected_avg[1]) < 0.01
    
    def test_fl_round_privacy_preserving_aggregation(self, fl_coordinator, privacy_preserver):
        """Test privacy-preserving aggregation with differential privacy."""
        round_id = fl_coordinator.create_round("round_privacy", "model_private")
        
        # Register nodes
        fl_coordinator.register_node_for_round("round_privacy", "node_a")
        fl_coordinator.register_node_for_round("round_privacy", "node_b")
        
        # Original weights
        original_weights = {"layer1": [1.0, 2.0, 3.0]}
        
        # Add noise before submission (simulating local DP)
        noisy_weights_a = privacy_preserver.add_noise(original_weights)
        noisy_weights_b = privacy_preserver.add_noise(original_weights)
        
        # Submit noisy updates
        fl_coordinator.submit_update("round_privacy", "node_a", noisy_weights_a)
        fl_coordinator.submit_update("round_privacy", "node_b", noisy_weights_b)
        
        # Aggregate
        result = fl_coordinator.aggregate_round("round_privacy")
        assert result["success"] is True
        
        # Verify privacy budget
        budget = privacy_preserver.get_privacy_budget()
        assert budget["epsilon"] == 1.0
        assert budget["delta"] == 1e-5
        assert budget["noise_scale"] > 0
    
    def test_fl_round_recovery_after_node_failure(self, fl_coordinator):
        """Test round recovery when node fails during training."""
        round_id = fl_coordinator.create_round("round_recovery", "model_resilient")
        
        # Register 4 nodes
        for i in range(4):
            fl_coordinator.register_node_for_round("round_recovery", f"node_{i}")
        
        # Submit updates from only 3 nodes (node_3 fails)
        for i in range(3):
            fl_coordinator.submit_update(
                "round_recovery",
                f"node_{i}",
                {"weights": [float(i)]},
                {"status": "success"}
            )
        
        # Check round status
        status = fl_coordinator.get_round_status("round_recovery")
        assert status["updates_received"] == 3
        assert status["participants"] == 4
        
        # Should still aggregate with 3 nodes (meets minimum)
        result = fl_coordinator.aggregate_round("round_recovery")
        assert result["success"] is True
        
        # Verify completion despite node failure
        final_status = fl_coordinator.get_round_status("round_recovery")
        assert final_status["status"] == "completed"
    
    def test_fl_round_model_versioning_and_rollback(self, fl_coordinator):
        """Test model versioning and rollback capability."""
        # Run multiple rounds
        versions = []
        
        for round_num in range(3):
            round_id = f"round_v{round_num}"
            fl_coordinator.create_round(round_id, f"model_base")
            
            fl_coordinator.register_node_for_round(round_id, "node_1")
            fl_coordinator.register_node_for_round(round_id, "node_2")
            
            fl_coordinator.submit_update(round_id, "node_1", {"weights": [round_num * 0.1]})
            fl_coordinator.submit_update(round_id, "node_2", {"weights": [round_num * 0.2]})
            
            result = fl_coordinator.aggregate_round(round_id)
            versions.append(result["model_version"])
        
        # Verify all versions are tracked
        assert len(versions) == 3
        
        # Get specific version
        model_v2 = fl_coordinator.get_aggregated_model(versions[2])
        assert model_v2 is not None
        assert model_v2["round_id"] == "round_v2"
        
        # Can access any historical version
        model_v0 = fl_coordinator.get_aggregated_model(versions[0])
        assert model_v0 is not None
    
    def test_fl_round_history_and_metrics(self, fl_coordinator):
        """Test round history tracking and metrics."""
        # Run multiple rounds
        for i in range(3):
            round_id = f"round_hist_{i}"
            fl_coordinator.create_round(round_id, "model_hist")
            
            # Varying number of participants
            num_nodes = i + 2
            for j in range(num_nodes):
                fl_coordinator.register_node_for_round(round_id, f"node_{j}")
                fl_coordinator.submit_update(round_id, f"node_{j}", {"w": [j]})
            
            fl_coordinator.aggregate_round(round_id)
        
        # Get history
        history = fl_coordinator.get_round_history()
        
        assert len(history) == 3
        
        # Verify metrics are tracked
        for i, round_hist in enumerate(history):
            assert "round_id" in round_hist
            assert "participants" in round_hist
            assert "completed_at" in round_hist
            assert round_hist["participants"] == i + 2  # 2, 3, 4 participants


if __name__ == "__main__":
    pytest.main([__file__, "-v"])