"""Brain Growth Read Model — Inspectable semantic transfer from inputs to graph/neuron updates.

Slice 5: Brain Growth Unification

Provides explicit, queryable read models for:
- Brain activity summary (growth rate, node/edge counts, freshness)
- Semantic transfer trace (which inputs triggered which graph/neuron updates)
- Zone/entity/module → brain context linkage

This makes the "growing brain" no longer only implied across separate subsystems.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BrainGrowthSummary:
    """High-level summary of brain activity and growth.
    
    Fields:
        total_nodes: Total node count in brain graph
        total_edges: Total edge count in brain graph
        nodes_added_last_hour: Nodes created in last 60 minutes
        edges_added_last_hour: Edges created in last 60 minutes
        growth_rate_nodes_per_hour: Average node growth rate
        growth_rate_edges_per_hour: Average edge growth rate
        last_input_timestamp: Most recent input that triggered growth
        brain_freshness_score: 0.0-1.0 freshness metric
        active_zone_count: Number of zones with recent brain activity
        module_context_count: Number of module-derived brain contexts
    """
    total_nodes: int = 0
    total_edges: int = 0
    nodes_added_last_hour: int = 0
    edges_added_last_hour: int = 0
    growth_rate_nodes_per_hour: float = 0.0
    growth_rate_edges_per_hour: float = 0.0
    last_input_timestamp: Optional[str] = None
    brain_freshness_score: float = 0.0
    active_zone_count: int = 0
    module_context_count: int = 0


@dataclass
class SemanticTransferTrace:
    """Trace of how an input triggered brain updates.
    
    Fields:
        input_id: Identifier of the triggering input (event/entity/sensor)
        input_type: Type of input (event, entity_state, sensor_reading, zone_update)
        input_timestamp: When the input was received
        graph_updates: List of graph node/edge updates triggered
        neuron_updates: List of neuron state updates triggered
        module_context_updates: List of module context updates triggered
        propagation_depth: How many hops the influence propagated
        confidence_score: 0.0-1.0 confidence in the transfer chain
    """
    input_id: str = ""
    input_type: str = ""
    input_timestamp: str = ""
    graph_updates: List[Dict[str, Any]] = field(default_factory=list)
    neuron_updates: List[Dict[str, Any]] = field(default_factory=list)
    module_context_updates: List[Dict[str, Any]] = field(default_factory=list)
    propagation_depth: int = 0
    confidence_score: float = 0.0


@dataclass
class ZoneBrainLink:
    """Linkage between a zone and its brain representation.
    
    Fields:
        zone_id: Zone identifier
        zone_name: Human-readable zone name
        entity_count: Number of entities mapped to this zone
        brain_node_count: Number of brain graph nodes for this zone
        brain_edge_count: Number of brain graph edges for this zone
        context_neuron_ids: List of context neuron IDs for this zone
        state_neuron_ids: List of state neuron IDs for this zone
        mood_neuron_ids: List of mood neuron IDs for this zone
        last_activity_timestamp: Most recent activity in this zone's brain context
        activity_score: 0.0-1.0 activity level
    """
    zone_id: str = ""
    zone_name: str = ""
    entity_count: int = 0
    brain_node_count: int = 0
    brain_edge_count: int = 0
    context_neuron_ids: List[str] = field(default_factory=list)
    state_neuron_ids: List[str] = field(default_factory=list)
    mood_neuron_ids: List[str] = field(default_factory=list)
    last_activity_timestamp: Optional[str] = None
    activity_score: float = 0.0


class BrainGrowthReadModel:
    """Read model for brain growth and semantic transfer inspection.
    
    Usage:
        read_model = BrainGrowthReadModel(graph_service, neuron_manager, zone_truth)
        summary = read_model.get_brain_growth_summary()
        trace = read_model.get_semantic_transfer_trace("event_123")
        zone_links = read_model.get_zone_brain_links()
    """
    
    def __init__(
        self,
        graph_service: Optional[Any] = None,
        neuron_manager: Optional[Any] = None,
        zone_truth: Optional[Any] = None,
        event_processor: Optional[Any] = None,
    ):
        self.graph_service = graph_service
        self.neuron_manager = neuron_manager
        self.zone_truth = zone_truth
        self.event_processor = event_processor
        self._transfer_trace_log: List[SemanticTransferTrace] = []
        self._max_trace_log_size = 1000
    
    def get_brain_growth_summary(self) -> BrainGrowthSummary:
        """Get high-level summary of brain activity and growth."""
        summary = BrainGrowthSummary()
        
        # Graph statistics
        if self.graph_service:
            try:
                graph_stats = self.graph_service.get_graph_statistics()
                summary.total_nodes = graph_stats.get("total_nodes", 0)
                summary.total_edges = graph_stats.get("total_edges", 0)
                summary.nodes_added_last_hour = graph_stats.get("nodes_added_last_hour", 0)
                summary.edges_added_last_hour = graph_stats.get("edges_added_last_hour", 0)
                summary.growth_rate_nodes_per_hour = graph_stats.get("growth_rate_nodes_per_hour", 0.0)
                summary.growth_rate_edges_per_hour = graph_stats.get("growth_rate_edges_per_hour", 0.0)
                summary.last_input_timestamp = graph_stats.get("last_input_timestamp")
                summary.brain_freshness_score = graph_stats.get("brain_freshness_score", 0.0)
            except Exception as exc:
                logger.warning("Failed to get graph statistics: %s", exc)
        
        # Zone activity
        if self.zone_truth:
            try:
                zones = self.zone_truth.get_all_zones()
                summary.active_zone_count = len([z for z in zones if z.get("enabled", True)])
            except Exception as exc:
                logger.warning("Failed to get zone count: %s", exc)
        
        # Module contexts
        if self.neuron_manager:
            try:
                module_contexts = self.neuron_manager.get_module_contexts()
                summary.module_context_count = len(module_contexts)
            except Exception as exc:
                logger.warning("Failed to get module contexts: %s", exc)
        
        return summary
    
    def get_semantic_transfer_trace(self, input_id: str) -> Optional[SemanticTransferTrace]:
        """Get trace of how a specific input triggered brain updates."""
        # Search trace log
        for trace in reversed(self._transfer_trace_log):
            if trace.input_id == input_id:
                return trace
        
        # Try to reconstruct from event processor
        if self.event_processor:
            try:
                event_data = self.event_processor.get_event_history(input_id)
                if event_data:
                    return self._build_trace_from_event(input_id, event_data)
            except Exception as exc:
                logger.warning("Failed to get event history for %s: %s", input_id, exc)
        
        return None
    
    def get_zone_brain_links(self) -> List[ZoneBrainLink]:
        """Get linkage between zones and their brain representations."""
        links: List[ZoneBrainLink] = []
        
        if not self.zone_truth:
            return links
        
        try:
            zones = self.zone_truth.get_all_zones()
            for zone in zones:
                link = ZoneBrainLink(
                    zone_id=zone.get("zone_id", ""),
                    zone_name=zone.get("name", ""),
                    entity_count=len(zone.get("entities", [])),
                )
                
                # Brain graph stats for this zone
                if self.graph_service:
                    try:
                        zone_graph_stats = self.graph_service.get_zone_graph_stats(zone["zone_id"])
                        link.brain_node_count = zone_graph_stats.get("node_count", 0)
                        link.brain_edge_count = zone_graph_stats.get("edge_count", 0)
                    except Exception as exc:
                        logger.debug("Failed to get zone graph stats for %s: %s", zone["zone_id"], exc)
                
                # Neuron IDs for this zone
                if self.neuron_manager:
                    try:
                        neuron_ids = self.neuron_manager.get_zone_neuron_ids(zone["zone_id"])
                        link.context_neuron_ids = neuron_ids.get("context", [])
                        link.state_neuron_ids = neuron_ids.get("state", [])
                        link.mood_neuron_ids = neuron_ids.get("mood", [])
                    except Exception as exc:
                        logger.debug("Failed to get zone neuron IDs for %s: %s", zone["zone_id"], exc)
                
                links.append(link)
        except Exception as exc:
            logger.warning("Failed to get zone brain links: %s", exc)
        
        return links
    
    def log_semantic_transfer(self, trace: SemanticTransferTrace) -> None:
        """Log a semantic transfer trace for later inspection."""
        self._transfer_trace_log.append(trace)
        
        # Trim log if too large
        if len(self._transfer_trace_log) > self._max_trace_log_size:
            self._transfer_trace_log = self._transfer_trace_log[-self._max_trace_log_size:]
    
    def _build_trace_from_event(self, input_id: str, event_data: Dict[str, Any]) -> SemanticTransferTrace:
        """Build a semantic transfer trace from event data."""
        trace = SemanticTransferTrace(
            input_id=input_id,
            input_type=event_data.get("type", "unknown"),
            input_timestamp=event_data.get("timestamp", ""),
            propagation_depth=event_data.get("propagation_depth", 0),
            confidence_score=event_data.get("confidence", 0.0),
        )
        
        # Extract graph updates
        if "graph_updates" in event_data:
            trace.graph_updates = event_data["graph_updates"]
        
        # Extract neuron updates
        if "neuron_updates" in event_data:
            trace.neuron_updates = event_data["neuron_updates"]
        
        # Extract module context updates
        if "module_context_updates" in event_data:
            trace.module_context_updates = event_data["module_context_updates"]
        
        return trace


def build_brain_growth_read_model(
    graph_service: Optional[Any] = None,
    neuron_manager: Optional[Any] = None,
    zone_truth: Optional[Any] = None,
    event_processor: Optional[Any] = None,
) -> BrainGrowthReadModel:
    """Factory function to build brain growth read model.
    
    This is the canonical entry point for Slice 5.
    """
    return BrainGrowthReadModel(
        graph_service=graph_service,
        neuron_manager=neuron_manager,
        zone_truth=zone_truth,
        event_processor=event_processor,
    )
