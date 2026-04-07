#!/usr/bin/env python3
"""Tests for Knowledge Transfer API (P2-008).

Tests cover:
1. Export/import functionality
2. Knowledge graph serialization
3. Migration tools
4. Validation and conflict resolution
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from copilot_core.knowledge.transfer_api import (
        KnowledgeTransferAPI,
        ExportPackage,
        ImportResult,
        TransferResult,
        ConflictStrategy,
        ExportFormat,
        ValidationError,
        MigrationPlan,
    )
    from copilot_core.collective_intelligence.models import KnowledgeItem
    from copilot_core.knowledge_graph.models import Node, Edge, NodeType, EdgeType
    KNOWLEDGE_TRANSFER_AVAILABLE = True
except (ModuleNotFoundError, ImportError) as e:
    KNOWLEDGE_TRANSFER_AVAILABLE = False
    print(f"Knowledge transfer module not available: {e}")


class TestExportPackage(unittest.TestCase):
    """Test ExportPackage dataclass."""

    def setUp(self):
        if not KNOWLEDGE_TRANSFER_AVAILABLE:
            self.skipTest("Knowledge transfer module not available")

    def test_export_package_creation(self):
        """Test creating an export package."""
        package = ExportPackage(
            package_id="test-pkg-001",
            version="1.0.0",
            source_node_id="home-1",
        )

        self.assertEqual(package.package_id, "test-pkg-001")
        self.assertEqual(package.version, "1.0.0")
        self.assertEqual(package.source_node_id, "home-1")
        self.assertIsNotNone(package.checksum)

    def test_export_package_checksum(self):
        """Test checksum computation."""
        package1 = ExportPackage(
            package_id="test-pkg",
            version="1.0.0",
            source_node_id="home-1",
            knowledge_items=[{"id": "item1"}],
        )

        package2 = ExportPackage(
            package_id="test-pkg",
            version="1.0.0",
            source_node_id="home-1",
            knowledge_items=[{"id": "item1"}],
        )

        # Same content should produce same checksum
        self.assertEqual(package1.checksum, package2.checksum)

    def test_export_package_to_dict(self):
        """Test serialization to dictionary."""
        package = ExportPackage(
            package_id="test-pkg",
            version="1.0.0",
            source_node_id="home-1",
        )

        data = package.to_dict()

        self.assertIsInstance(data, dict)
        self.assertEqual(data["package_id"], "test-pkg")
        self.assertEqual(data["version"], "1.0.0")

    def test_export_package_json_roundtrip(self):
        """Test JSON serialization roundtrip."""
        package = ExportPackage(
            package_id="test-pkg",
            version="1.0.0",
            source_node_id="home-1",
            knowledge_items=[{"knowledge_id": "k1", "type": "test"}],
        )

        json_str = package.to_json()
        restored = ExportPackage.from_json(json_str)

        self.assertEqual(restored.package_id, package.package_id)
        self.assertEqual(restored.version, package.version)


class TestKnowledgeTransferAPI(unittest.TestCase):
    """Test KnowledgeTransferAPI functionality."""

    def setUp(self):
        if not KNOWLEDGE_TRANSFER_AVAILABLE:
            self.skipTest("Knowledge transfer module not available")

        self.temp_dir = tempfile.mkdtemp()
        self.api = KnowledgeTransferAPI(
            export_dir=os.path.join(self.temp_dir, "exports"),
            import_dir=os.path.join(self.temp_dir, "imports"),
        )

    def tearDown(self):
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_api_initialization(self):
        """Test API initialization."""
        self.assertIsNotNone(self.api)
        self.assertEqual(self.api._schema_version, "1.0.0")

    def test_export_knowledge_empty(self):
        """Test exporting empty knowledge base."""
        package = self.api.export_knowledge(
            package_name="test-export",
            include_graph=False,
        )

        self.assertIsNotNone(package)
        self.assertEqual(package.package_id.split("_")[0], "pkg")
        self.assertEqual(len(package.knowledge_items), 0)

    def test_export_knowledge_with_items(self):
        """Test exporting with knowledge items."""
        # Add knowledge items
        item = KnowledgeItem(
            knowledge_id="test-k1",
            source_node_id="home-1",
            knowledge_type="habitus_pattern",
            payload={"pattern": "evening_lights"},
            confidence=0.9,
        )
        self.api._knowledge_items[item.knowledge_hash] = item

        package = self.api.export_knowledge(
            package_name="test-export",
            include_graph=False,
        )

        self.assertEqual(len(package.knowledge_items), 1)
        self.assertEqual(package.knowledge_items[0]["knowledge_id"], "test-k1")

    def test_export_knowledge_with_graph(self):
        """Test exporting with knowledge graph."""
        # Add graph nodes and edges
        node = Node(
            id="light.kitchen",
            type=NodeType.ENTITY,
            label="Kitchen Light",
        )
        self.api._graph_nodes[node.id] = node

        package = self.api.export_knowledge(
            package_name="test-export",
            include_graph=True,
        )

        self.assertEqual(len(package.graph_nodes), 1)
        self.assertEqual(package.graph_nodes[0]["id"], "light.kitchen")

    def test_export_knowledge_node_filter(self):
        """Test exporting with node type filter."""
        # Add nodes of different types
        entity_node = Node(
            id="light.kitchen",
            type=NodeType.ENTITY,
            label="Kitchen Light",
        )
        mood_node = Node(
            id="mood:relax",
            type=NodeType.MOOD,
            label="Relax",
        )
        self.api._graph_nodes[entity_node.id] = entity_node
        self.api._graph_nodes[mood_node.id] = mood_node

        # Export only ENTITY nodes
        package = self.api.export_knowledge(
            package_name="test-export",
            include_graph=True,
            node_filter={NodeType.ENTITY},
        )

        self.assertEqual(len(package.graph_nodes), 1)
        self.assertEqual(package.graph_nodes[0]["type"], NodeType.ENTITY.value)

    def test_export_to_file_json(self):
        """Test exporting to JSON file."""
        item = KnowledgeItem(
            knowledge_id="test-k1",
            source_node_id="home-1",
            knowledge_type="test",
            payload={"data": "value"},
            confidence=0.9,
        )
        self.api._knowledge_items[item.knowledge_hash] = item

        package = self.api.export_knowledge("test-export", include_graph=False)
        filepath = self.api.export_to_file(package, ExportFormat.JSON)

        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith(".json"))

        # Verify file content
        with open(filepath, "r") as f:
            data = json.load(f)
        self.assertEqual(data["package_id"], package.package_id)

    def test_import_knowledge(self):
        """Test importing knowledge."""
        # Create a package to import
        package = ExportPackage(
            package_id="import-pkg",
            version="1.0.0",
            source_node_id="home-2",
            knowledge_items=[{
                "knowledge_id": "k1",
                "source_node_id": "home-2",
                "knowledge_type": "test",
                "payload": {"data": "value"},
                "confidence": 0.9,
                "timestamp": time.time(),
                "metadata": {},
            }],
        )

        result = self.api.import_knowledge(package)

        self.assertTrue(result.success)
        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.imported_knowledge_ids, ["k1"])

    def test_import_knowledge_validation_failure(self):
        """Test import with validation failure."""
        # Create invalid package (missing required fields)
        package = ExportPackage(
            package_id="invalid-pkg",
            version="1.0.0",
            source_node_id="home-2",
            knowledge_items=[{
                # Missing required fields
                "partial": "data",
            }],
        )

        result = self.api.import_knowledge(package, validate=True)

        self.assertFalse(result.success)
        self.assertGreater(result.error_count, 0)

    def test_import_conflict_skip(self):
        """Test import with conflict and SKIP strategy."""
        # Add existing knowledge
        existing = KnowledgeItem(
            knowledge_id="existing-k1",
            source_node_id="home-1",
            knowledge_type="test",
            payload={"data": "original"},
            confidence=0.8,
        )
        self.api._knowledge_items[existing.knowledge_hash] = existing

        # Import conflicting knowledge
        package = ExportPackage(
            package_id="conflict-pkg",
            version="1.0.0",
            source_node_id="home-2",
            knowledge_items=[{
                "knowledge_id": "existing-k1",
                "source_node_id": "home-2",
                "knowledge_type": "test",
                "payload": {"data": "original"},  # Same payload = same hash
                "confidence": 0.9,
                "timestamp": time.time(),
                "metadata": {},
            }],
        )

        result = self.api.import_knowledge(
            package,
            conflict_strategy=ConflictStrategy.SKIP,
        )

        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.conflict_count, 0)

    def test_import_conflict_highest_confidence(self):
        """Test import with HIGHEST_CONFIDENCE strategy."""
        # Add existing knowledge with lower confidence
        existing = KnowledgeItem(
            knowledge_id="existing-k1",
            source_node_id="home-1",
            knowledge_type="test",
            payload={"data": "original"},
            confidence=0.5,
        )
        self.api._knowledge_items[existing.knowledge_hash] = existing

        # Import conflicting knowledge with higher confidence
        package = ExportPackage(
            package_id="conflict-pkg",
            version="1.0.0",
            source_node_id="home-2",
            knowledge_items=[{
                "knowledge_id": "existing-k1",
                "source_node_id": "home-2",
                "knowledge_type": "test",
                "payload": {"data": "original"},
                "confidence": 0.9,
                "timestamp": time.time(),
                "metadata": {},
            }],
        )

        result = self.api.import_knowledge(
            package,
            conflict_strategy=ConflictStrategy.HIGHEST_CONFIDENCE,
        )

        # Should import the higher confidence item
        self.assertGreater(result.imported_count, 0)

    def test_import_from_file(self):
        """Test importing from file."""
        # First export
        item = KnowledgeItem(
            knowledge_id="test-k1",
            source_node_id="home-1",
            knowledge_type="test",
            payload={"data": "value"},
            confidence=0.9,
        )
        self.api._knowledge_items[item.knowledge_hash] = item

        package = self.api.export_knowledge("test-export", include_graph=False)
        filepath = self.api.export_to_file(package, ExportFormat.JSON)

        # Clear and import
        self.api.clear_all()
        result = self.api.import_from_file(filepath)

        self.assertTrue(result.success)
        self.assertEqual(result.imported_count, 1)

    def test_migration_plan_creation(self):
        """Test creating migration plan."""
        plan = self.api.create_migration_plan("1.0.0", "1.1.0")

        self.assertEqual(plan.source_version, "1.0.0")
        self.assertEqual(plan.target_version, "1.1.0")
        self.assertGreaterEqual(len(plan.transformations), 0)

    def test_migration_plan_major_version(self):
        """Test migration plan for major version upgrade."""
        plan = self.api.create_migration_plan("1.0.0", "2.0.0")

        self.assertGreater(len(plan.risks), 0)
        self.assertTrue(any("backup" in r.lower() for r in plan.risks))

    def test_execute_migration(self):
        """Test executing migration."""
        # Create package with v1 schema
        package = ExportPackage(
            package_id="migrate-pkg",
            version="1.0.0",
            source_node_id="home-1",
            knowledge_items=[{
                "knowledge_id": "k1",
                "source_node_id": "home-1",
                "knowledge_type": "test",
                "payload": {"data": "value"},
                "confidence": 0.9,
                "timestamp": time.time(),
                "metadata": {},
            }],
        )

        plan = self.api.create_migration_plan("1.0.0", "2.0.0")
        migrated = self.api.execute_migration(package, plan)

        self.assertEqual(migrated.version, "2.0.0")
        self.assertEqual(len(migrated.knowledge_items), 1)
        # Check v2 fields were added
        self.assertIn("schema_version", migrated.knowledge_items[0])

    def test_get_statistics(self):
        """Test getting API statistics."""
        # Add some data
        item = KnowledgeItem(
            knowledge_id="test-k1",
            source_node_id="home-1",
            knowledge_type="test",
            payload={"data": "value"},
            confidence=0.9,
        )
        self.api._knowledge_items[item.knowledge_hash] = item

        node = Node(
            id="light.kitchen",
            type=NodeType.ENTITY,
            label="Kitchen Light",
        )
        self.api._graph_nodes[node.id] = node

        stats = self.api.get_statistics()

        self.assertEqual(stats["knowledge_items"], 1)
        self.assertEqual(stats["graph_nodes"], 1)
        self.assertEqual(stats["schema_version"], "1.0.0")

    def test_transfer_logging(self):
        """Test transfer logging."""
        result = TransferResult(
            success=True,
            transfer_id="transfer-001",
            source_node_id="home-1",
            target_node_id="home-2",
        )

        self.api.log_transfer(result)

        history = self.api.get_transfer_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].transfer_id, "transfer-001")

    def test_checksum_verification(self):
        """Test checksum verification on import."""
        package = ExportPackage(
            package_id="checksum-pkg",
            version="1.0.0",
            source_node_id="home-1",
        )

        # Corrupt checksum
        original_checksum = package.checksum
        package.checksum = "invalid_checksum"

        result = self.api.import_knowledge(package, validate=True)

        self.assertFalse(result.success)
        self.assertTrue(any("checksum" in e.lower() for e in result.errors))


class TestGraphMLExport(unittest.TestCase):
    """Test GraphML export functionality."""

    def setUp(self):
        if not KNOWLEDGE_TRANSFER_AVAILABLE:
            self.skipTest("Knowledge transfer module not available")

        self.temp_dir = tempfile.mkdtemp()
        self.api = KnowledgeTransferAPI(
            export_dir=os.path.join(self.temp_dir, "exports"),
            import_dir=os.path.join(self.temp_dir, "imports"),
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_graphml_export(self):
        """Test exporting to GraphML format."""
        # Add graph data
        node1 = Node(
            id="light.kitchen",
            type=NodeType.ENTITY,
            label="Kitchen Light",
            properties={"dimable": True},
        )
        node2 = Node(
            id="area.kitchen",
            type=NodeType.AREA,
            label="Kitchen",
        )
        edge = Edge(
            source="light.kitchen",
            target="area.kitchen",
            type=EdgeType.BELONGS_TO,
            confidence=1.0,
        )

        self.api._graph_nodes[node1.id] = node1
        self.api._graph_nodes[node2.id] = node2
        self.api._graph_edges[edge.id] = edge

        package = self.api.export_knowledge(
            "graphml-test",
            include_graph=True,
            format=ExportFormat.GRAPHML,
        )

        filepath = self.api.export_to_file(package, ExportFormat.GRAPHML)

        self.assertTrue(filepath.endswith(".graphml"))
        self.assertTrue(os.path.exists(filepath))

        # Verify GraphML content
        with open(filepath, "r") as f:
            content = f.read()

        self.assertIn("<?xml", content)
        self.assertIn("<graphml", content)
        self.assertIn("light.kitchen", content)


class TestTarGzExport(unittest.TestCase):
    """Test tar.gz export functionality."""

    def setUp(self):
        if not KNOWLEDGE_TRANSFER_AVAILABLE:
            self.skipTest("Knowledge transfer module not available")

        self.temp_dir = tempfile.mkdtemp()
        self.api = KnowledgeTransferAPI(
            export_dir=os.path.join(self.temp_dir, "exports"),
            import_dir=os.path.join(self.temp_dir, "imports"),
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_targz_export_import_roundtrip(self):
        """Test tar.gz export and import roundtrip."""
        # Add data
        item = KnowledgeItem(
            knowledge_id="test-k1",
            source_node_id="home-1",
            knowledge_type="test",
            payload={"data": "value"},
            confidence=0.9,
        )
        self.api._knowledge_items[item.knowledge_hash] = item

        # Export to tar.gz
        package = self.api.export_knowledge("targz-test", include_graph=False)
        filepath = self.api.export_to_file(package, ExportFormat.TAR_GZ)

        self.assertTrue(filepath.endswith(".tar.gz"))

        # Clear and import
        self.api.clear_all()
        result = self.api.import_from_file(filepath)

        self.assertTrue(result.success)
        self.assertEqual(result.imported_count, 1)


if __name__ == "__main__":
    unittest.main()
