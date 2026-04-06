"""Brain Graph Query Optimizer (Slice 146).

Performance optimizations for large-scale graph queries:
- Index-based lookups
- Cached traversal results
- Batch node/edge operations
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Callable

from ..brain_graph.model import GraphNode, GraphEdge

_LOGGER = logging.getLogger(__name__)


class GraphIndex:
    """In-memory index for fast graph lookups."""
    
    def __init__(self):
        # node_id -> GraphNode
        self._nodes: Dict[str, GraphNode] = {}
        
        # node_type -> set of node_ids
        self._type_index: Dict[str, Set[str]] = {}
        
        # source_id -> set of edge_ids
        self._outgoing_edges: Dict[str, Set[str]] = {}
        
        # target_id -> set of edge_ids  
        self._incoming_edges: Dict[str, Set[str]] = {}
        
        # edge_type -> set of edge_ids
        self._edge_type_index: Dict[str, Set[str]] = {}
        
        self._lock = threading.RLock()
        self._last_update = 0.0
    
    def add_node(self, node: GraphNode) -> None:
        """Index a node."""
        with self._lock:
            self._nodes[node.node_id] = node
            
            if node.node_type not in self._type_index:
                self._type_index[node.node_type] = set()
            self._type_index[node.node_type].add(node.node_id)
            
            self._last_update = time.monotonic()
    
    def add_edge(self, edge: GraphEdge) -> None:
        """Index an edge."""
        with self._lock:
            # Outgoing from source
            if edge.source_id not in self._outgoing_edges:
                self._outgoing_edges[edge.source_id] = set()
            self._outgoing_edges[edge.source_id].add(edge.edge_id)
            
            # Incoming to target
            if edge.target_id not in self._incoming_edges:
                self._incoming_edges[edge.target_id] = set()
            self._incoming_edges[edge.target_id].add(edge.edge_id)
            
            # By edge type
            if edge.edge_type not in self._edge_type_index:
                self._edge_type_index[edge.edge_type] = set()
            self._edge_type_index[edge.edge_type].add(edge.edge_id)
            
            self._last_update = time.monotonic()
    
    def get_nodes_by_type(self, node_type: str) -> List[GraphNode]:
        """Fast lookup by node type."""
        with self._lock:
            node_ids = self._type_index.get(node_type, set())
            return [self._nodes[nid] for nid in node_ids if nid in self._nodes]
    
    def get_outgoing_edges(self, node_id: str) -> List[str]:
        """Get all outgoing edge IDs from a node."""
        with self._lock:
            return list(self._outgoing_edges.get(node_id, set()))
    
    def get_incoming_edges(self, node_id: str) -> List[str]:
        """Get all incoming edge IDs to a node."""
        with self._lock:
            return list(self._incoming_edges.get(node_id, set()))
    
    def get_edges_by_type(self, edge_type: str) -> List[str]:
        """Get all edge IDs of a specific type."""
        with self._lock:
            return list(self._edge_type_index.get(edge_type, set()))


class QueryCache:
    """TTL cache for expensive graph queries."""
    
    def __init__(self, ttl_seconds: float = 60.0, max_size: int = 1000):
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.RLock()
    
    def _make_key(self, func_name: str, *args, **kwargs) -> str:
        """Create cache key from function call."""
        key_parts = [func_name]
        key_parts.extend(str(a) for a in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return "|".join(key_parts)
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached result if valid."""
        with self._lock:
            if key in self._cache:
                result, timestamp = self._cache[key]
                if time.monotonic() - timestamp < self._ttl:
                    return result
                else:
                    del self._cache[key]
            return None
    
    def set(self, key: str, value: Any) -> None:
        """Cache a result."""
        with self._lock:
            # Evict oldest if at capacity (simple LRU)
            if len(self._cache) >= self._max_size:
                oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            
            self._cache[key] = (value, time.monotonic())
    
    def clear(self) -> None:
        """Clear all cached results."""
        with self._lock:
            self._cache.clear()


def cached_query(cache: QueryCache):
    """Decorator to cache graph query results."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # First arg should be self with cache
            if hasattr(args[0], '_query_cache'):
                instance_cache = args[0]._query_cache
                key = f"{func.__name__}|{str(args[1:])}|{str(sorted(kwargs.items()))}"
                
                cached = instance_cache.get(key)
                if cached is not None:
                    return cached
                
                result = func(*args, **kwargs)
                instance_cache.set(key, result)
                return result
            else:
                return func(*args, **kwargs)
        return wrapper
    return decorator


class OptimizedGraphService:
    """Brain Graph Service with query optimizations."""
    
    def __init__(self):
        self._index = GraphIndex()
        self._query_cache = QueryCache(ttl_seconds=30.0)
        self._initialized = False
    
    def initialize_from_service(self, service) -> None:
        """Build index from existing BrainGraphService."""
        if self._initialized:
            return
        
        _LOGGER.info("Building graph index...")
        start = time.monotonic()
        
        # Index all nodes
        for node in service.get_all_nodes():
            self._index.add_node(node)
        
        # Index all edges
        for edge in service.get_all_edges():
            self._index.add_edge(edge)
        
        elapsed = time.monotonic() - start
        _LOGGER.info("Graph index built in %.2fms", elapsed * 1000)
        self._initialized = True
    
    @cached_query(_query_cache)
    def find_pattern_paths(
        self,
        start_node_type: str,
        end_node_type: str,
        max_depth: int = 3
    ) -> List[List[str]]:
        """Find all paths between node types (cached)."""
        paths = []
        start_nodes = self._index.get_nodes_by_type(start_node_type)
        
        for start_node in start_nodes:
            self._dfs_paths(start_node.node_id, end_node_type, [start_node.node_id], max_depth, paths)
        
        return paths
    
    def _dfs_paths(
        self,
        current: str,
        target_type: str,
        path: List[str],
        max_depth: int,
        results: List[List[str]]
    ) -> None:
        """Depth-first search for paths."""
        if len(path) > max_depth:
            return
        
        # Check if current node is target type
        if current in self._index._nodes:
            node = self._index._nodes[current]
            if node.node_type == target_type and len(path) > 1:
                results.append(path.copy())
                return
        
        # Explore outgoing edges
        for edge_id in self._index.get_outgoing_edges(current):
            # Parse edge_id to get target
            # Edge format: "source--type--target"
            parts = edge_id.split("--")
            if len(parts) == 3:
                target = parts[2]
                if target not in path:  # Avoid cycles
                    path.append(target)
                    self._dfs_paths(target, target_type, path, max_depth, results)
                    path.pop()
    
    def get_neighborhood(
        self,
        node_id: str,
        radius: int = 1
    ) -> Dict[str, List[str]]:
        """Get all nodes within radius (cached)."""
        cache_key = f"neighborhood|{node_id}|{radius}"
        cached = self._query_cache.get(cache_key)
        if cached:
            return cached
        
        result = {"nodes": [], "edges": []}
        visited = {node_id}
        current_level = {node_id}
        
        for _ in range(radius):
            next_level = set()
            for nid in current_level:
                # Outgoing edges
                for edge_id in self._index.get_outgoing_edges(nid):
                    parts = edge_id.split("--")
                    if len(parts) == 3:
                        target = parts[2]
                        if target not in visited:
                            visited.add(target)
                            next_level.add(target)
                            result["nodes"].append(target)
                            result["edges"].append(edge_id)
                
                # Incoming edges
                for edge_id in self._index.get_incoming_edges(nid):
                    parts = edge_id.split("--")
                    if len(parts) == 3:
                        source = parts[0]
                        if source not in visited:
                            visited.add(source)
                            next_level.add(source)
                            result["nodes"].append(source)
                            result["edges"].append(edge_id)
            
            current_level = next_level
        
        self._query_cache.set(cache_key, result)
        return result
