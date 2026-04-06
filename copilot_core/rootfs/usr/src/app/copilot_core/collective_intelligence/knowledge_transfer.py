"""Knowledge Transfer Module for Cross-Home Learning."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import hashlib
import json
import time
import logging

from .models import KnowledgeItem


logger = logging.getLogger(__name__)


class KnowledgeTransfer:
    """
    Enables cross-home knowledge sharing while preserving privacy.

    Features:
    - Knowledge extraction from patterns
    - Privacy-preserving transfer
    - Knowledge validation
    - Transfer tracking
    """

    def __init__(self, min_confidence: float = 0.7,
                 max_transfer_rate: int = 10):
        """
        Initialize knowledge transfer module.

        Args:
            min_confidence: Minimum confidence for transferable knowledge
            max_transfer_rate: Maximum transfers per hour
        """
        self.min_confidence = min_confidence
        self.max_transfer_rate = max_transfer_rate
        self.knowledge_base: Dict[str, KnowledgeItem] = {}
        self.transfer_log: List[Dict[str, Any]] = []
        self.knowledge_types: Dict[str, List[str]] = {}  # type -> list of IDs

    def extract_knowledge(self, node_id: str, knowledge_type: str,
                         payload: Dict[str, Any],
                         confidence: float = 1.0) -> Optional[KnowledgeItem]:
        """
        Extract knowledge from a node's data.

        Args:
            node_id: Source node ID
            knowledge_type: Type of knowledge (e.g., "habitus_pattern")
            payload: The knowledge payload
            confidence: Confidence in the knowledge (0-1)

        Returns:
            KnowledgeItem if confident enough, None otherwise
        """
        if confidence < self.min_confidence:
            return None

        knowledge = KnowledgeItem(
            knowledge_id=hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest()[:16],
            source_node_id=node_id,
            knowledge_type=knowledge_type,
            payload=payload,
            confidence=confidence,
            timestamp=time.time()
        )

        # Check for duplicates
        if knowledge.knowledge_hash in self.knowledge_base:
            return None

        self.knowledge_base[knowledge.knowledge_hash] = knowledge

        # Update type index
        if knowledge_type not in self.knowledge_types:
            self.knowledge_types[knowledge_type] = []
        self.knowledge_types[knowledge_type].append(knowledge.knowledge_hash)

        return knowledge

    def transfer_knowledge(self, knowledge_id: str,
                          target_node_id: str) -> bool:
        """
        Transfer knowledge to another node.

        Args:
            knowledge_id: ID of knowledge to transfer
            target_node_id: Target node ID

        Returns:
            True if transfer successful
        """
        if knowledge_id not in self.knowledge_base:
            return False

        knowledge = self.knowledge_base[knowledge_id]

        # Log transfer
        self.transfer_log.append({
            "knowledge_id": knowledge_id,
            "source": knowledge.source_node_id,
            "target": target_node_id,
            "timestamp": time.time(),
            "type": knowledge.knowledge_type
        })

        # Check rate limit
        if self._exceeds_rate_limit(target_node_id):
            return False

        return True

    def _exceeds_rate_limit(self, node_id: str) -> bool:
        """Check if node exceeds transfer rate limit."""
        hour_ago = time.time() - 3600
        recent_transfers = [
            t for t in self.transfer_log
            if t["target"] == node_id and t["timestamp"] > hour_ago
        ]
        return len(recent_transfers) >= self.max_transfer_rate

    def get_knowledge_for_type(self, knowledge_type: str,
                              min_confidence: Optional[float] = None) -> List[KnowledgeItem]:
        """Get knowledge of a specific type."""
        if knowledge_type not in self.knowledge_types:
            return []

        knowledge_items = []
        for hash_id in self.knowledge_types[knowledge_type]:
            item = self.knowledge_base.get(hash_id)
            if item:
                if min_confidence is None or item.confidence >= min_confidence:
                    knowledge_items.append(item)

        return knowledge_items

    def get_recommended_transfers(self, node_id: str,
                                 target_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get knowledge recommendations for a node.

        Args:
            node_id: Node to recommend for
            target_types: Optional list of target knowledge types

        Returns:
            List of recommendations
        """
        recommendations = []

        for knowledge_id, knowledge in self.knowledge_base.items():
            if knowledge.source_node_id == node_id:
                continue

            if target_types and knowledge.knowledge_type not in target_types:
                continue

            recommendations.append({
                "knowledge_id": knowledge_id,
                "knowledge_type": knowledge.knowledge_type,
                "confidence": knowledge.confidence,
                "source": knowledge.source_node_id,
                "payload_summary": self._summarize_payload(knowledge.payload)
            })

        # Sort by confidence
        recommendations.sort(key=lambda x: x["confidence"], reverse=True)

        return recommendations

    def _summarize_payload(self, payload: Dict[str, Any], max_len: int = 100) -> str:
        """Create a summary of payload."""
        try:
            json_str = json.dumps(payload, sort_keys=True)
            if len(json_str) > max_len:
                return json_str[:max_len-3] + "..."
            return json_str
        except (TypeError, ValueError):
            # Fallback: simple string conversion
            return str(payload)[:max_len]

    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge transfer statistics."""
        stats = {
            "total_knowledge_items": len(self.knowledge_base),
            "total_transfers": len(self.transfer_log),
            "knowledge_types": {
                ktype: len(ids) for ktype, ids in self.knowledge_types.items()
            },
            "transfers_by_type": {},
            "transfers_by_target": {}
        }

        # Count by type
        for transfer in self.transfer_log:
            ktype = transfer["type"]
            stats["transfers_by_type"][ktype] = (
                stats["transfers_by_type"].get(ktype, 0) + 1
            )

            target = transfer["target"]
            stats["transfers_by_target"][target] = (
                stats["transfers_by_target"].get(target, 0) + 1
            )

        return stats

    def clear_knowledge(self, knowledge_id: str) -> bool:
        """Remove a specific knowledge item."""
        if knowledge_id not in self.knowledge_base:
            return False

        knowledge = self.knowledge_base.pop(knowledge_id)

        # Update type index
        if knowledge.knowledge_type in self.knowledge_types:
            self.knowledge_types[knowledge.knowledge_type].remove(knowledge_id)

        return True

    def clear_all(self):
        """Clear all knowledge and logs."""
        self.knowledge_base.clear()
        self.transfer_log.clear()
        self.knowledge_types.clear()


# Slice 70: Knowledge Transfer API Contract (P2-009)
# REST API endpoints for cross-home knowledge sharing

class KnowledgeTransferAPI:
    """API contract for Knowledge Transfer operations."""

    # ─── REST Endpoints ──────────────────────────────────────────────────────────
    #
    # GET    /api/v1/knowledge                          → list all knowledge items
    # GET    /api/v1/knowledge/{knowledge_id}            → get single item
    # POST   /api/v1/knowledge                          → extract new knowledge
    # POST   /api/v1/knowledge/{knowledge_id}/transfer   → transfer to target
    # DELETE /api/v1/knowledge/{knowledge_id}           → delete knowledge
    #
    # GET    /api/v1/knowledge/types                    → list knowledge types
    # GET    /api/v1/knowledge/types/{type}             → list items by type
    #
    # GET    /api/v1/knowledge/transfer-log             → get transfer history
    #
    # ─── API Contract ───────────────────────────────────────────────────────────
    #
    # POST /api/v1/knowledge
    # Body: { node_id, knowledge_type, payload, confidence }
    # Response 201: { knowledge_id, hash, created_at }
    #
    # POST /api/v1/knowledge/{knowledge_id}/transfer
    # Body: { target_node_id }
    # Response 200: { success, knowledge_id, target_node_id, transferred_at }
    # Response 404: { error: "Knowledge not found" }
    # Response 429: { error: "Rate limit exceeded" }
    #
    # GET /api/v1/knowledge
    # Query: ?type=&min_confidence=&limit=&offset=
    # Response 200: { items: [...], total, limit, offset }
    #
    # DELETE /api/v1/knowledge/{knowledge_id}
    # Response 200: { success: true }
    # Response 404: { error: "Knowledge not found" }

    @staticmethod
    def validate_knowledge_payload(payload: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate POST payload. Returns (valid, error_message)."""
        if not isinstance(payload.get("node_id"), str):
            return False, "node_id must be string"
        if not isinstance(payload.get("knowledge_type"), str):
            return False, "knowledge_type must be string"
        if not isinstance(payload.get("payload"), dict):
            return False, "payload must be dict"
        conf = payload.get("confidence", 1.0)
        if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
            return False, "confidence must be in [0.0, 1.0]"
        return True, None

    @staticmethod
    def validate_transfer_payload(payload: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate transfer POST payload."""
        if not isinstance(payload.get("target_node_id"), str):
            return False, "target_node_id must be string"
        if not payload["target_node_id"].strip():
            return False, "target_node_id cannot be empty"
        return True, None

    @staticmethod
    def format_knowledge_response(item: "KnowledgeItem") -> Dict[str, Any]:
        """Format a KnowledgeItem for API response."""
        return {
            "knowledge_id": item.knowledge_hash,
            "source_node_id": item.source_node_id,
            "knowledge_type": item.knowledge_type,
            "confidence": item.confidence,
            "timestamp": item.timestamp,
            "payload": item.payload,
        }

    @staticmethod
    def format_transfer_log_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Format a transfer log entry for API response."""
        return {
            "knowledge_id": entry.get("knowledge_id"),
            "source_node_id": entry.get("source_node_id"),
            "target_node_id": entry.get("target_node_id"),
            "transferred_at": entry.get("transferred_at"),
            "success": entry.get("success"),
        }
