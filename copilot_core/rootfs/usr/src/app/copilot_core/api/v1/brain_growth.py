"""Brain Growth API — Inspectable semantic transfer and brain activity monitoring.

Slice 5: Brain Growth Unification

Endpoints:
  GET /api/v1/brain/growth/summary          - Brain activity and growth summary
  GET /api/v1/brain/growth/trace/<input_id> - Semantic transfer trace for specific input
  GET /api/v1/brain/growth/zone-links       - Zone-to-brain linkage mapping
  GET /api/v1/brain/growth/activity         - Recent brain activity timeline
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify

from copilot_core.api.security import require_token
from copilot_core.brain_graph.brain_growth_read_model import (
    BrainGrowthReadModel,
    BrainGrowthSummary,
    SemanticTransferTrace,
    ZoneBrainLink,
    build_brain_growth_read_model,
)

logger = logging.getLogger(__name__)

brain_growth_bp = Blueprint("brain_growth", __name__, url_prefix="/api/v1/brain/growth")

# Service references
_read_model: Optional[BrainGrowthReadModel] = None


def init_brain_growth_api(
    graph_service: Optional[Any] = None,
    neuron_manager: Optional[Any] = None,
    zone_truth: Optional[Any] = None,
    event_processor: Optional[Any] = None,
) -> None:
    """Initialize Brain Growth API with service references."""
    global _read_model
    _read_model = build_brain_growth_read_model(
        graph_service=graph_service,
        neuron_manager=neuron_manager,
        zone_truth=zone_truth,
        event_processor=event_processor,
    )
    logger.info("Brain Growth API initialized")


def _summary_to_dict(summary: BrainGrowthSummary) -> Dict[str, Any]:
    """Convert BrainGrowthSummary to JSON-serializable dict."""
    return {
        "total_nodes": summary.total_nodes,
        "total_edges": summary.total_edges,
        "nodes_added_last_hour": summary.nodes_added_last_hour,
        "edges_added_last_hour": summary.edges_added_last_hour,
        "growth_rate_nodes_per_hour": summary.growth_rate_nodes_per_hour,
        "growth_rate_edges_per_hour": summary.growth_rate_edges_per_hour,
        "last_input_timestamp": summary.last_input_timestamp,
        "brain_freshness_score": summary.brain_freshness_score,
        "active_zone_count": summary.active_zone_count,
        "module_context_count": summary.module_context_count,
    }


def _trace_to_dict(trace: SemanticTransferTrace) -> Dict[str, Any]:
    """Convert SemanticTransferTrace to JSON-serializable dict."""
    return {
        "input_id": trace.input_id,
        "input_type": trace.input_type,
        "input_timestamp": trace.input_timestamp,
        "graph_updates": trace.graph_updates,
        "neuron_updates": trace.neuron_updates,
        "module_context_updates": trace.module_context_updates,
        "propagation_depth": trace.propagation_depth,
        "confidence_score": trace.confidence_score,
    }


def _zone_link_to_dict(link: ZoneBrainLink) -> Dict[str, Any]:
    """Convert ZoneBrainLink to JSON-serializable dict."""
    return {
        "zone_id": link.zone_id,
        "zone_name": link.zone_name,
        "entity_count": link.entity_count,
        "brain_node_count": link.brain_node_count,
        "brain_edge_count": link.brain_edge_count,
        "context_neuron_ids": link.context_neuron_ids,
        "state_neuron_ids": link.state_neuron_ids,
        "mood_neuron_ids": link.mood_neuron_ids,
        "last_activity_timestamp": link.last_activity_timestamp,
        "activity_score": link.activity_score,
    }


@brain_growth_bp.route("/summary", methods=["GET"])
@require_token
def get_brain_growth_summary() -> tuple:
    """Get high-level summary of brain activity and growth.
    
    Returns:
        JSON with brain statistics:
        - total_nodes, total_edges: Graph size
        - nodes_added_last_hour, edges_added_last_hour: Recent growth
        - growth_rate_nodes_per_hour, growth_rate_edges_per_hour: Growth rates
        - last_input_timestamp: Most recent input
        - brain_freshness_score: 0.0-1.0 freshness metric
        - active_zone_count: Zones with recent activity
        - module_context_count: Module-derived contexts
    """
    if not _read_model:
        return jsonify({"error": "Brain Growth API not initialized"}), 503
    
    try:
        summary = _read_model.get_brain_growth_summary()
        return jsonify(_summary_to_dict(summary)), 200
    except Exception as exc:
        logger.exception("Failed to get brain growth summary")
        return jsonify({"error": str(exc)}), 500


@brain_growth_bp.route("/trace/<input_id>", methods=["GET"])
@require_token
def get_semantic_transfer_trace(input_id: str) -> tuple:
    """Get trace of how a specific input triggered brain updates.
    
    Args:
        input_id: Identifier of the triggering input (event/entity/sensor)
    
    Returns:
        JSON with trace data:
        - input_id, input_type, input_timestamp: Input details
        - graph_updates: List of graph node/edge updates
        - neuron_updates: List of neuron state updates
        - module_context_updates: List of module context updates
        - propagation_depth: How many hops the influence propagated
        - confidence_score: 0.0-1.0 confidence in the transfer chain
    """
    if not _read_model:
        return jsonify({"error": "Brain Growth API not initialized"}), 503
    
    try:
        trace = _read_model.get_semantic_transfer_trace(input_id)
        if not trace:
            return jsonify({"error": f"No trace found for input {input_id}"}), 404
        return jsonify(_trace_to_dict(trace)), 200
    except Exception as exc:
        logger.exception("Failed to get semantic transfer trace for %s", input_id)
        return jsonify({"error": str(exc)}), 500


@brain_growth_bp.route("/zone-links", methods=["GET"])
@require_token
def get_zone_brain_links() -> tuple:
    """Get linkage between zones and their brain representations.
    
    Returns:
        JSON array of zone links:
        - zone_id, zone_name: Zone identifiers
        - entity_count: Entities mapped to zone
        - brain_node_count, brain_edge_count: Brain graph stats
        - context_neuron_ids, state_neuron_ids, mood_neuron_ids: Neuron mappings
        - last_activity_timestamp: Most recent zone activity
        - activity_score: 0.0-1.0 activity level
    """
    if not _read_model:
        return jsonify({"error": "Brain Growth API not initialized"}), 503
    
    try:
        links = _read_model.get_zone_brain_links()
        return jsonify([_zone_link_to_dict(link) for link in links]), 200
    except Exception as exc:
        logger.exception("Failed to get zone brain links")
        return jsonify({"error": str(exc)}), 500


@brain_growth_bp.route("/activity", methods=["GET"])
@require_token
def get_brain_activity_timeline() -> tuple:
    """Get recent brain activity timeline.
    
    Query params:
        limit: Max entries to return (default: 50)
    
    Returns:
        JSON array of recent semantic transfer traces
    """
    if not _read_model:
        return jsonify({"error": "Brain Growth API not initialized"}), 503
    
    try:
        limit = int(request.args.get("limit", 50))
        # Access internal trace log (would need to be exposed in read model)
        # For now, return empty array - implementation detail
        return jsonify([]), 200
    except Exception as exc:
        logger.exception("Failed to get brain activity timeline")
        return jsonify({"error": str(exc)}), 500
