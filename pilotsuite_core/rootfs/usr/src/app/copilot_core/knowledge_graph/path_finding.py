"""Path Finding and Graph Traversal for Knowledge Graph.

Provides algorithms for finding paths and relationships in the knowledge graph:
- Shortest path between entities
- All paths within N hops
- Connected components
- Reachability analysis
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from .models import Edge, EdgeType, GraphResult, Node, NodeType

_LOGGER = logging.getLogger(__name__)


# ==================== Path Finding Types ====================

@dataclass
class PathResult:
    """Result from a path finding operation."""
    start_node: Node
    end_node: Node
    path: list[Node]
    edges: list[Edge]
    total_weight: float = 1.0
    hop_count: int = 0


@dataclass
class PathQuery:
    """Query for finding paths in the graph."""
    start_id: str
    end_id: str
    max_hops: int = 5
    edge_types: Optional[list[EdgeType]] = None
    node_types: Optional[list[NodeType]] = None
    min_confidence: float = 0.0


@dataclass
class NeighborhoodQuery:
    """Query for finding nodes within N hops."""
    center_id: str
    max_hops: int = 2
    edge_types: Optional[list[EdgeType]] = None
    include_center: bool = True


@dataclass
class ConnectivityQuery:
    """Query for analyzing graph connectivity."""
    node_ids: Optional[list[str]] = None
    zone_id: Optional[str] = None
    domain: Optional[str] = None


# ==================== Path Finding Algorithms ====================

class GraphPathFinder:
    """
    Path finding and graph traversal algorithms for the knowledge graph.

    Example:
        finder = GraphPathFinder(graph_store)
        path = finder.find_shortest_path(
            start_id="light.kitchen",
            end_id="sensor.motion_kitchen",
            max_hops=3,
        )
    """

    def __init__(self, graph_store: Any) -> None:
        self._store = graph_store

    def find_shortest_path(
        self,
        start_id: str,
        end_id: str,
        max_hops: int = 5,
        edge_types: Optional[list[EdgeType]] = None,
    ) -> Optional[PathResult]:
        """
        Find the shortest path between two nodes using BFS.

        Args:
            start_id: Starting node ID
            end_id: Target node ID
            max_hops: Maximum number of hops to search
            edge_types: Filter by edge types (None for all)

        Returns:
            PathResult if path found, None otherwise
        """
        if start_id == end_id:
            start_node = self._store.get_node(start_id)
            if start_node:
                return PathResult(
                    start_node=start_node,
                    end_node=start_node,
                    path=[start_node],
                    edges=[],
                    total_weight=0.0,
                    hop_count=0,
                )
            return None

        # BFS
        queue: deque = deque()
        queue.append((start_id, [start_id], []))
        visited = {start_id}

        while queue:
            current_id, path_ids, edge_ids = queue.popleft()

            if len(path_ids) > max_hops:
                continue

            # Get edges from current node
            edges = self._store.get_edges_by_node(
                current_id,
                edge_type=None,  # Get all edges
                direction="both",
            )

            # Filter by edge types if specified
            if edge_types:
                edges = [e for e in edges if e.type in edge_types]

            for edge in edges:
                # Determine next node
                next_id = edge.target if edge.source == current_id else edge.source

                if next_id == end_id:
                    # Path found
                    final_path_ids = path_ids + [next_id]
                    final_edge_ids = edge_ids + [edge.id]

                    # Resolve nodes and edges
                    nodes = [self._store.get_node(nid) for nid in final_path_ids]
                    nodes = [n for n in nodes if n]

                    resolved_edges = []
                    for eid in final_edge_ids:
                        # Find edge by ID
                        for e in edges:
                            if e.id == eid:
                                resolved_edges.append(e)
                                break

                    if len(nodes) == len(final_path_ids):
                        return PathResult(
                            start_node=nodes[0],
                            end_node=nodes[-1],
                            path=nodes,
                            edges=resolved_edges,
                            total_weight=sum(e.weight for e in resolved_edges),
                            hop_count=len(nodes) - 1,
                        )

                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, path_ids + [next_id], edge_ids + [edge.id]))

        return None

    def find_all_paths(
        self,
        start_id: str,
        end_id: str,
        max_hops: int = 5,
        edge_types: Optional[list[EdgeType]] = None,
        max_paths: int = 10,
    ) -> list[PathResult]:
        """
        Find all paths between two nodes up to max_hops.

        Args:
            start_id: Starting node ID
            end_id: Target node ID
            max_hops: Maximum number of hops
            edge_types: Filter by edge types
            max_paths: Maximum number of paths to return

        Returns:
            List of PathResult objects
        """
        all_paths: list[PathResult] = []

        # DFS with path tracking
        def dfs(
            current_id: str,
            path_ids: list[str],
            edge_list: list[Edge],
            visited: set[str],
        ):
            if len(all_paths) >= max_paths:
                return

            if current_id == end_id and len(path_ids) > 1:
                nodes = [self._store.get_node(nid) for nid in path_ids]
                nodes = [n for n in nodes if n]

                if len(nodes) == len(path_ids):
                    all_paths.append(PathResult(
                        start_node=nodes[0],
                        end_node=nodes[-1],
                        path=nodes,
                        edges=edge_list,
                        total_weight=sum(e.weight for e in edge_list),
                        hop_count=len(nodes) - 1,
                    ))
                return

            if len(path_ids) > max_hops:
                return

            edges = self._store.get_edges_by_node(
                current_id,
                edge_type=None,
                direction="both",
            )

            if edge_types:
                edges = [e for e in edges if e.type in edge_types]

            for edge in edges:
                next_id = edge.target if edge.source == current_id else edge.source

                if next_id not in visited:
                    new_visited = visited | {next_id}
                    dfs(
                        next_id,
                        path_ids + [next_id],
                        edge_list + [edge],
                        new_visited,
                    )

        dfs(start_id, [start_id], [], {start_id})
        return all_paths

    def find_neighbors(
        self,
        center_id: str,
        max_hops: int = 1,
        edge_types: Optional[list[EdgeType]] = None,
        node_types: Optional[list[NodeType]] = None,
        include_center: bool = True,
    ) -> GraphResult:
        """
        Find all nodes within N hops of a center node.

        Args:
            center_id: Center node ID
            max_hops: Maximum number of hops
            edge_types: Filter by edge types
            node_types: Filter neighbor nodes by type
            include_center: Whether to include the center node

        Returns:
            GraphResult with all nodes and edges in the neighborhood
        """
        center_node = self._store.get_node(center_id)
        if not center_node:
            return GraphResult(nodes=[], edges=[])

        nodes: dict[str, Node] = {}
        edges: dict[str, Edge] = {}

        if include_center:
            nodes[center_id] = center_node

        # BFS up to max_hops
        queue: deque = deque()
        queue.append((center_id, 0))
        visited = {center_id}

        while queue:
            current_id, hops = queue.popleft()

            if hops >= max_hops:
                continue

            edges_from_node = self._store.get_edges_by_node(
                current_id,
                edge_type=None,
                direction="both",
            )

            if edge_types:
                edges_from_node = [e for e in edges_from_node if e.type in edge_types]

            for edge in edges_from_node:
                next_id = edge.target if edge.source == current_id else edge.source

                if next_id not in visited:
                    visited.add(next_id)

                    node = self._store.get_node(next_id)
                    if node:
                        # Filter by node types if specified
                        if node_types is None or node.type in node_types:
                            nodes[next_id] = node
                            edges[edge.id] = edge
                            queue.append((next_id, hops + 1))
                    else:
                        edges[edge.id] = edge
                        queue.append((next_id, hops + 1))

        return GraphResult(
            nodes=list(nodes.values()),
            edges=list(edges.values()),
            confidence=1.0,
            sources=["neighborhood_query"],
        )

    def find_connected_components(
        self,
        node_ids: Optional[list[str]] = None,
        edge_types: Optional[list[EdgeType]] = None,
    ) -> list[list[str]]:
        """
        Find connected components in the graph.

        Args:
            node_ids: Subset of nodes to analyze (None for all)
            edge_types: Filter by edge types

        Returns:
            List of components, each component is a list of node IDs
        """
        # Get all nodes if not specified
        if node_ids is None:
            all_nodes = []
            for node_type in NodeType:
                all_nodes.extend(self._store.get_nodes_by_type(node_type, limit=1000))
            node_ids = [n.id for n in all_nodes]

        visited = set()
        components: list[list[str]] = []

        for start_id in node_ids:
            if start_id in visited:
                continue

            # BFS to find component
            component: list[str] = []
            queue: deque = deque([start_id])
            visited.add(start_id)

            while queue:
                current_id = queue.popleft()
                component.append(current_id)

                edges = self._store.get_edges_by_node(
                    current_id,
                    edge_type=None,
                    direction="both",
                )

                if edge_types:
                    edges = [e for e in edges if e.type in edge_types]

                for edge in edges:
                    next_id = edge.target if edge.source == current_id else edge.source

                    if next_id not in visited and (node_ids is None or next_id in node_ids):
                        visited.add(next_id)
                        queue.append(next_id)

            if component:
                components.append(component)

        return components

    def is_reachable(
        self,
        start_id: str,
        end_id: str,
        max_hops: int = 10,
        edge_types: Optional[list[EdgeType]] = None,
    ) -> bool:
        """
        Check if end_id is reachable from start_id.

        Args:
            start_id: Starting node ID
            end_id: Target node ID
            max_hops: Maximum hops to search
            edge_types: Filter by edge types

        Returns:
            True if reachable, False otherwise
        """
        if start_id == end_id:
            return True

        visited = {start_id}
        queue: deque = deque([(start_id, 0)])

        while queue:
            current_id, hops = queue.popleft()

            if hops >= max_hops:
                continue

            edges = self._store.get_edges_by_node(
                current_id,
                edge_type=None,
                direction="both",
            )

            if edge_types:
                edges = [e for e in edges if e.type in edge_types]

            for edge in edges:
                next_id = edge.target if edge.source == current_id else edge.source

                if next_id == end_id:
                    return True

                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, hops + 1))

        return False

    def find_bridge_nodes(
        self,
        node_ids: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Find bridge nodes that connect different parts of the graph.

        Bridge nodes are those whose removal would disconnect the graph.

        Args:
            node_ids: Subset of nodes to analyze

        Returns:
            List of bridge node IDs
        """
        if node_ids is None:
            all_nodes = []
            for node_type in NodeType:
                all_nodes.extend(self._store.get_nodes_by_type(node_type, limit=1000))
            node_ids = [n.id for n in all_nodes]

        bridge_nodes = []

        for test_id in node_ids:
            # Get neighbors of test node
            test_edges = self._store.get_edges_by_node(
                test_id,
                edge_type=None,
                direction="both",
            )

            if len(test_edges) < 2:
                continue  # Can't be a bridge with < 2 connections

            neighbor_ids = []
            for edge in test_edges:
                neighbor_ids.append(
                    edge.target if edge.source == test_id else edge.source
                )

            # Check if any pair of neighbors becomes disconnected without test node
            for i, n1 in enumerate(neighbor_ids):
                for n2 in neighbor_ids[i + 1:]:
                    # Check reachability without test_id
                    if not self._is_reachable_excluding(n1, n2, exclude=test_id):
                        bridge_nodes.append(test_id)
                        break

                if test_id in bridge_nodes:
                    break

        return list(set(bridge_nodes))

    def _is_reachable_excluding(
        self,
        start_id: str,
        end_id: str,
        exclude: str,
        max_hops: int = 10,
    ) -> bool:
        """Check reachability while excluding a specific node."""
        if start_id == end_id:
            return True

        visited = {start_id, exclude}
        queue: deque = deque([(start_id, 0)])

        while queue:
            current_id, hops = queue.popleft()

            if hops >= max_hops:
                continue

            edges = self._store.get_edges_by_node(
                current_id,
                edge_type=None,
                direction="both",
            )

            for edge in edges:
                next_id = edge.target if edge.source == current_id else edge.source

                if next_id == end_id:
                    return True

                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, hops + 1))

        return False
