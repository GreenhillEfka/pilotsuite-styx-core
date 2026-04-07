"""Knowledge Graph API endpoints.

Provides REST API for querying and managing the Knowledge Graph.
Includes Neo4j integration endpoints for visualization and advanced queries.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from .models import EdgeType, GraphQuery, NodeType
from .graph_store import get_graph_store
from .builder import GraphBuilder
from .pattern_importer import PatternImporter

try:
    from .neo4j_adapter import get_neo4j_adapter, Neo4jAdapter, Neo4jConfig
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    _LOGGER = logging.getLogger(__name__)
    _LOGGER.warning("Neo4j adapter not available - install neo4j driver")

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("knowledge_graph", __name__, url_prefix="/kg")


def _store():
    """Get the graph store singleton."""
    return get_graph_store()


def _builder():
    """Get a new graph builder."""
    return GraphBuilder(_store())


def _importer():
    """Get a new pattern importer."""
    return PatternImporter(_store())


# ==================== Stats ====================

@bp.get("/stats")
def kg_stats():
    """Get knowledge graph statistics."""
    try:
        stats = _store().stats()
        return jsonify({"ok": True, "stats": stats})
    except Exception as e:
        _LOGGER.exception("Failed to get graph stats")
        return jsonify({"ok": False, "error": str(e)}), 500


# ==================== Node Operations ====================

@bp.get("/nodes")
def kg_list_nodes():
    """List nodes with optional filtering."""
    try:
        node_type = request.args.get("type")
        limit = min(int(request.args.get("limit", 100)), 500)
        
        if node_type:
            try:
                ntype = NodeType(node_type)
                nodes = _store().get_nodes_by_type(ntype, limit)
                return jsonify({
                    "ok": True,
                    "nodes": [n.to_dict() for n in nodes],
                    "count": len(nodes),
                })
            except ValueError:
                return jsonify({
                    "ok": False,
                    "error": f"Invalid node type: {node_type}",
                }), 400
        else:
            # Get all types (limited)
            all_nodes = []
            for ntype in NodeType:
                nodes = _store().get_nodes_by_type(ntype, limit // len(NodeType))
                all_nodes.extend(nodes)
                if len(all_nodes) >= limit:
                    break
            
            return jsonify({
                "ok": True,
                "nodes": [n.to_dict() for n in all_nodes[:limit]],
                "count": min(len(all_nodes), limit),
            })
    except Exception as e:
        _LOGGER.exception("Failed to list nodes")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/nodes/<path:node_id>")
def kg_get_node(node_id: str):
    """Get a specific node by ID."""
    try:
        node = _store().get_node(node_id)
        if node:
            return jsonify({"ok": True, "node": node.to_dict()})
        else:
            return jsonify({"ok": False, "error": "Node not found"}), 404
    except Exception as e:
        _LOGGER.exception("Failed to get node %s", node_id)
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/nodes")
def kg_create_node():
    """Create a new node."""
    try:
        data = request.get_json() or {}
        
        node_id = data.get("id")
        node_type = data.get("type")
        label = data.get("label", node_id)
        properties = data.get("properties", {})
        
        if not node_id or not node_type:
            return jsonify({
                "ok": False,
                "error": "Missing required fields: id, type",
            }), 400
        
        try:
            ntype = NodeType(node_type)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid node type: {node_type}",
            }), 400
        
        from .models import Node
        node = Node(
            id=node_id,
            type=ntype,
            label=label,
            properties=properties,
        )
        _store().add_node(node)
        
        return jsonify({"ok": True, "node": node.to_dict()}), 201
    except Exception as e:
        _LOGGER.exception("Failed to create node")
        return jsonify({"ok": False, "error": str(e)}), 500


# ==================== Edge Operations ====================

@bp.get("/edges")
def kg_list_edges():
    """List edges with optional filtering."""
    try:
        source = request.args.get("source")
        target = request.args.get("target")
        edge_type = request.args.get("type")
        limit = min(int(request.args.get("limit", 100)), 500)
        
        edges = []
        
        if source:
            etype = EdgeType(edge_type) if edge_type else None
            edges = _store().get_edges_from(source, etype)
        elif target:
            etype = EdgeType(edge_type) if edge_type else None
            edges = _store().get_edges_to(target, etype)
        else:
            # Get all edges (expensive, limited) - pagination to be implemented in v1.1
            return jsonify({
                "ok": False,
                "error": "Must specify source or target",
            }), 400
        
        edges = edges[:limit]
        return jsonify({
            "ok": True,
            "edges": [e.to_dict() for e in edges],
            "count": len(edges),
        })
    except Exception as e:
        _LOGGER.exception("Failed to list edges")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/edges")
def kg_create_edge():
    """Create a new edge."""
    try:
        data = request.get_json() or {}
        
        source = data.get("source")
        target = data.get("target")
        edge_type = data.get("type")
        weight = data.get("weight", 1.0)
        confidence = data.get("confidence", 0.0)
        source_type = data.get("source_type", "inferred")
        evidence = data.get("evidence", {})
        
        if not source or not target or not edge_type:
            return jsonify({
                "ok": False,
                "error": "Missing required fields: source, target, type",
            }), 400
        
        try:
            etype = EdgeType(edge_type)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid edge type: {edge_type}",
            }), 400
        
        from .models import Edge
        edge = Edge(
            source=source,
            target=target,
            type=etype,
            weight=weight,
            confidence=confidence,
            source_type=source_type,
            evidence=evidence,
        )
        _store().add_edge(edge)
        
        return jsonify({"ok": True, "edge": edge.to_dict()}), 201
    except Exception as e:
        _LOGGER.exception("Failed to create edge")
        return jsonify({"ok": False, "error": str(e)}), 500


# ==================== Query Operations ====================

@bp.post("/query")
def kg_query():
    """Execute a graph query."""
    try:
        data = request.get_json() or {}
        
        query = GraphQuery(
            query_type=data.get("query_type", "structural"),
            entity_id=data.get("entity_id"),
            zone_id=data.get("zone_id"),
            mood=data.get("mood"),
            time_context=data.get("time_context"),
            pattern_id=data.get("pattern_id"),
            max_results=data.get("max_results", 10),
            min_confidence=data.get("min_confidence", 0.5),
            include_evidence=data.get("include_evidence", False),
        )
        
        result = _store().query(query)
        
        return jsonify({
            "ok": True,
            "result": result.to_dict(),
        })
    except Exception as e:
        _LOGGER.exception("Failed to execute query")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/entity/<path:entity_id>/related")
def kg_entity_related(entity_id: str):
    """Get entities related to a specific entity."""
    try:
        min_confidence = float(request.args.get("min_confidence", 0.5))
        limit = min(int(request.args.get("limit", 10)), 50)
        
        query = GraphQuery(
            query_type="structural",
            entity_id=entity_id,
            max_results=limit,
            min_confidence=min_confidence,
            include_evidence=True,
        )
        
        result = _store().query(query)
        
        return jsonify({
            "ok": True,
            "entity_id": entity_id,
            "related": result.to_dict(),
        })
    except Exception as e:
        _LOGGER.exception("Failed to get related entities for %s", entity_id)
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/zone/<path:zone_id>/entities")
def kg_zone_entities(zone_id: str):
    """Get all entities in a zone."""
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        
        query = GraphQuery(
            query_type="structural",
            zone_id=zone_id,
            max_results=limit,
        )
        
        result = _store().query(query)
        
        return jsonify({
            "ok": True,
            "zone_id": zone_id,
            "entities": [n.to_dict() for n in result.nodes if n.type == NodeType.ENTITY],
            "count": len(result.nodes),
        })
    except Exception as e:
        _LOGGER.exception("Failed to get entities for zone %s", zone_id)
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/mood/<path:mood>/patterns")
def kg_mood_patterns(mood: str):
    """Get patterns related to a mood."""
    try:
        min_confidence = float(request.args.get("min_confidence", 0.5))
        limit = min(int(request.args.get("limit", 10)), 50)
        
        query = GraphQuery(
            query_type="contextual",
            mood=mood,
            max_results=limit,
            min_confidence=min_confidence,
            include_evidence=True,
        )
        
        result = _store().query(query)
        
        return jsonify({
            "ok": True,
            "mood": mood,
            "patterns": [n.to_dict() for n in result.nodes if n.type == NodeType.PATTERN],
            "edges": [e.to_dict() for e in result.edges],
            "count": len(result.nodes),
        })
    except Exception as e:
        _LOGGER.exception("Failed to get patterns for mood %s", mood)
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/pattern/<path:pattern_id>")
def kg_get_pattern(pattern_id: str):
    """Get details about a specific pattern."""
    try:
        node = _store().get_node(pattern_id)
        if not node or node.type != NodeType.PATTERN:
            return jsonify({"ok": False, "error": "Pattern not found"}), 404
        
        # Get related edges
        edges = _store().get_edges_from(pattern_id)
        
        return jsonify({
            "ok": True,
            "pattern": node.to_dict(),
            "related": [e.to_dict() for e in edges],
        })
    except Exception as e:
        _LOGGER.exception("Failed to get pattern %s", pattern_id)
        return jsonify({"ok": False, "error": str(e)}), 500


# ==================== Import Operations ====================

@bp.post("/import/entities")
def kg_import_entities():
    """Import entities from Home Assistant states."""
    try:
        data = request.get_json() or {}
        states = data.get("states", [])
        area_registry = data.get("area_registry", {})
        entity_registry = data.get("entity_registry", {})
        
        builder = _builder()
        stats = builder.build_from_ha_states(states, area_registry, entity_registry)
        
        return jsonify({
            "ok": True,
            "imported": stats,
        })
    except Exception as e:
        _LOGGER.exception("Failed to import entities")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/import/patterns")
def kg_import_patterns():
    """Import patterns from Habitus miner output."""
    try:
        data = request.get_json() or {}
        rules = data.get("rules", [])
        min_confidence = data.get("min_confidence", 0.5)
        min_support = data.get("min_support", 5)
        min_lift = data.get("min_lift", 1.2)
        
        importer = _importer()
        stats = importer.import_from_habitus_rules(
            rules=rules,
            min_confidence=min_confidence,
            min_support=min_support,
            min_lift=min_lift,
        )
        
        return jsonify({
            "ok": True,
            "imported": stats,
        })
    except Exception as e:
        _LOGGER.exception("Failed to import patterns")
        return jsonify({"ok": False, "error": str(e)}), 500


# ==================== Entity Management ====================

@bp.post("/entities")
def kg_upsert_entity():
    """Create or update an entity with relationships."""
    try:
        data = request.get_json() or {}
        
        entity_id = data.get("entity_id")
        domain = data.get("domain")
        label = data.get("label")
        area_id = data.get("area_id")
        capabilities = data.get("capabilities", [])
        tags = data.get("tags", [])
        properties = data.get("properties", {})
        
        if not entity_id or not domain:
            return jsonify({
                "ok": False,
                "error": "Missing required fields: entity_id, domain",
            }), 400
        
        builder = _builder()
        node = builder.upsert_entity(
            entity_id=entity_id,
            domain=domain,
            label=label,
            area_id=area_id,
            capabilities=capabilities,
            tags=tags,
            properties=properties,
        )
        
        return jsonify({"ok": True, "entity": node.to_dict()})
    except Exception as e:
        _LOGGER.exception("Failed to upsert entity")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/moods")
def kg_upsert_mood():
    """Create or update a mood."""
    try:
        data = request.get_json() or {}
        
        mood = data.get("mood")
        label = data.get("label")
        properties = data.get("properties", {})
        
        if not mood:
            return jsonify({
                "ok": False,
                "error": "Missing required field: mood",
            }), 400
        
        builder = _builder()
        node = builder.upsert_mood(mood=mood, label=label, properties=properties)
        
        return jsonify({"ok": True, "mood": node.to_dict()})
    except Exception as e:
        _LOGGER.exception("Failed to upsert mood")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/zones")
def kg_upsert_zone():
    """Create or update a zone."""
    try:
        data = request.get_json() or {}
        
        zone_id = data.get("zone_id")
        label = data.get("label")
        area_ids = data.get("area_ids", [])
        properties = data.get("properties", {})
        
        if not zone_id:
            return jsonify({
                "ok": False,
                "error": "Missing required field: zone_id",
            }), 400
        
        builder = _builder()
        node = builder.upsert_zone(
            zone_id=zone_id,
            label=label,
            area_ids=area_ids,
            properties=properties,
        )
        
        return jsonify({"ok": True, "zone": node.to_dict()})
    except Exception as e:
        _LOGGER.exception("Failed to upsert zone")
        return jsonify({"ok": False, "error": str(e)}), 500


# ==================== Neo4j Integration ====================

@bp.get("/neo4j/visualize")
def kg_neo4j_visualize():
    """Export graph data for Neo4j visualization.
    
    Query params:
    - root: Optional root node ID for subgraph
    - max_nodes: Max nodes to return (default 500)
    - max_edges: Max edges to return (default 1000)
    - include_properties: Include node properties (default false)
    """
    if not NEO4J_AVAILABLE:
        return jsonify({
            "ok": False,
            "error": "Neo4j adapter not available",
            "neo4j_available": False,
        }), 503
    
    try:
        root = request.args.get("root")
        max_nodes = min(int(request.args.get("max_nodes", 500)), 1000)
        max_edges = min(int(request.args.get("max_edges", 1000)), 2000)
        include_properties = request.args.get("include_properties", "false").lower() == "true"
        
        adapter = get_neo4j_adapter()
        try:
            viz_data = adapter.export_visualization_data(
                root_node=root,
                max_nodes=max_nodes,
                max_edges=max_edges,
                include_properties=include_properties,
            )
            
            return jsonify({
                "ok": viz_data.get("success", False),
                "data": viz_data,
                "neo4j_available": True,
            })
        finally:
            adapter.disconnect()
            
    except Exception as e:
        _LOGGER.exception("Failed to export Neo4j visualization data")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/neo4j/stats")
def kg_neo4j_stats():
    """Get Neo4j graph statistics."""
    if not NEO4J_AVAILABLE:
        return jsonify({
            "ok": False,
            "error": "Neo4j adapter not available",
            "neo4j_available": False,
        }), 503
    
    try:
        adapter = get_neo4j_adapter()
        try:
            stats = adapter.get_graph_stats()
            
            return jsonify({
                "ok": stats.get("success", False),
                "stats": stats,
                "neo4j_available": True,
            })
        finally:
            adapter.disconnect()
            
    except Exception as e:
        _LOGGER.exception("Failed to get Neo4j stats")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/neo4j/central")
def kg_neo4j_central_nodes():
    """Get most central nodes in Neo4j graph.
    
    Query params:
    - top: Number of top nodes (default 10)
    """
    if not NEO4J_AVAILABLE:
        return jsonify({
            "ok": False,
            "error": "Neo4j adapter not available",
            "neo4j_available": False,
        }), 503
    
    try:
        top = min(int(request.args.get("top", 10)), 50)
        
        adapter = get_neo4j_adapter()
        try:
            result = adapter.find_central_nodes(top_k=top)
            
            return jsonify({
                "ok": result.success,
                "nodes": result.records,
                "count": len(result.records),
                "neo4j_available": True,
            })
        finally:
            adapter.disconnect()
            
    except Exception as e:
        _LOGGER.exception("Failed to get central nodes")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/neo4j/export")
def kg_neo4j_export():
    """Export Brain Graph to Neo4j.
    
    Expects JSON body with nodes and edges arrays.
    """
    if not NEO4J_AVAILABLE:
        return jsonify({
            "ok": False,
            "error": "Neo4j adapter not available",
            "neo4j_available": False,
        }), 503
    
    try:
        data = request.get_json() or {}
        nodes_data = data.get("nodes", [])
        edges_data = data.get("edges", [])
        
        # Convert from dict to Node/Edge objects
        from .models import Node, Edge
        
        nodes = [Node.from_dict(n) for n in nodes_data if isinstance(n, dict)]
        edges = [Edge.from_dict(e) for e in edges_data if isinstance(e, dict)]
        
        adapter = get_neo4j_adapter()
        try:
            stats = adapter.export_brain_graph(nodes, edges)
            
            return jsonify({
                "ok": len(stats.get("errors", [])) == 0,
                "stats": stats,
                "neo4j_available": True,
            })
        finally:
            adapter.disconnect()
            
    except Exception as e:
        _LOGGER.exception("Failed to export to Neo4j")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/neo4j/schema")
def kg_neo4j_schema():
    """Ensure Neo4j schema (constraints and indexes)."""
    if not NEO4J_AVAILABLE:
        return jsonify({
            "ok": False,
            "error": "Neo4j adapter not available",
            "neo4j_available": False,
        }), 503
    
    try:
        adapter = get_neo4j_adapter()
        try:
            result = adapter.ensure_schema()
            
            return jsonify({
                "ok": result.get("success", False),
                "schema": result,
                "neo4j_available": True,
            })
        finally:
            adapter.disconnect()
            
    except Exception as e:
        _LOGGER.exception("Failed to ensure Neo4j schema")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/neo4j/query")
def kg_neo4j_query():
    """Execute custom Cypher query (read-only).
    
    Query params:
    - cypher: Cypher query string
    - params: JSON-encoded parameters (optional)
    
    Only read-only queries are allowed for safety.
    """
    if not NEO4J_AVAILABLE:
        return jsonify({
            "ok": False,
            "error": "Neo4j adapter not available",
            "neo4j_available": False,
        }), 503
    
    try:
        cypher = request.args.get("cypher")
        if not cypher:
            return jsonify({
                "ok": False,
                "error": "Missing required parameter: cypher",
            }), 400
        
        # Validate query is read-only
        from .cypher_adapter import CypherValidator
        is_safe, warning = CypherValidator.is_safe(cypher)
        if not is_safe:
            return jsonify({
                "ok": False,
                "error": warning,
                "safety_check": "failed",
            }), 400
        
        # Parse optional parameters
        params = {}
        params_str = request.args.get("params")
        if params_str:
            import json
            params = json.loads(params_str)
        
        adapter = get_neo4j_adapter()
        try:
            from .neo4j_adapter import CypherQuery
            query = CypherQuery(query=cypher, parameters=params, read_only=True)
            result = adapter.execute(query)
            
            return jsonify({
                "ok": result.success,
                "records": result.records,
                "summary": result.summary,
                "execution_time_ms": result.execution_time_ms,
                "neo4j_available": True,
            })
        finally:
            adapter.disconnect()
            
    except Exception as e:
        _LOGGER.exception("Failed to execute Cypher query")
        return jsonify({"ok": False, "error": str(e)}), 500