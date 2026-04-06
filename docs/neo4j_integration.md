# Neo4j Integration for PilotSuite Knowledge Graph (P3-006)

## Overview

This document describes the Neo4j integration for the PilotSuite Knowledge Graph, providing advanced graph storage, querying, and visualization capabilities beyond the SQLite fallback.

### Features

- **Dual Backend Support**: Neo4j (preferred) with SQLite fallback
- **Brain Graph Export**: Batch export of nodes and edges to Neo4j
- **Cypher Query Adapter**: Fluent API for building complex queries
- **Visualization Export**: D3.js/Cytoscape-ready graph data
- **Graph Analytics**: Centrality, communities, statistics
- **Schema Management**: Automatic constraints and indexes
- **REST API Endpoints**: Full CRUD and query operations

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PilotSuite Core                          │
├─────────────────────────────────────────────────────────────┤
│  Knowledge Graph API (api.py)                               │
│  /kg/* endpoints                                            │
│  /kg/neo4j/* endpoints                                      │
├─────────────────────────────────────────────────────────────┤
│  Neo4j Adapter (neo4j_adapter.py)                           │
│  - Connection management                                    │
│  - Batch export                                             │
│  - Visualization export                                     │
│  - Analytics                                                │
├─────────────────────────────────────────────────────────────┤
│  Cypher Adapter (cypher_adapter.py)                         │
│  - CypherBuilder (fluent API)                               │
│  - CypherTemplates (pre-built queries)                      │
│  - CypherValidator (safety checks)                          │
│  - CypherOptimizer (performance hints)                      │
├─────────────────────────────────────────────────────────────┤
│  Graph Store (graph_store.py)                               │
│  - Dual backend (Neo4j/SQLite)                              │
│  - CRUD operations                                          │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

```bash
# Neo4j connection
COPILOT_NEO4J_URI=bolt://neo4j:7687
COPILOT_NEO4J_USER=neo4j
COPILOT_NEO4J_PASSWORD=your_password
COPILOT_NEO4J_DATABASE=neo4j
COPILOT_NEO4J_ENABLED=true

# Optional tuning
COPILOT_NEO4J_TIMEOUT=30
COPILOT_NEO4J_MAX_POOL_SIZE=50
```

### Python Configuration

```python
from copilot_core.knowledge_graph.neo4j_adapter import Neo4jConfig, Neo4jAdapter

config = Neo4jConfig(
    uri="bolt://neo4j:7687",
    user="neo4j",
    password="secret",
    database="neo4j",
    timeout=30,
    max_pool_size=50,
    encrypted=False,
)

adapter = Neo4jAdapter(config)
adapter.connect()
```

## Usage

### Basic Connection

```python
from copilot_core.knowledge_graph.neo4j_adapter import get_neo4j_adapter

# Get connected adapter
adapter = get_neo4j_adapter()

# Use adapter...

# Disconnect when done
adapter.disconnect()
```

### Exporting Brain Graph

```python
from copilot_core.knowledge_graph.neo4j_adapter import export_to_neo4j
from copilot_core.knowledge_graph.models import Node, Edge, NodeType, EdgeType

# Prepare data
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
        confidence=0.9,
    )
]

# Export to Neo4j
stats = export_to_neo4j(nodes, edges)
print(f"Imported {stats['nodes_imported']} nodes, {stats['edges_imported']} edges")
```

### Building Cypher Queries

```python
from copilot_core.knowledge_graph.cypher_adapter import CypherBuilder, CypherTemplates

# Using the fluent builder
builder = CypherBuilder()
query, params = (
    builder
    .match("(n:Entity {id: $entity_id})")
    .optional_match("(n)-[r]-(neighbor)")
    .where("n.domain = $domain", domain="light")
    .return_expr("n, r, neighbor")
    .limit(100)
    .build()
)

# Execute with adapter
result = adapter.execute(query)

# Using pre-built templates
query, params = CypherTemplates.find_entity_with_relationships(
    "light.kitchen",
    max_hops=2
)
```

### Visualization Data Export

```python
from copilot_core.knowledge_graph.neo4j_adapter import get_visualization_data

# Export full graph
viz_data = get_visualization_data(max_nodes=500, max_edges=1000)

# Export subgraph around a node
viz_data = get_visualization_data(
    root_node="light.kitchen",
    max_nodes=100,
    include_properties=True,
)

# Use with D3.js
# viz_data['nodes'] and viz_data['edges'] are D3-ready
```

### Graph Analytics

```python
# Get statistics
stats = adapter.get_graph_stats()
print(f"Nodes: {stats['node_count']}, Edges: {stats['edge_count']}")

# Find central nodes
central = adapter.find_central_nodes(top_k=10)
for record in central.records:
    print(f"{record['label']}: degree={record['degree']}")

# Execute custom analytics query
from copilot_core.knowledge_graph.neo4j_adapter import CypherQuery

query = CypherQuery(
    query="""
    MATCH (n:Entity)
    WITH n, size((n)--()) AS degree
    ORDER BY degree DESC
    LIMIT 10
    RETURN n.label AS label, degree
    """,
    read_only=True,
)
result = adapter.execute(query)
```

## REST API Endpoints

### Neo4j-Specific Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/kg/neo4j/visualize` | GET | Export graph data for visualization |
| `/kg/neo4j/stats` | GET | Get Neo4j graph statistics |
| `/kg/neo4j/central` | GET | Get most central nodes |
| `/kg/neo4j/export` | POST | Export Brain Graph to Neo4j |
| `/kg/neo4j/schema` | GET | Ensure Neo4j schema (constraints/indexes) |
| `/kg/neo4j/query` | GET | Execute custom Cypher query (read-only) |

### Example Requests

#### Get Visualization Data

```bash
curl "http://localhost:8080/kg/neo4j/visualize?max_nodes=500&max_edges=1000"
```

#### Get Subgraph for Visualization

```bash
curl "http://localhost:8080/kg/neo4j/visualize?root=light.kitchen&include_properties=true"
```

#### Get Graph Statistics

```bash
curl "http://localhost:8080/kg/neo4j/stats"
```

#### Get Central Nodes

```bash
curl "http://localhost:8080/kg/neo4j/central?top=20"
```

#### Execute Custom Cypher Query

```bash
curl "http://localhost:8080/kg/neo4j/query?cypher=MATCH%20(n)%20RETURN%20n%20LIMIT%2010"
```

#### Export Brain Graph

```bash
curl -X POST "http://localhost:8080/kg/neo4j/export" \
  -H "Content-Type: application/json" \
  -d '{
    "nodes": [{"id": "test", "type": "entity", "label": "Test"}],
    "edges": []
  }'
```

## Neo4j Browser Usage

### Connecting to Neo4j Browser

1. Open Neo4j Browser at `http://localhost:7474`
2. Connect with:
   - URI: `bolt://localhost:7687`
   - Username: `neo4j`
   - Password: (your configured password)

### Useful Browser Commands

```cypher
// View all nodes
MATCH (n) RETURN n LIMIT 100;

// View graph schema
CALL db.schema.visualization();

// Find Entity nodes
MATCH (n:Entity) RETURN n LIMIT 50;

// Find relationships
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50;

// Find patterns for an entity
MATCH (p:Pattern)-[:INVOLVES]->(e:Entity {id: "light.kitchen"})
RETURN p, e;

// Find mood associations
MATCH (e:Entity)-[r:RELATES_TO_MOOD]->(m:Mood {id: "mood:relax"})
RETURN e, r, m;

// Get node degree distribution
MATCH (n)
WITH n, size((n)--()) AS degree
RETURN labels(n)[0] AS type, degree
ORDER BY degree DESC
LIMIT 20;

// Find orphan nodes (no relationships)
MATCH (n) WHERE NOT (n)--() RETURN n;

// Clear all data (use with caution!)
MATCH (n) DETACH DELETE n;
```

### Visualizing in Browser

```cypher
// Visualize subgraph around a node
MATCH (root {id: "light.kitchen"})
OPTIONAL MATCH (root)-[r]-(neighbor)
RETURN root, r, neighbor;

// Visualize by domain
MATCH (n:Entity {domain: "light"})
OPTIONAL MATCH (n)-[r]-(m)
RETURN n, r, m;
```

## Schema

### Node Labels

| Label | Description | Key Properties |
|-------|-------------|----------------|
| `Entity` | Home Assistant entities | `id`, `domain`, `area_id`, `capabilities` |
| `Zone` | Geographic zones | `id`, `label`, `area_ids` |
| `Area` | Physical areas | `id`, `label` |
| `Service` | External services | `id`, `label`, `type` |
| `Mood` | Mood states | `id`, `label` |
| `Pattern` | Discovered patterns | `id`, `confidence`, `support`, `lift` |
| `Context` | Contextual information | `id`, `label`, `type` |

### Relationship Types

| Type | Description | Properties |
|------|-------------|------------|
| `BELONGS_TO` | Entity → Area/Zone | `weight`, `confidence` |
| `CONTAINS` | Zone → Area | `weight` |
| `TRIGGERS` | Entity → Entity (patterns) | `confidence`, `time_window_sec` |
| `RELATES_TO_MOOD` | Entity → Mood | `weight`, `confidence` |
| `INVOLVES` | Pattern → Entity | `role` |
| `USES` | Service → Entity | `weight` |

### Constraints

```cypher
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Zone) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Area) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Service) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Mood) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Pattern) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Context) REQUIRE n.id IS UNIQUE;
```

### Indexes

```cypher
CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.label);
CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.domain);
CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.area_id);
CREATE INDEX IF NOT EXISTS FOR ()-[r:TRIGGERS]-() ON (r.confidence);
CREATE INDEX IF NOT EXISTS FOR ()-[r:BELONGS_TO]-() ON (r.weight);
```

## Error Handling

### Connection Failures

The adapter gracefully handles connection failures:

```python
adapter = Neo4jAdapter()
if not adapter.connect():
    # Fall back to SQLite or handle error
    print("Neo4j unavailable, using fallback")
```

### Query Validation

Write queries are rejected for safety:

```python
from copilot_core.knowledge_graph.cypher_adapter import CypherValidator

query = "MATCH (n) DELETE n"
is_safe, warning = CypherValidator.is_safe(query)
# is_safe = False, warning = "Query contains dangerous operation: DELETE"
```

## Testing

Run the test suite:

```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
python -m pytest tests/test_neo4j_integration_p3_006.py -v
```

### Test Coverage

- Neo4jAdapter connection lifecycle (8 tests)
- Schema management (3 tests)
- Brain Graph export (2 tests)
- Visualization export (2 tests)
- Graph analytics (2 tests)
- CypherQuery dataclass (1 test)
- CypherBuilder fluent API (6 tests)
- CypherTemplates (5 tests)
- CypherValidator (6 tests)
- CypherOptimizer (4 tests)
- API endpoints (2 tests)
- Error handling (3 tests)
- Convenience functions (3 tests)

**Total: 45+ test cases**

## Performance Considerations

### Batch Operations

Always use batch operations for bulk imports:

```python
# Good: batch export
stats = adapter.export_brain_graph(nodes, edges, batch_size=100)

# Bad: individual inserts (slow)
for node in nodes:
    adapter.execute(f"CREATE (n {{id: '{node.id}'}})")
```

### Query Optimization

Use the optimizer for suggestions:

```python
from copilot_core.knowledge_graph.cypher_adapter import CypherOptimizer

query = "MATCH (n) RETURN n"
suggestions = CypherOptimizer.suggest_optimizations(query)
# ['Node pattern without label - add label for better performance']
```

### Connection Pooling

Configure appropriate pool sizes:

```python
config = Neo4jConfig(
    max_pool_size=50,  # Adjust based on concurrent users
    timeout=30,        # Connection acquisition timeout
)
```

## Migration from SQLite

To migrate existing data from SQLite to Neo4j:

```python
from copilot_core.knowledge_graph.graph_store import get_graph_store
from copilot_core.knowledge_graph.neo4j_adapter import get_neo4j_adapter

# Get SQLite store
sqlite_store = get_graph_store()

# Get all nodes
all_nodes = []
from copilot_core.knowledge_graph.models import NodeType
for node_type in NodeType:
    nodes = sqlite_store.get_nodes_by_type(node_type, limit=10000)
    all_nodes.extend(nodes)

# Get all edges (implement get_all_edges if needed)
all_edges = sqlite_store.get_all_edges()

# Export to Neo4j
adapter = get_neo4j_adapter()
stats = adapter.export_brain_graph(all_nodes, all_edges)
print(f"Migrated {stats['nodes_imported']} nodes, {stats['edges_imported']} edges")
adapter.disconnect()
```

## Troubleshooting

### Connection Issues

1. Verify Neo4j is running: `docker ps | grep neo4j`
2. Check connection URI format: `bolt://host:port`
3. Verify credentials in environment variables
4. Test with Neo4j Browser first

### Query Performance

1. Add appropriate indexes
2. Use labels in MATCH patterns
3. Limit result sets
4. Avoid Cartesian products (use WITH between MATCH clauses)

### Schema Issues

Run schema setup:

```bash
curl http://localhost:8080/kg/neo4j/schema
```

Or in Python:

```python
adapter = get_neo4j_adapter()
result = adapter.ensure_schema()
print(result)
```

## Security Notes

- Only read-only queries are allowed via the `/kg/neo4j/query` endpoint
- Credentials should be stored securely (environment variables or secrets manager)
- Neo4j should not be exposed directly to the internet
- Use encrypted connections in production (`encrypted=True`)

## References

- [Neo4j Documentation](https://neo4j.com/docs/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/current/)
- [PilotSuite Knowledge Graph](./knowledge_graph.md)
