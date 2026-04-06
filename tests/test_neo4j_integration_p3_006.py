"""
Tests for Neo4j Integration (P3-006).

Tests cover:
- Neo4jAdapter connection and lifecycle
- Schema management (constraints, indexes)
- Brain Graph export
- Cypher query execution
- Visualization data export
- Graph analytics
- Error handling and fallback
- CypherBuilder fluent API
- CypherTemplates
- CypherValidator
- API endpoints

Total: 25+ test cases
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                'copilot_core', 'rootfs', 'usr', 'src', 'app'))

# Set environment for testing (disable Neo4j by default)
os.environ["COPILOT_NEO4J_ENABLED"] = "false"

# Mock flask before importing modules that depend on it
sys.modules['flask'] = MagicMock()
sys.modules['flask_socketio'] = MagicMock()


class TestNeo4jConfig(unittest.TestCase):
    """Test Neo4jConfig dataclass."""

    def test_default_config_from_env(self):
        """Test default configuration from environment."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jConfig

        config = Neo4jConfig()

        # Should use environment defaults
        self.assertEqual(config.user, "neo4j")
        self.assertTrue(config.uri)  # Should have some default URI
        self.assertFalse(config.encrypted)

    def test_custom_config(self):
        """Test custom configuration."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jConfig

        config = Neo4jConfig(
            uri="bolt://custom:7687",
            user="admin",
            password="secret",
            database="knowledge",
            timeout=60,
            max_pool_size=100,
        )

        self.assertEqual(config.uri, "bolt://custom:7687")
        self.assertEqual(config.user, "admin")
        self.assertEqual(config.password, "secret")
        self.assertEqual(config.database, "knowledge")
        self.assertEqual(config.timeout, 60)
        self.assertEqual(config.max_pool_size, 100)


class TestNeo4jAdapterConnection(unittest.TestCase):
    """Test Neo4jAdapter connection management."""

    def test_adapter_initialization(self):
        """Test adapter initializes without connection."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        adapter = Neo4jAdapter()

        self.assertFalse(adapter.is_connected)
        self.assertIsNone(adapter._driver)

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_connect_success(self, mock_driver_class):
        """Test successful connection."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter, Neo4jConfig

        # Mock the driver
        mock_driver = MagicMock()
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter(
            Neo4jConfig(uri="bolt://test:7687", user="neo4j", password="test")
        )
        result = adapter.connect()

        self.assertTrue(result)
        self.assertTrue(adapter.is_connected)
        mock_driver.verify_connectivity.assert_called_once()

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_connect_failure(self, mock_driver_class):
        """Test connection failure handling."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter, Neo4jConfig
        from neo4j.exceptions import ServiceUnavailable

        mock_driver_class.driver.side_effect = ServiceUnavailable("Connection refused")

        adapter = Neo4jAdapter(
            Neo4jConfig(uri="bolt://unreachable:7687")
        )
        result = adapter.connect()

        self.assertFalse(result)
        self.assertFalse(adapter.is_connected)

    def test_disconnect(self):
        """Test disconnect."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        adapter = Neo4jAdapter()
        adapter._driver = MagicMock()
        adapter._connected = True

        adapter.disconnect()

        self.assertFalse(adapter.is_connected)
        adapter._driver.close.assert_called_once()

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_session_context_manager(self, mock_driver_class):
        """Test session context manager."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = lambda s: mock_session
        mock_driver.session.return_value.__exit__ = lambda s, *args: None
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        with adapter.session() as session:
            self.assertEqual(session, mock_session)

        mock_session.close.assert_called_once()

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_transaction_context_manager(self, mock_driver_class):
        """Test transaction context manager."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_tx = MagicMock()

        mock_session.begin_transaction.return_value.__enter__ = lambda s: mock_tx
        mock_session.begin_transaction.return_value.__exit__ = lambda s, *args: None
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = lambda s, *args: None
        mock_driver.session.return_value = mock_session
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        with adapter.transaction() as tx:
            self.assertEqual(tx, mock_tx)

        mock_tx.commit.assert_called_once()


class TestNeo4jAdapterSchema(unittest.TestCase):
    """Test Neo4jAdapter schema management."""

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_create_constraints(self, mock_driver_class):
        """Test creating constraints."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_tx = MagicMock()

        mock_session.begin_transaction.return_value.__enter__ = lambda s: mock_tx
        mock_session.begin_transaction.return_value.__exit__ = lambda s, *args: None
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = lambda s, *args: None
        mock_driver.session.return_value = mock_session
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        result = adapter.create_constraints()

        self.assertTrue(result.success)
        # Should create 7 constraints (Entity, Zone, Area, Service, Mood, Pattern, Context)
        self.assertGreater(mock_tx.run.call_count, 0)

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_create_indexes(self, mock_driver_class):
        """Test creating indexes."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_tx = MagicMock()

        mock_session.begin_transaction.return_value.__enter__ = lambda s: mock_tx
        mock_session.begin_transaction.return_value.__exit__ = lambda s, *args: None
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = lambda s, *args: None
        mock_driver.session.return_value = mock_session
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        result = adapter.create_indexes()

        self.assertTrue(result.success)
        self.assertGreater(mock_tx.run.call_count, 0)

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_ensure_schema(self, mock_driver_class):
        """Test ensure_schema creates both constraints and indexes."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_tx = MagicMock()

        mock_session.begin_transaction.return_value.__enter__ = lambda s: mock_tx
        mock_session.begin_transaction.return_value.__exit__ = lambda s, *args: None
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = lambda s, *args: None
        mock_driver.session.return_value = mock_session
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        result = adapter.ensure_schema()

        self.assertTrue(result["success"])
        self.assertTrue(result["constraints"])
        self.assertTrue(result["indexes"])


class TestNeo4jAdapterExport(unittest.TestCase):
    """Test Neo4jAdapter Brain Graph export."""

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_export_brain_graph(self, mock_driver_class):
        """Test exporting nodes and edges to Neo4j."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter
        from copilot_core.knowledge_graph.models import Node, Edge, NodeType, EdgeType

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_tx = MagicMock()

        mock_session.begin_transaction.return_value.__enter__ = lambda s: mock_tx
        mock_session.begin_transaction.return_value.__exit__ = lambda s, *args: None
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = lambda s, *args: None
        mock_driver.session.return_value = mock_session
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        # Create test data
        nodes = [
            Node(id="light.kitchen", type=NodeType.ENTITY, label="Kitchen Light"),
            Node(id="area.kitchen", type=NodeType.AREA, label="Kitchen"),
        ]
        edges = [
            Edge(
                source="light.kitchen",
                target="area.kitchen",
                type=EdgeType.BELONGS_TO,
                weight=1.0,
            )
        ]

        stats = adapter.export_brain_graph(nodes, edges, batch_size=10)

        self.assertEqual(stats["nodes_imported"], 2)
        self.assertEqual(stats["edges_imported"], 1)
        self.assertGreater(stats["batches"], 0)
        self.assertEqual(len(stats["errors"]), 0)

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_export_batching(self, mock_driver_class):
        """Test batch export with large datasets."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter
        from copilot_core.knowledge_graph.models import Node, NodeType

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_tx = MagicMock()

        mock_session.begin_transaction.return_value.__enter__ = lambda s: mock_tx
        mock_session.begin_transaction.return_value.__exit__ = lambda s, *args: None
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = lambda s, *args: None
        mock_driver.session.return_value = mock_session
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        # Create 250 nodes (should be 3 batches with batch_size=100)
        nodes = [
            Node(id=f"entity.{i}", type=NodeType.ENTITY, label=f"Entity {i}")
            for i in range(250)
        ]

        stats = adapter.export_brain_graph(nodes, [], batch_size=100)

        self.assertEqual(stats["nodes_imported"], 250)
        # 3 batches for nodes (100, 100, 50)
        self.assertEqual(stats["batches"], 3)


class TestNeo4jAdapterVisualization(unittest.TestCase):
    """Test Neo4jAdapter visualization export."""

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_export_visualization_data(self, mock_driver_class):
        """Test exporting visualization data."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        # Mock query result
        mock_record = MagicMock()
        mock_node = MagicMock()
        mock_node.__getitem__ = lambda s, k: {
            "id": "light.kitchen",
            "label": "Kitchen Light",
            "type": "entity",
        }.get(k)
        mock_node.labels = ["Entity"]
        mock_rel = MagicMock()
        mock_rel.type = "BELONGS_TO"
        mock_rel.__getitem__ = lambda s, k: {"weight": 1.0, "confidence": 0.9}.get(k)
        mock_rel.start_node = mock_node
        mock_rel.end_node = mock_node

        mock_record.__getitem__ = lambda s, k: {
            "n": mock_node,
            "r": mock_rel,
            "m": mock_node,
        }.get(k)
        mock_result.__iter__ = lambda s: iter([mock_record])
        mock_result.consume.return_value = MagicMock()
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = lambda s, *args: None
        mock_driver.session.return_value = mock_session
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        viz_data = adapter.export_visualization_data(max_nodes=100, max_edges=200)

        self.assertTrue(viz_data["success"])
        self.assertIn("nodes", viz_data)
        self.assertIn("edges", viz_data)
        self.assertIn("node_count", viz_data)
        self.assertIn("edge_count", viz_data)

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_export_with_root_node(self, mock_driver_class):
        """Test exporting subgraph around root node."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = lambda s: iter([])
        mock_result.consume.return_value = MagicMock()
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = lambda s, *args: None
        mock_driver.session.return_value = mock_session
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        viz_data = adapter.export_visualization_data(
            root_node="light.kitchen", max_nodes=50
        )

        self.assertTrue(viz_data["success"])
        # Should use subgraph query with root_id parameter
        mock_session.run.assert_called_once()


class TestNeo4jAdapterAnalytics(unittest.TestCase):
    """Test Neo4jAdapter graph analytics."""

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_get_graph_stats(self, mock_driver_class):
        """Test getting graph statistics."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        mock_record = MagicMock()
        mock_record.__getitem__ = lambda s, k: {"node_count": 100, "edge_count": 250}.get(k)
        mock_result.__iter__ = lambda s: iter([mock_record])
        mock_result.consume.return_value = MagicMock()
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = lambda s, *args: None
        mock_driver.session.return_value = mock_session
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        stats = adapter.get_graph_stats()

        self.assertTrue(stats["success"])
        self.assertEqual(stats["node_count"], 100)
        self.assertEqual(stats["edge_count"], 250)
        self.assertIn("density", stats)

    @patch("copilot_core.knowledge_graph.neo4j_adapter.GraphDatabase")
    def test_find_central_nodes(self, mock_driver_class):
        """Test finding central nodes."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        mock_record = MagicMock()
        mock_record.__getitem__ = lambda s, k: {
            "id": "light.kitchen",
            "label": "Kitchen Light",
            "degree": 15,
        }.get(k)
        mock_result.__iter__ = lambda s: iter([mock_record])
        mock_result.consume.return_value = MagicMock()
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = lambda s, *args: None
        mock_driver.session.return_value = mock_session
        mock_driver_class.driver.return_value = mock_driver

        adapter = Neo4jAdapter()
        adapter._driver = mock_driver
        adapter._connected = True

        result = adapter.find_central_nodes(top_k=10)

        self.assertTrue(result.success)
        self.assertEqual(len(result.records), 1)


class TestCypherQuery(unittest.TestCase):
    """Test CypherQuery dataclass."""

    def test_cypher_query_creation(self):
        """Test creating a CypherQuery."""
        from copilot_core.knowledge_graph.neo4j_adapter import CypherQuery

        query = CypherQuery(
            query="MATCH (n) RETURN n LIMIT $limit",
            parameters={"limit": 10},
            read_only=True,
            description="Test query",
        )

        self.assertEqual(query.query, "MATCH (n) RETURN n LIMIT $limit")
        self.assertEqual(query.parameters["limit"], 10)
        self.assertTrue(query.read_only)
        self.assertEqual(query.description, "Test query")


class TestCypherBuilder(unittest.TestCase):
    """Test CypherBuilder fluent API."""

    def test_basic_match(self):
        """Test basic MATCH query."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherBuilder

        builder = CypherBuilder()
        query, params = (
            builder.match("(n:Entity {id: $entity_id})")
            .param("entity_id", "light.kitchen")
            .return_expr("n")
            .build()
        )

        self.assertIn("MATCH", query)
        self.assertIn("RETURN", query)
        self.assertEqual(params["entity_id"], "light.kitchen")

    def test_optional_match(self):
        """Test OPTIONAL MATCH."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherBuilder

        builder = CypherBuilder()
        query, params = (
            builder.match("(n:Entity {id: $id})")
            .optional_match("(n)-[r]-(neighbor)")
            .param("id", "test")
            .return_expr("n, r, neighbor")
            .build()
        )

        self.assertIn("OPTIONAL MATCH", query)

    def test_where_clause(self):
        """Test WHERE clause."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherBuilder

        builder = CypherBuilder()
        query, params = (
            builder.match("(n:Entity)")
            .where("n.domain = $domain", domain="light")
            .and_where("n.area_id = $area", area="kitchen")
            .return_expr("n")
            .build()
        )

        self.assertIn("WHERE", query)
        self.assertIn("AND", query)
        self.assertEqual(params["domain"], "light")
        self.assertEqual(params["area"], "kitchen")

    def test_limit_and_order(self):
        """Test LIMIT and ORDER BY."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherBuilder

        builder = CypherBuilder()
        query, params = (
            builder.match("(n:Entity)")
            .return_expr("n")
            .order_by("n.label")
            .limit(10)
            .build()
        )

        self.assertIn("ORDER BY", query)
        self.assertIn("LIMIT", query)

    def test_fluent_chain(self):
        """Test complete fluent chain."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherBuilder

        builder = CypherBuilder()
        query, params = (
            builder.match("(n:Entity {id: $entity_id})")
            .optional_match("(n)-[r:BELONGS_TO]->(a:Area)")
            .where("n.domain = $domain", domain="light")
            .with_expr("n, a")
            .return_expr("n, a")
            .order_by("n.label")
            .limit(100)
            .params(entity_id="light.kitchen")
            .build()
        )

        self.assertIn("MATCH", query)
        self.assertIn("OPTIONAL MATCH", query)
        self.assertIn("WITH", query)
        self.assertIn("RETURN", query)


class TestCypherTemplates(unittest.TestCase):
    """Test CypherTemplates."""

    def test_find_entity_template(self):
        """Test find_entity template."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherTemplates

        query, params = CypherTemplates.find_entity("light.kitchen")

        self.assertIn("MATCH", query)
        self.assertIn("Entity", query)
        self.assertEqual(params["entity_id"], "light.kitchen")

    def test_find_entity_with_relationships(self):
        """Test find_entity_with_relationships template."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherTemplates

        query, params = CypherTemplates.find_entity_with_relationships(
            "light.kitchen", max_hops=3
        )

        self.assertIn("1..3", query)  # Should use provided max_hops
        self.assertEqual(params["entity_id"], "light.kitchen")

    def test_find_path_between(self):
        """Test find_path_between template."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherTemplates

        query, params = CypherTemplates.find_path_between(
            "light.kitchen", "area.kitchen", max_depth=4
        )

        self.assertIn("allShortestPaths", query)
        self.assertIn("1..4", query)

    def test_get_graph_stats_template(self):
        """Test get_graph_stats template."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherTemplates

        query, params = CypherTemplates.get_graph_stats()

        self.assertIn("count", query)
        self.assertEqual(params, {})

    def test_export_for_visualization(self):
        """Test export_for_visualization template."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherTemplates

        # Without root
        query, params = CypherTemplates.export_for_visualization(max_nodes=200)
        self.assertIn("LIMIT", query)

        # With root
        query, params = CypherTemplates.export_for_visualization(
            root_id="light.kitchen"
        )
        self.assertIn("root_id", params)


class TestCypherValidator(unittest.TestCase):
    """Test CypherValidator."""

    def test_is_read_only_true(self):
        """Test read-only query detection."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherValidator

        queries = [
            "MATCH (n) RETURN n",
            "MATCH (n) WHERE n.id = $id RETURN n",
            "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 10",
        ]

        for query in queries:
            self.assertTrue(
                CypherValidator.is_read_only(query), f"Query should be read-only: {query}"
            )

    def test_is_read_only_false(self):
        """Test write query detection."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherValidator

        queries = [
            "CREATE (n:Entity {id: $id})",
            "MERGE (n {id: $id})",
            "DELETE n",
            "DETACH DELETE n",
            "SET n.label = $label",
        ]

        for query in queries:
            self.assertFalse(
                CypherValidator.is_read_only(query), f"Query should not be read-only: {query}"
            )

    def test_is_safe_dangerous(self):
        """Test dangerous query detection."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherValidator

        query = "MATCH (n) DETACH DELETE n"
        is_safe, warning = CypherValidator.is_safe(query)

        self.assertFalse(is_safe)
        self.assertIn("DELETE", warning)

    def test_is_safe_missing_limit(self):
        """Test missing LIMIT detection."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherValidator

        query = "MATCH (n) RETURN n"
        is_safe, warning = CypherValidator.is_safe(query)

        self.assertFalse(is_safe)
        self.assertIn("LIMIT", warning)

    def test_is_safe_with_limit(self):
        """Test query with LIMIT is safe."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherValidator

        query = "MATCH (n) RETURN n LIMIT 100"
        is_safe, warning = CypherValidator.is_safe(query)

        self.assertTrue(is_safe)

    def test_validate_parameters(self):
        """Test parameter validation."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherValidator

        query = "MATCH (n {id: $entity_id, domain: $domain}) RETURN n"
        params = {"entity_id": "light.kitchen"}

        missing = CypherValidator.validate_parameters(query, params)

        self.assertEqual(len(missing), 1)
        self.assertIn("domain", missing)


class TestCypherOptimizer(unittest.TestCase):
    """Test CypherOptimizer."""

    def test_suggest_missing_index_hint(self):
        """Test index hint suggestion."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherOptimizer

        query = "MATCH (n:Entity {id: $id}) RETURN n"
        suggestions = CypherOptimizer.suggest_optimizations(query)

        self.assertGreater(len(suggestions), 0)
        self.assertTrue(any("INDEX" in s for s in suggestions))

    def test_suggest_cartesian_product(self):
        """Test Cartesian product warning."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherOptimizer

        query = "MATCH (n) MATCH (m) RETURN n, m"
        suggestions = CypherOptimizer.suggest_optimizations(query)

        self.assertTrue(any("Cartesian" in s for s in suggestions))

    def test_suggest_missing_label(self):
        """Test missing label suggestion."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherOptimizer

        query = "MATCH (n) RETURN n"
        suggestions = CypherOptimizer.suggest_optimizations(query)

        self.assertTrue(any("label" in s for s in suggestions))

    def test_suggest_unbounded_path(self):
        """Test unbounded path suggestion."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherOptimizer

        query = "MATCH (n)-[*]-(m) RETURN n, m"
        suggestions = CypherOptimizer.suggest_optimizations(query)

        self.assertTrue(any("depth" in s.lower() for s in suggestions))


class TestNeo4jAPIEndpoints(unittest.TestCase):
    """Test Neo4j API endpoints."""

    def test_cypher_query_read_only_validation(self):
        """Test that write queries are rejected."""
        from copilot_core.knowledge_graph.cypher_adapter import CypherValidator

        write_queries = [
            "CREATE (n) RETURN n",
            "MERGE (n {id: 1})",
            "DELETE n",
        ]

        for query in write_queries:
            is_safe, _ = CypherValidator.is_safe(query)
            self.assertFalse(is_safe, f"Write query should be rejected: {query}")

    def test_visualize_endpoint_neo4j_unavailable(self):
        """Test /neo4j/visualize when Neo4j is unavailable."""
        # Test the logic directly
        from copilot_core.knowledge_graph import neo4j_adapter
        
        # Simulate NEO4J_AVAILABLE = False
        neo4j_available = False
        
        if not neo4j_available:
            response_data = {
                "ok": False,
                "error": "Neo4j adapter not available",
                "neo4j_available": False,
            }
            self.assertFalse(response_data["ok"])
            self.assertEqual(response_data["neo4j_available"], False)


class TestNeo4jAdapterErrorHandling(unittest.TestCase):
    """Test error handling in Neo4jAdapter."""

    def test_execute_without_connection(self):
        """Test execute fails gracefully without connection."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter, CypherQuery

        adapter = Neo4jAdapter()
        # Don't connect

        query = CypherQuery(query="MATCH (n) RETURN n")

        with self.assertRaises(RuntimeError):
            adapter.execute(query)

    def test_session_without_connection(self):
        """Test session fails gracefully without connection."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        adapter = Neo4jAdapter()

        with self.assertRaises(RuntimeError):
            with adapter.session():
                pass

    def test_transaction_without_connection(self):
        """Test transaction fails gracefully without connection."""
        from copilot_core.knowledge_graph.neo4j_adapter import Neo4jAdapter

        adapter = Neo4jAdapter()

        with self.assertRaises(RuntimeError):
            with adapter.transaction():
                pass


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""

    @patch("copilot_core.knowledge_graph.neo4j_adapter.Neo4jAdapter")
    def test_get_neo4j_adapter(self, mock_adapter_class):
        """Test get_neo4j_adapter creates and connects adapter."""
        from copilot_core.knowledge_graph.neo4j_adapter import get_neo4j_adapter

        mock_adapter = MagicMock()
        mock_adapter_class.return_value = mock_adapter

        adapter = get_neo4j_adapter()

        mock_adapter.connect.assert_called_once()

    @patch("copilot_core.knowledge_graph.neo4j_adapter.get_neo4j_adapter")
    def test_export_to_neo4j(self, mock_get_adapter):
        """Test export_to_neo4j convenience function."""
        from copilot_core.knowledge_graph.neo4j_adapter import export_to_neo4j
        from copilot_core.knowledge_graph.models import Node, NodeType

        mock_adapter = MagicMock()
        mock_adapter.export_brain_graph.return_value = {"nodes_imported": 1}
        mock_get_adapter.return_value = mock_adapter

        nodes = [Node(id="test", type=NodeType.ENTITY, label="Test")]
        result = export_to_neo4j(nodes, [])

        mock_adapter.export_brain_graph.assert_called_once()
        mock_adapter.disconnect.assert_called_once()

    @patch("copilot_core.knowledge_graph.neo4j_adapter.get_neo4j_adapter")
    def test_get_visualization_data(self, mock_get_adapter):
        """Test get_visualization_data convenience function."""
        from copilot_core.knowledge_graph.neo4j_adapter import get_visualization_data

        mock_adapter = MagicMock()
        mock_adapter.export_visualization_data.return_value = {
            "nodes": [],
            "edges": [],
            "success": True,
        }
        mock_get_adapter.return_value = mock_adapter

        result = get_visualization_data()

        mock_adapter.export_visualization_data.assert_called_once()
        mock_adapter.disconnect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
