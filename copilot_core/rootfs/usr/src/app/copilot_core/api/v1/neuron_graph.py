"""Neuron Graph Data Structure - 14 Neurons + Connections.

Provides the graph structure for the Neuron Dashboard with:
- 14 Neurons (Context, State, Mood layers)
- Connection/Edge definitions
- Fire-Rate Tracking (last 60 seconds)
- Confidence Scoring per Neuron
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from collections import deque
import time

_LOGGER = logging.getLogger(__name__)


@dataclass
class NodeMetrics:
    """Live metrics for a neuron node."""
    fire_rate: float = 0.0  # Fires per minute (last 60s)
    confidence: float = 0.0  # Current confidence score
    avg_value: float = 0.0  # Average activation value
    trend: str = "stable"  # "increasing", "decreasing", "stable"
    last_fire_time: Optional[datetime] = None
    fire_history: deque = field(default_factory=lambda: deque(maxlen=60))  # Last 60 seconds
    
    def record_fire(self, value: float = 1.0):
        """Record a fire event."""
        now = datetime.now(timezone.utc)
        self.last_fire_time = now
        self.fire_history.append((now, value))
        self._update_fire_rate()
    
    def _update_fire_rate(self):
        """Update fire rate based on last 60 seconds."""
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - 60
        
        # Count fires in last 60 seconds
        recent_fires = [
            ts for ts, val in self.fire_history
            if ts.timestamp() > cutoff
        ]
        
        self.fire_rate = len(recent_fires)  # Fires per minute
    
    def update_confidence(self, confidence: float):
        """Update confidence score."""
        self.confidence = confidence
    
    def update_trend(self, current_value: float):
        """Update trend based on value changes."""
        if current_value > 0.7:
            self.trend = "increasing"
        elif current_value < 0.3:
            self.trend = "decreasing"
        else:
            self.trend = "stable"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "fire_rate": round(self.fire_rate, 3),
            "confidence": round(self.confidence, 3),
            "avg_value": round(self.avg_value, 3),
            "trend": self.trend,
            "last_fire_time": self.last_fire_time.isoformat() if self.last_fire_time else None
        }


@dataclass
class GraphNode:
    """A node in the neuron graph."""
    id: str
    name: str
    neuron_type: str  # "context", "state", "mood"
    layer: int  # 0=context, 1=state, 2=mood
    active: bool = False
    value: float = 0.0
    config: Dict[str, Any] = field(default_factory=dict)
    metrics: NodeMetrics = field(default_factory=NodeMetrics)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "neuron_type": self.neuron_type,
            "layer": self.layer,
            "active": self.active,
            "value": round(self.value, 3),
            "config": self.config,
            "metrics": self.metrics.to_dict()
        }


@dataclass
class GraphEdge:
    """An edge/connection between neurons."""
    source: str  # Source node ID
    target: str  # Target node ID
    weight: float = 1.0  # Connection strength
    edge_type: str = "synapse"  # "synapse", "feedback", "modulatory"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source": self.source,
            "target": self.target,
            "weight": round(self.weight, 3),
            "type": self.edge_type
        }


class NeuronGraph:
    """Complete neuron graph with 14 neurons and their connections."""
    
    # Define the 14 neurons
    NEURON_DEFINITIONS = [
        # Context Layer (5 neurons)
        {"id": "context.presence", "name": "Presence", "neuron_type": "context", "layer": 0},
        {"id": "context.time_of_day", "name": "Time of Day", "neuron_type": "context", "layer": 0},
        {"id": "context.light_level", "name": "Light Level", "neuron_type": "context", "layer": 0},
        {"id": "context.weather", "name": "Weather", "neuron_type": "context", "layer": 0},
        {"id": "context.activity", "name": "Activity", "neuron_type": "context", "layer": 0},
        
        # State Layer (5 neurons)
        {"id": "state.energy_level", "name": "Energy Level", "neuron_type": "state", "layer": 1},
        {"id": "state.comfort", "name": "Comfort", "neuron_type": "state", "layer": 1},
        {"id": "state.productivity", "name": "Productivity", "neuron_type": "state", "layer": 1},
        {"id": "state.relaxation", "name": "Relaxation", "neuron_type": "state", "layer": 1},
        {"id": "state.social", "name": "Social", "neuron_type": "state", "layer": 1},
        
        # Mood Layer (4 neurons)
        {"id": "mood.focus", "name": "Focus", "neuron_type": "mood", "layer": 2},
        {"id": "mood.relax", "name": "Relax", "neuron_type": "mood", "layer": 2},
        {"id": "mood.energy", "name": "Energy", "neuron_type": "mood", "layer": 2},
        {"id": "mood.calm", "name": "Calm", "neuron_type": "mood", "layer": 2},
    ]
    
    # Define connections between neurons
    CONNECTION_DEFINITIONS = [
        # Context -> State connections
        {"source": "context.presence", "target": "state.energy_level", "weight": 0.8},
        {"source": "context.presence", "target": "state.social", "weight": 0.7},
        {"source": "context.time_of_day", "target": "state.energy_level", "weight": 0.9},
        {"source": "context.time_of_day", "target": "state.productivity", "weight": 0.6},
        {"source": "context.light_level", "target": "state.comfort", "weight": 0.5},
        {"source": "context.light_level", "target": "state.relaxation", "weight": 0.6},
        {"source": "context.weather", "target": "state.comfort", "weight": 0.4},
        {"source": "context.weather", "target": "state.relaxation", "weight": 0.5},
        {"source": "context.activity", "target": "state.energy_level", "weight": 0.7},
        {"source": "context.activity", "target": "state.productivity", "weight": 0.8},
        
        # State -> Mood connections
        {"source": "state.energy_level", "target": "mood.energy", "weight": 0.9},
        {"source": "state.energy_level", "target": "mood.focus", "weight": 0.7},
        {"source": "state.comfort", "target": "mood.calm", "weight": 0.8},
        {"source": "state.comfort", "target": "mood.relax", "weight": 0.7},
        {"source": "state.productivity", "target": "mood.focus", "weight": 0.9},
        {"source": "state.relaxation", "target": "mood.relax", "weight": 0.9},
        {"source": "state.relaxation", "target": "mood.calm", "weight": 0.8},
        {"source": "state.social", "target": "mood.energy", "weight": 0.6},
        
        # Feedback connections (State -> Context)
        {"source": "state.energy_level", "target": "context.activity", "weight": 0.3, "edge_type": "feedback"},
        {"source": "state.comfort", "target": "context.light_level", "weight": 0.2, "edge_type": "feedback"},
        
        # Modulatory connections (Mood -> State)
        {"source": "mood.focus", "target": "state.productivity", "weight": 0.4, "edge_type": "modulatory"},
        {"source": "mood.relax", "target": "state.relaxation", "weight": 0.4, "edge_type": "modulatory"},
        {"source": "mood.energy", "target": "state.energy_level", "weight": 0.3, "edge_type": "modulatory"},
        {"source": "mood.calm", "target": "state.comfort", "weight": 0.3, "edge_type": "modulatory"},
    ]
    
    def __init__(self):
        """Initialize the neuron graph."""
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._initialize_graph()
    
    def _initialize_graph(self):
        """Initialize all nodes and edges."""
        # Create nodes
        for definition in self.NEURON_DEFINITIONS:
            node = GraphNode(
                id=definition["id"],
                name=definition["name"],
                neuron_type=definition["neuron_type"],
                layer=definition["layer"]
            )
            self.nodes[node.id] = node
        
        # Create edges
        for definition in self.CONNECTION_DEFINITIONS:
            edge = GraphEdge(
                source=definition["source"],
                target=definition["target"],
                weight=definition.get("weight", 1.0),
                edge_type=definition.get("edge_type", "synapse")
            )
            self.edges.append(edge)
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def update_node_state(self, node_id: str, active: bool, value: float, confidence: float):
        """Update a node's state and metrics."""
        node = self.nodes.get(node_id)
        if not node:
            return
        
        node.active = active
        node.value = value
        node.metrics.update_confidence(confidence)
        node.metrics.update_trend(value)
        
        if active:
            node.metrics.record_fire(value)
    
    def get_nodes_by_layer(self, layer: int) -> List[GraphNode]:
        """Get all nodes in a specific layer."""
        return [n for n in self.nodes.values() if n.layer == layer]
    
    def get_outgoing_edges(self, node_id: str) -> List[GraphEdge]:
        """Get all edges originating from a node."""
        return [e for e in self.edges if e.source == node_id]
    
    def get_incoming_edges(self, node_id: str) -> List[GraphEdge]:
        """Get all edges targeting a node."""
        return [e for e in self.edges if e.target == node_id]
    
    def get_connected_nodes(self, node_id: str, hops: int = 1) -> Set[str]:
        """Get all nodes connected to a node within N hops."""
        connected = set()
        to_visit = {node_id}
        visited = set()
        
        for hop in range(hops + 1):  # Include hop 0 (the node itself)
            next_visit = set()
            for current_id in to_visit:
                if current_id in visited:
                    continue
                visited.add(current_id)
                connected.add(current_id)
                
                # Add neighbors
                for edge in self.edges:
                    if edge.source == current_id:
                        next_visit.add(edge.target)
                    elif edge.target == current_id:
                        next_visit.add(edge.source)
            
            to_visit = next_visit
            if not to_visit:
                break
        
        return connected
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire graph to dictionary."""
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "metadata": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "layers": {
                    "context": len(self.get_nodes_by_layer(0)),
                    "state": len(self.get_nodes_by_layer(1)),
                    "mood": len(self.get_nodes_by_layer(2))
                }
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        active_nodes = sum(1 for n in self.nodes.values() if n.active)
        avg_fire_rate = sum(n.metrics.fire_rate for n in self.nodes.values()) / len(self.nodes)
        avg_confidence = sum(n.metrics.confidence for n in self.nodes.values()) / len(self.nodes)
        
        return {
            "total_nodes": len(self.nodes),
            "active_nodes": active_nodes,
            "total_edges": len(self.edges),
            "avg_fire_rate": round(avg_fire_rate, 3),
            "avg_confidence": round(avg_confidence, 3),
            "layers": {
                "context": {
                    "total": len(self.get_nodes_by_layer(0)),
                    "active": sum(1 for n in self.get_nodes_by_layer(0) if n.active)
                },
                "state": {
                    "total": len(self.get_nodes_by_layer(1)),
                    "active": sum(1 for n in self.get_nodes_by_layer(1) if n.active)
                },
                "mood": {
                    "total": len(self.get_nodes_by_layer(2)),
                    "active": sum(1 for n in self.get_nodes_by_layer(2) if n.active)
                }
            }
        }


# Singleton instance
_graph_instance: Optional[NeuronGraph] = None


def get_neuron_graph() -> NeuronGraph:
    """Get the singleton neuron graph instance."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = NeuronGraph()
    return _graph_instance


def reset_neuron_graph():
    """Reset the graph instance (for testing)."""
    global _graph_instance
    _graph_instance = None


def get_neuron_connections(node_id: Optional[str] = None) -> Dict[str, Any]:
    """Get connections between neurons.
    
    Args:
        node_id: Optional node ID to filter connections for a specific node
        
    Returns:
        Dictionary with connections data
    """
    graph = get_neuron_graph()
    
    if node_id:
        # Get connections for specific node
        node = graph.get_node(node_id)
        if not node:
            return {"error": f"Node not found: {node_id}"}
        
        incoming = graph.get_incoming_edges(node_id)
        outgoing = graph.get_outgoing_edges(node_id)
        
        return {
            "node_id": node_id,
            "node_name": node.name,
            "incoming": [edge.to_dict() for edge in incoming],
            "outgoing": [edge.to_dict() for edge in outgoing],
            "total_connections": len(incoming) + len(outgoing)
        }
    else:
        # Get all connections
        return {
            "total_connections": len(graph.edges),
            "connections": [edge.to_dict() for edge in graph.edges],
            "by_type": {
                "synapse": len([e for e in graph.edges if e.edge_type == "synapse"]),
                "feedback": len([e for e in graph.edges if e.edge_type == "feedback"]),
                "modulatory": len([e for e in graph.edges if e.edge_type == "modulatory"])
            }
        }


def find_paths(start_id: str, end_id: str, max_depth: int = 5) -> List[Dict[str, Any]]:
    """Find all paths between two nodes.
    
    Args:
        start_id: Starting node ID
        end_id: Ending node ID
        max_depth: Maximum path length to search
        
    Returns:
        List of paths, each path is a list of node IDs
    """
    graph = get_neuron_graph()
    
    start_node = graph.get_node(start_id)
    end_node = graph.get_node(end_id)
    
    if not start_node:
        raise ValueError(f"Start node not found: {start_id}")
    if not end_node:
        raise ValueError(f"End node not found: {end_id}")
    
    paths = []
    
    def dfs(current: str, target: str, path: List[str], visited: Set[str], depth: int):
        if depth > max_depth:
            return
        
        if current == target:
            paths.append(path.copy())
            return
        
        # Get outgoing edges
        for edge in graph.get_outgoing_edges(current):
            next_node = edge.target
            if next_node not in visited:
                visited.add(next_node)
                path.append(next_node)
                dfs(next_node, target, path, visited, depth + 1)
                path.pop()
                visited.remove(next_node)
    
    visited = {start_id}
    dfs(start_id, end_id, [start_id], visited, 0)
    
    return [
        {
            "path": path,
            "length": len(path) - 1,  # Number of edges
            "nodes": [graph.get_node(nid).name for nid in path if graph.get_node(nid)]
        }
        for path in paths
    ]


__all__ = [
    "NeuronGraph",
    "GraphNode",
    "GraphEdge",
    "NodeMetrics",
    "get_neuron_graph",
    "reset_neuron_graph",
    "get_neuron_connections",
    "find_paths"
]
