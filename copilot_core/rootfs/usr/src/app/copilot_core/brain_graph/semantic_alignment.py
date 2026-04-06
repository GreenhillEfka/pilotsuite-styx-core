"""Brain Graph Semantic Alignment (Slice 146).

Aligns discovered entities with brain graph nodes for automatic relationship creation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher

from copilot_core.brain_graph.model import GraphNode, NodeKind
from copilot_core.brain_graph.service import BrainGraphService

_LOGGER = logging.getLogger(__name__)


class SemanticAligner:
    """Aligns HA entities with Brain Graph nodes."""
    
    def __init__(self, service: Optional[BrainGraphService] = None):
        self._service = service or BrainGraphService()
        self._similarity_threshold = 0.7
    
    def _calculate_similarity(self, entity_id: str, node_label: str) -> float:
        """Calculate string similarity between entity_id and node_label."""
        entity_name = entity_id.split(".")[-1].replace("_", " ")
        return SequenceMatcher(None, entity_name.lower(), node_label.lower()).ratio()
    
    def _normalize_entity_name(self, entity_id: str) -> str:
        """Normalize entity ID to a name for matching."""
        name = entity_id.split(".")[-1]
        name = name.replace("_", " ").replace("-", " ")
        return name.lower()
    
    def _extract_semantic_features(self, entity: Dict[str, Any]) -> Dict[str, str]:
        """Extract semantic features from HA entity."""
        domain = entity.get("entity_id", "").split(".")[0]
        attrs = entity.get("attributes", {})
        
        return {
            "domain": domain,
            "device_class": attrs.get("device_class", "unknown"),
            "friendly_name": attrs.get("friendly_name", ""),
            "area": attrs.get("area_id", ""),
        }
    
    def find_alignments(
        self,
        entities: List[Dict[str, Any]],
        node_types: List[str] = None
    ) -> List[Tuple[str, str, float]]]:
        """
        Find potential alignments between entities and graph nodes.
        
        Returns: List of (entity_id, node_id, similarity_score) tuples
        """
        if node_types is None:
            node_types = ["device", "sensor", "zone"]
        
        alignments = []
        nodes = self._service.get_nodes_by_type(node_types)
        
        for entity in entities:
            entity_id = entity.get("entity_id", "")
            entity_features = self._extract_semantic_features(entity)
            
            for node in nodes:
                similarity = self._calculate_similarity(entity_id, node.label)
                
                # Boost score based on domain matching
                if entity_features["domain"] in node.label.lower():
                    similarity += 0.1
                
                if similarity >= self._similarity_threshold:
                    alignments.append((entity_id, node.node_id, similarity))
        
        # Sort by similarity descending
        alignments.sort(key=lambda x: x[2], reverse=True)
        return alignments
    
    def auto_align(self, entities: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
        """Automatically create edges between aligned entities and nodes."""
        alignments = self.find_alignments(entities)
        
        results = {
            "created_edges": 0,
            "alignments_found": len(alignments),
            "edges": [],
        }
        
        for entity_id, node_id, score in alignments:
            if not dry_run:
                try:
                    self._service.add_edge(
                        source_id=entity_id,
                        target_id=node_id,
                        edge_type="represents",
                        weight=score,
                        attributes={"auto_aligned": True, "confidence": score}
                    )
                    results["created_edges"] += 1
                    results["edges"].append({
                        "entity_id": entity_id,
                        "node_id": node_id,
                        "confidence": score,
                    })
                except Exception as exc:
                    _LOGGER.error("Failed to create edge %s -> %s: %s", entity_id, node_id, exc)
        
        return results
