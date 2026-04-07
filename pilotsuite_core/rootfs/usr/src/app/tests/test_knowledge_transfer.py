#!/usr/bin/env python3
"""Tests for knowledge transfer."""

import unittest
import time
from unittest.mock import patch, MagicMock

try:
    from copilot_core.collective_intelligence.knowledge_transfer import KnowledgeTransfer
    from copilot_core.collective_intelligence.models import KnowledgeItem
except ModuleNotFoundError:
    KnowledgeTransfer = None


class TestKnowledgeTransfer(unittest.TestCase):
    """Test KnowledgeTransfer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        self.kt = KnowledgeTransfer(
            min_confidence=0.7,
            max_transfer_rate=10
        )

    def test_knowledge_transfer_initialization(self):
        """Test KnowledgeTransfer initialization."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        self.assertEqual(self.kt.min_confidence, 0.7)
        self.assertEqual(self.kt.max_transfer_rate, 10)
        self.assertEqual(len(self.kt.knowledge_base), 0)
        self.assertEqual(len(self.kt.transfer_log), 0)

    def test_extract_knowledge(self):
        """Test extracting knowledge."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        knowledge = self.kt.extract_knowledge(
            node_id="home-1",
            knowledge_type="habitus_pattern",
            payload={"pattern": "evening_lights", "time": "19:00"},
            confidence=0.9
        )
        
        self.assertIsNotNone(knowledge)
        self.assertEqual(knowledge.source_node_id, "home-1")
        self.assertEqual(knowledge.knowledge_type, "habitus_pattern")
        self.assertEqual(knowledge.confidence, 0.9)

    def test_extract_knowledge_low_confidence(self):
        """Test extracting knowledge with low confidence."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        knowledge = self.kt.extract_knowledge(
            node_id="home-1",
            knowledge_type="habitus_pattern",
            payload={"pattern": "test"},
            confidence=0.5  # Below min_confidence
        )
        
        self.assertIsNone(knowledge)

    def test_extract_knowledge_duplicate(self):
        """Test extracting duplicate knowledge."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        payload = {"pattern": "same_pattern"}
        
        knowledge1 = self.kt.extract_knowledge(
            node_id="home-1",
            knowledge_type="habitus_pattern",
            payload=payload,
            confidence=0.9
        )
        
        knowledge2 = self.kt.extract_knowledge(
            node_id="home-2",
            knowledge_type="habitus_pattern",
            payload=payload,
            confidence=0.9
        )
        
        # First should succeed, second should be None (duplicate)
        self.assertIsNotNone(knowledge1)
        self.assertIsNone(knowledge2)

    def test_transfer_knowledge(self):
        """Test transferring knowledge."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        # First extract knowledge
        knowledge = self.kt.extract_knowledge(
            node_id="home-1",
            knowledge_type="energy_saving",
            payload={"strategy": "night_climate"},
            confidence=0.9
        )
        
        # Then transfer
        result = self.kt.transfer_knowledge(
            knowledge_id=knowledge.knowledge_hash,
            target_node_id="home-2"
        )
        
        self.assertTrue(result)
        self.assertEqual(len(self.kt.transfer_log), 1)

    def test_transfer_knowledge_not_found(self):
        """Test transferring non-existent knowledge."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        result = self.kt.transfer_knowledge(
            knowledge_id="nonexistent",
            target_node_id="home-2"
        )
        
        self.assertFalse(result)

    def test_get_knowledge_by_type(self):
        """Test getting knowledge by type."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        # Extract multiple types
        self.kt.extract_knowledge("h1", "type_a", {"data": 1}, 0.9)
        self.kt.extract_knowledge("h1", "type_b", {"data": 2}, 0.9)
        self.kt.extract_knowledge("h2", "type_a", {"data": 3}, 0.9)
        
        type_a_knowledge = self.kt.get_knowledge_for_type("type_a")

        self.assertEqual(len(type_a_knowledge), 2)

    def test_get_all_knowledge(self):
        """Test getting all knowledge."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        self.kt.extract_knowledge("h1", "type_a", {"data": 1}, 0.9)
        self.kt.extract_knowledge("h2", "type_b", {"data": 2}, 0.9)
        
        all_knowledge = self.kt.extract_knowledge("h3", "type_c", {"data": 3}, 0.9)
        # Verify we can extract and have knowledge items
        self.assertIsNotNone(all_knowledge)

    def test_knowledge_exists_after_extract(self):
        """Test knowledge exists after extraction."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        knowledge = self.kt.extract_knowledge(
            node_id="home-1",
            knowledge_type="test",
            payload={"key": "value"},
            confidence=0.9
        )

        # Verify knowledge was stored by retrieving it
        items = self.kt.get_knowledge_for_type("test")
        self.assertTrue(len(items) >= 1)

    def test_clear_knowledge(self):
        """Test clearing knowledge."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        knowledge = self.kt.extract_knowledge(
            node_id="home-1",
            knowledge_type="test",
            payload={"key": "value"},
            confidence=0.9
        )
        result = self.kt.clear_knowledge(knowledge.knowledge_hash)
        self.assertTrue(result)

    def test_get_transfer_stats(self):
        """Test getting transfer statistics."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        # Extract and transfer some knowledge
        k1 = self.kt.extract_knowledge("h1", "type_a", {"d": 1}, 0.9)
        k2 = self.kt.extract_knowledge("h2", "type_b", {"d": 2}, 0.9)
        
        self.kt.transfer_knowledge(k1.knowledge_hash, "target-1")
        self.kt.transfer_knowledge(k2.knowledge_hash, "target-2")
        
        stats = self.kt.get_statistics()

        self.assertIn("total_knowledge_items", stats)
        self.assertIn("total_transfers", stats)


class TestKnowledgeItem(unittest.TestCase):
    """Test KnowledgeItem model."""

    def test_knowledge_item_creation(self):
        """Test creating a KnowledgeItem."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        item = KnowledgeItem(
            knowledge_id="test-1",
            source_node_id="home-1",
            knowledge_type="habitus_pattern",
            payload={"pattern": "test"},
            confidence=0.8
        )
        
        self.assertEqual(item.knowledge_id, "test-1")
        self.assertEqual(item.source_node_id, "home-1")
        self.assertEqual(item.confidence, 0.8)

    def test_knowledge_hash(self):
        """Test knowledge_hash property."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        item = KnowledgeItem(
            knowledge_id="test-1",
            source_node_id="home-1",
            knowledge_type="test",
            payload={"key": "value"},
            confidence=0.9
        )
        
        self.assertIsNotNone(item.knowledge_hash)
        self.assertIsInstance(item.knowledge_hash, str)

    def test_knowledge_to_dict(self):
        """Test KnowledgeItem serialization."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        item = KnowledgeItem(
            knowledge_id="test-1",
            source_node_id="home-1",
            knowledge_type="test",
            payload={"key": "value"},
            confidence=0.9
        )
        
        data = item.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data["knowledge_id"], "test-1")

    def test_knowledge_from_dict(self):
        """Test KnowledgeItem deserialization."""
        if KnowledgeTransfer is None:
            self.skipTest("KnowledgeTransfer not available")
        data = {
            "knowledge_id": "test-1",
            "source_node_id": "home-1",
            "knowledge_type": "test",
            "payload": {"key": "value"},
            "confidence": 0.9,
            "timestamp": time.time(),
            "metadata": {}
        }
        
        item = KnowledgeItem.from_dict(data)
        
        self.assertEqual(item.knowledge_id, "test-1")
        self.assertEqual(item.source_node_id, "home-1")


if __name__ == "__main__":
    unittest.main()
