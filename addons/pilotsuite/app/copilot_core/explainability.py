"""
Explainability Engine -- Explain why Styx suggests something.

Traverses the Brain Graph to find causal chains and generates
natural language explanations for suggestions.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_CHAIN_DEPTH = 5


class ExplainabilityEngine:
    """Generate human-readable explanations for suggestions.

    Uses the Brain Graph to trace causal chains from trigger entities
    to suggestion targets, then renders a natural-language summary.
    """

    def __init__(
        self,
        brain_graph_service=None,
        llm_provider=None,
    ):
        self._graph = brain_graph_service
        self._llm = llm_provider
        self._lock = threading.Lock()
        logger.info("ExplainabilityEngine initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def explain_suggestion(
        self, suggestion_id: str, suggestion_data: dict
    ) -> dict:
        """Build a full explanation for a suggestion.

        Parameters
        ----------
        suggestion_id : str
            Unique suggestion / candidate id.
        suggestion_data : dict
            Must contain at least ``source_entity`` and ``target_entity``.

        Returns
        -------
        dict with keys: suggestion_id, chain, evidence, confidence,
        human_text, factors.
        """
        source = suggestion_data.get("source_entity", "")
        target = suggestion_data.get("target_entity", "")

        chain = self._build_causal_chain(source, target)
        evidence = self._gather_evidence(chain, suggestion_data)
        confidence = self._calculate_confidence(chain)
        factors = self._extract_factors(chain, evidence)
        human_text = self._generate_human_text(chain, evidence)

        return {
            "suggestion_id": suggestion_id,
            "chain": chain,
            "evidence": evidence,
            "confidence": round(confidence, 4),
            "human_text": human_text,
            "factors": factors,
        }

    # ------------------------------------------------------------------
    # Causal chain
    # ------------------------------------------------------------------

    def _build_causal_chain(
        self, from_entity: str, to_entity: str
    ) -> List[Dict[str, Any]]:
        """BFS traversal of Brain Graph edges from *from_entity* to *to_entity*.

        Returns a list of dicts, each representing one hop:
        ``{"from": ..., "to": ..., "edge_type": ..., "weight": ...}``
        """
        if not self._graph or not from_entity or not to_entity:
            return []

        with self._lock:
            store = self._graph.store

            visited: set[str] = set()
            queue: deque[tuple[str, list]] = deque()
            queue.append((from_entity, []))

            while queue:
                current, path = queue.popleft()

                if len(path) >= MAX_CHAIN_DEPTH:
                    continue
                if current in visited:
                    continue
                visited.add(current)

                edges = store.get_edges(from_node=current)
                for edge in edges:
                    hop = {
                        "from": edge.from_node,
                        "to": edge.to_node,
                        "edge_type": str(edge.edge_type),
                        "weight": round(edge.weight, 4),
                    }
                    new_path = path + [hop]

                    if edge.to_node == to_entity:
                        return new_path

                    queue.append((edge.to_node, new_path))

        return []

    # ------------------------------------------------------------------
    # Evidence & confidence
    # ------------------------------------------------------------------

    def _gather_evidence(
        self, chain: list, suggestion_data: dict
    ) -> Dict[str, Any]:
        """Aggregate numeric evidence from chain edges and suggestion data."""
        if not chain:
            return {
                "edge_weights": [],
                "node_scores": [],
                "temporal_patterns": [],
            }

        edge_weights = [hop["weight"] for hop in chain]
        node_scores: list[float] = []
        temporal_patterns: list[str] = []

        if self._graph:
            store = self._graph.store
            seen: set[str] = set()
            for hop in chain:
                for nid in (hop["from"], hop["to"]):
                    if nid in seen:
                        continue
                    seen.add(nid)
                    node = store.get_node(nid)
                    if node:
                        node_scores.append(round(node.score, 4))

        # Simple temporal hint from suggestion metadata
        if suggestion_data.get("time_pattern"):
            temporal_patterns.append(suggestion_data["time_pattern"])

        return {
            "edge_weights": edge_weights,
            "node_scores": node_scores,
            "temporal_patterns": temporal_patterns,
        }

    def _calculate_confidence(self, chain: List[dict]) -> float:
        """Confidence = product of normalised edge weights along the chain.

        Clamped to [0.0, 1.0].  An empty chain yields 0.0.
        """
        if not chain:
            return 0.0

        product = 1.0
        for hop in chain:
            w = min(hop["weight"], 1.0)
            product *= w

        # Penalise longer chains slightly
        depth_penalty = 1.0 / (1.0 + 0.1 * len(chain))
        return max(0.0, min(1.0, product * depth_penalty))

    # ------------------------------------------------------------------
    # Human-readable text
    # ------------------------------------------------------------------

    def _generate_human_text(self, chain: list, evidence: dict) -> str:
        """Build a template-based natural-language explanation."""
        if not chain:
            return "No causal chain found for this suggestion."

        parts: list[str] = []
        for i, hop in enumerate(chain):
            if i == 0:
                parts.append(
                    f"It starts with {hop['from']}, which is connected "
                    f"to {hop['to']} via '{hop['edge_type']}' "
                    f"(strength {hop['weight']:.2f})."
                )
            else:
                parts.append(
                    f"Then {hop['from']} links to {hop['to']} "
                    f"via '{hop['edge_type']}' (strength {hop['weight']:.2f})."
                )

        weights = evidence.get("edge_weights", [])
        if weights:
            avg_w = sum(weights) / len(weights)
            parts.append(
                f"Overall, the chain has {len(chain)} hop(s) with an "
                f"average edge strength of {avg_w:.2f}."
            )

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Factor extraction
    # ------------------------------------------------------------------

    def _extract_factors(
        self, chain: list, evidence: dict
    ) -> List[Dict[str, Any]]:
        """Return a list of contributing factors for the UI."""
        factors: list[dict] = []

        for hop in chain:
            factors.append(
                {
                    "type": "edge",
                    "description": (
                        f"{hop['from']} -> {hop['to']} ({hop['edge_type']})"
                    ),
                    "weight": hop["weight"],
                }
            )

        for score in evidence.get("node_scores", []):
            factors.append(
                {"type": "node_score", "description": "Node salience", "weight": score}
            )

        for tp in evidence.get("temporal_patterns", []):
            factors.append(
                {"type": "temporal", "description": tp, "weight": 1.0}
            )

        return factors
