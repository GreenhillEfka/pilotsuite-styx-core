# Neuron Graph API Documentation

## Overview

The Neuron Graph API provides endpoints for visualizing and analyzing the 14-neuron neural system used in PilotSuite Styx. The graph consists of three layers:

- **Context Layer (5 neurons)**: presence, time_of_day, light_level, weather, activity
- **State Layer (5 neurons)**: energy_level, comfort, productivity, relaxation, social
- **Mood Layer (4 neurons)**: focus, relax, energy, calm

## Base URL

```
/api/v1/neurons
```

## Authentication

All endpoints require authentication via:
- `X-Auth-Token` header, or
- `Authorization: Bearer <token>` header

---

## Endpoints

### 1. GET /graph

Get complete neuron graph with all nodes and edges.

**Response:**
```json
{
  "success": true,
  "data": {
    "nodes": [
      {
        "id": "context.presence",
        "name": "Presence",
        "neuron_type": "context",
        "layer": 0,
        "active": false,
        "value": 0.0,
        "config": {},
        "metrics": {
          "fire_rate": 0.0,
          "confidence": 0.0,
          "avg_value": 0.0,
          "trend": "stable",
          "last_fire_time": null
        }
      }
      // ... 13 more nodes
    ],
    "edges": [
      {
        "source": "context.presence",
        "target": "state.energy_level",
        "weight": 0.8,
        "type": "synapse"
      }
      // ... more edges
    ],
    "metadata": {
      "total_nodes": 14,
      "total_edges": 22,
      "layers": {
        "context": 5,
        "state": 5,
        "mood": 4
      }
    }
  }
}
```

---

### 2. GET /graph/stats

Get overall graph statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "total_nodes": 14,
    "active_nodes": 3,
    "total_edges": 22,
    "avg_fire_rate": 1.234,
    "avg_confidence": 0.756,
    "layers": {
      "context": {
        "total": 5,
        "active": 2
      },
      "state": {
        "total": 5,
        "active": 1
      },
      "mood": {
        "total": 4,
        "active": 0
      }
    }
  }
}
```

---

### 3. GET /connections

Get connections between neurons.

**Query Parameters:**
- `node_id` (optional): Filter connections for a specific node

**Example 1: Get all connections**
```
GET /api/v1/neurons/connections
```

**Response:**
```json
{
  "success": true,
  "data": {
    "total_connections": 22,
    "connections": [
      {
        "source": "context.presence",
        "target": "state.energy_level",
        "weight": 0.8,
        "type": "synapse"
      }
      // ... more connections
    ],
    "by_type": {
      "synapse": 18,
      "feedback": 2,
      "modulatory": 4
    }
  }
}
```

**Example 2: Get connections for specific node**
```
GET /api/v1/neurons/connections?node_id=context.presence
```

**Response:**
```json
{
  "success": true,
  "data": {
    "node_id": "context.presence",
    "node_name": "Presence",
    "incoming": [
      {
        "source": "state.energy_level",
        "target": "context.presence",
        "weight": 0.3,
        "type": "feedback"
      }
    ],
    "outgoing": [
      {
        "source": "context.presence",
        "target": "state.energy_level",
        "weight": 0.8,
        "type": "synapse"
      },
      {
        "source": "context.presence",
        "target": "state.social",
        "weight": 0.7,
        "type": "synapse"
      }
    ],
    "total_connections": 3
  }
}
```

---

### 4. GET /paths

Find all paths between two neurons.

**Query Parameters:**
- `from` (required): Starting node ID
- `to` (required): Ending node ID
- `max_depth` (optional): Maximum path length (default: 5, max: 10)

**Example:**
```
GET /api/v1/neurons/paths?from=context.presence&to=mood.energy
```

**Response:**
```json
{
  "success": true,
  "data": {
    "from": "context.presence",
    "to": "mood.energy",
    "paths": [
      {
        "path": ["context.presence", "state.energy_level", "mood.energy"],
        "length": 2,
        "nodes": ["Presence", "Energy Level", "Energy"]
      },
      {
        "path": ["context.presence", "state.social", "mood.energy"],
        "length": 2,
        "nodes": ["Presence", "Social", "Energy"]
      }
    ],
    "path_count": 2,
    "max_depth": 5
  }
}
```

**Error Response (missing parameters):**
```json
{
  "success": false,
  "error": "Missing required parameters: 'from' and 'to'"
}
```

**Error Response (node not found):**
```json
{
  "success": false,
  "error": "Start node not found: nonexistent.node"
}
```

---

### 5. GET /<neuron_id>/stats

Get statistics for a specific neuron.

**Path Parameters:**
- `neuron_id`: Neuron identifier (e.g., "context.presence", "mood.focus")

**Example:**
```
GET /api/v1/neurons/context.presence/stats
```

**Response:**
```json
{
  "success": true,
  "data": {
    "neuron_id": "context.presence",
    "name": "Presence",
    "type": "context",
    "layer": 0,
    "active": true,
    "value": 0.8,
    "metrics": {
      "fire_rate": 3.5,
      "confidence": 0.92,
      "avg_value": 0.75,
      "trend": "increasing",
      "last_fire_time": "2025-03-03T14:30:00+00:00"
    },
    "connections": {
      "incoming": 1,
      "outgoing": 2
    }
  }
}
```

---

## Connection Types

The graph supports three types of connections:

1. **Synapse**: Forward connections (Context → State, State → Mood)
2. **Feedback**: Backward connections (State → Context)
3. **Modulatory**: Mood influencing State (Mood → State)

---

## Node Metrics

Each neuron tracks the following metrics:

- **fire_rate**: Number of activations in the last 60 seconds
- **confidence**: Current confidence score (0.0 - 1.0)
- **avg_value**: Average activation value
- **trend**: Direction of change ("increasing", "decreasing", "stable")
- **last_fire_time**: Timestamp of last activation

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (missing/invalid parameters) |
| 401 | Unauthorized (missing/invalid auth token) |
| 404 | Not Found (neuron doesn't exist) |
| 500 | Internal Server Error |

---

## Usage Examples

### cURL

```bash
# Get complete graph
curl -H "X-Auth-Token: your-token" \
  http://localhost:5000/api/v1/neurons/graph

# Get connections for a specific node
curl -H "X-Auth-Token: your-token" \
  "http://localhost:5000/api/v1/neurons/connections?node_id=mood.focus"

# Find paths between neurons
curl -H "X-Auth-Token: your-token" \
  "http://localhost:5000/api/v1/neurons/paths?from=context.time_of_day&to=mood.relax&max_depth=3"
```

### JavaScript/TypeScript

```typescript
// Fetch neuron graph
const response = await fetch('/api/v1/neurons/graph', {
  headers: {
    'X-Auth-Token': token
  }
});
const { data } = await response.json();
console.log(`Graph has ${data.nodes.length} nodes and ${data.edges.length} edges`);

// Find paths
const pathsResponse = await fetch(
  '/api/v1/neurons/paths?from=context.presence&to=mood.focus',
  { headers: { 'X-Auth-Token': token } }
);
const { data: pathData } = await pathsResponse.json();
console.log(`Found ${pathData.path_count} paths`);
```

### Python

```python
import requests

headers = {'X-Auth-Token': 'your-token'}

# Get graph
response = requests.get('http://localhost:5000/api/v1/neurons/graph', headers=headers)
graph = response.json()['data']
print(f"Nodes: {len(graph['nodes'])}, Edges: {len(graph['edges'])}")

# Get paths
response = requests.get(
    'http://localhost:5000/api/v1/neurons/paths',
    params={'from': 'context.weather', 'to': 'mood.calm'},
    headers=headers
)
paths = response.json()['data']
for path in paths['paths']:
    print(f"Path: {' -> '.join(path['nodes'])}")
```

---

## Testing

Run the test suite:

```bash
cd /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app
python3 -m pytest tests/test_neuron_graph.py tests/test_neurons_api.py -v
```

All 89 tests should pass, including:
- 46 unit tests for graph data structures
- 12 API endpoint tests
- 31 existing neuron API tests

---

## Implementation Details

- **Singleton Pattern**: Graph instance is shared across requests
- **Thread-Safe**: Metrics updates are thread-safe
- **Caching**: Graph structure is cached; metrics are live
- **Validation**: All neuron IDs are validated before processing
- **Rate Limiting**: Path finding is capped at max_depth=10 to prevent DoS

---

## Related Files

- `copilot_core/api/v1/neuron_graph.py` - Graph data structures and functions
- `copilot_core/api/v1/neurons.py` - Flask API endpoints
- `tests/test_neuron_graph.py` - Unit tests for graph logic
- `tests/test_neurons_api.py` - Integration tests for API endpoints
