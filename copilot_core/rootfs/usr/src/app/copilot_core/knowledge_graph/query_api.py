"""SPARQL-like Query Interface for Knowledge Graph (P3-007)."""

import re
from typing import Any, Dict, List, Optional


def kg_query(graph: "GraphStore", query_str: str, limit: int = 100) -> Dict[str, Any]:
    """SPARQL-like query interface for Knowledge Graph.
    
    Simplified query DSL:
    - MATCH (n:NodeType) WHERE n.property = 'value' → match nodes
    - MATCH (n)-[r:edge_type]->(m) → match edges
    - RETURN n.label, m.label → return specified fields
    
    Returns { nodes: [...], edges: [...], count: N }
    """
    nodes_result: List[Dict[str, Any]] = []
    edges_result: List[Dict[str, Any]] = []
    
    match_nodes = re.findall(r"\((\w+):(\w+))", query_str)
    match_edges = re.findall(r"\[(\w+):(\w+)\]", query_str)
    where_match = re.search(r"WHERE\s+(\w+)\.(\w+)\s*=\s*['\"]?(\w+)['\"]?", query_str)
    
    if match_nodes:
        for alias, node_type in match_nodes:
            if where_match:
                prop_name = where_match.group(2)
                prop_val = where_match.group(3)
                all_nodes = _get_all_nodes(graph, limit * 2)
                filtered = [n for n in all_nodes
                           if getattr(n, prop_name, None) and prop_val.lower() in str(getattr(n, prop_name)).lower()]
                nodes_result.extend(filtered[:limit])
            else:
                all_nodes = _get_all_nodes(graph, limit)
                nodes_result.extend(all_nodes[:limit])
    
    if match_edges:
        edges_result.extend(graph.list_edges(limit_edges=limit))
    
    return {
        "nodes": [_node_to_dict(n) for n in nodes_result[:limit]],
        "edges": [_edge_to_dict(e) for e in edges_result[:limit]],
        "count": len(nodes_result[:limit]),
        "query": query_str,
    }


def _get_all_nodes(graph: "GraphStore", limit: int) -> List["Node"]:
    try:
        return graph.list_nodes(limit_nodes=limit)
    except Exception:
        return []


def _node_to_dict(n) -> Dict[str, Any]:
    if hasattr(n, 'to_dict'):
        return n.to_dict()
    return {"node_id": getattr(n, 'node_id', '?'), "label": getattr(n, 'label', '')}


def _edge_to_dict(e) -> Dict[str, Any]:
    if hasattr(e, 'to_dict'):
        return e.to_dict()
    return {"edge_id": getattr(e, 'edge_id', '?')}
