"""
Habitus Miner - Discover A→B patterns from brain graph temporal sequences.

This module implements the core pattern discovery algorithm:
1. Analyze time-ordered sequences of actions/states in brain graph
2. Apply delta-time windows to find potential correlations  
3. Calculate statistical evidence (support/confidence/lift)
4. Filter patterns with debounce logic to reduce noise

Based on association rule mining but adapted for home automation scenarios.
"""
import time
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict, Counter

from ..brain_graph.service import BrainGraphService
from ..brain_graph.model import GraphEdge, EdgeType

logger = logging.getLogger(__name__)


@dataclass
class PatternEvidence:
    """Statistical evidence for an A→B automation pattern."""
    support: float      # P(A ∩ B) - how often A and B occur together
    confidence: float   # P(B|A) - how often B follows A
    lift: float         # P(B|A) / P(B) - how much A increases likelihood of B
    count: int          # Number of times pattern was observed
    total_sessions: int # Total observation sessions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable format."""
        return {
            "support": round(self.support, 3),
            "confidence": round(self.confidence, 3), 
            "lift": round(self.lift, 3),
            "count": self.count,
            "total_sessions": self.total_sessions
        }


class HabitusMiner:
    """Core pattern discovery engine."""
    
    def __init__(self, 
                 brain_service: BrainGraphService,
                 min_confidence: float = 0.6,
                 min_support: float = 0.1,
                 min_lift: float = 1.2,
                 delta_window_minutes: int = 15,
                 debounce_minutes: int = 5):
        """
        Initialize the habitus miner.
        
        Args:
            brain_service: Brain graph service for data access
            min_confidence: Minimum confidence threshold for patterns
            min_support: Minimum support threshold for patterns  
            min_lift: Minimum lift threshold for patterns
            delta_window_minutes: Time window to consider A→B sequences
            debounce_minutes: Minimum gap between same action to count as separate
        """
        self.brain_service = brain_service
        self.min_confidence = min_confidence
        self.min_support = min_support
        self.min_lift = min_lift
        self.delta_window_ms = delta_window_minutes * 60 * 1000
        self.debounce_ms = debounce_minutes * 60 * 1000
        
    def mine_patterns(
        self, 
        lookback_hours: int = 72,
        zone: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Mine A→B automation patterns from recent brain graph activity.
        
        Args:
            lookback_hours: How far back to analyze (default 72h)
            zone: Optional zone ID to filter patterns (e.g., "kitchen" or "zone:kitchen")
                  When specified, only patterns where both antecedent and consequent
                  entities belong to this zone will be mined.
            
        Returns:
            Dict mapping pattern_id to pattern details with evidence
        """
        logger.info(f"Starting habitus mining with {lookback_hours}h lookback, zone={zone}")
        
        # Extract action sequences from brain graph
        sequences = self._extract_action_sequences(lookback_hours, zone=zone)
        
        if not sequences:
            logger.info("No action sequences found for pattern mining")
            if zone:
                logger.info(f"Zone '{zone}' may have no activity or does not exist")
            return {}
            
        logger.info(f"Extracted {len(sequences)} action sequences")
        
        # Discover A→B patterns with temporal correlation
        patterns = self._discover_patterns(sequences)
        
        # Calculate statistical evidence for each pattern
        evidence_patterns = {}
        for pattern_id, pattern_data in patterns.items():
            evidence = self._calculate_evidence(pattern_data, sequences)
            
            # Filter by thresholds
            if (evidence.confidence >= self.min_confidence and 
                evidence.support >= self.min_support and
                evidence.lift >= self.min_lift):
                
                evidence_patterns[pattern_id] = {
                    "pattern_id": pattern_id,
                    "antecedent": pattern_data["antecedent"],
                    "consequent": pattern_data["consequent"],
                    "evidence": evidence.to_dict(),
                    "discovered_at": int(time.time() * 1000)
                }
                
        logger.info(f"Found {len(evidence_patterns)} qualifying patterns")
        return evidence_patterns
        
    def _extract_action_sequences(
        self, 
        lookback_hours: int,
        zone: Optional[str] = None
    ) -> List[List[Dict[str, Any]]]:
        """Extract time-ordered action sequences from brain graph.
        
        Args:
            lookback_hours: Time window for extraction
            zone: Optional zone ID to filter entities (e.g., "kitchen" or "zone:kitchen")
                  When specified, only entities belonging to this zone are included.
        """
        cutoff_ms = int((time.time() - lookback_hours * 3600) * 1000)
        
        # Get all service call edges (intentional actions) within time window
        all_edges = self.brain_service.store.get_edges()
        service_edges = [
            edge for edge in all_edges 
            if (edge.edge_type == "affects" and 
                edge.from_node.startswith("ha.service:") and
                edge.updated_at_ms >= cutoff_ms)
        ]
        
        if not service_edges:
            return []
        
        # Zone filtering: get entities in the specified zone
        zone_entities: Set[str] = set()
        if zone:
            zone_id = zone if zone.startswith("zone:") else f"zone:{zone}"
            zone_info = self.brain_service.get_zone_entities(zone_id)
            if "error" not in zone_info:
                for entity in zone_info.get("entities", []):
                    zone_entities.add(f"ha.entity:{entity['id']}")
                logger.info(f"Zone filtering: found {len(zone_entities)} entities in zone '{zone}'")
            else:
                logger.warning(f"Zone '{zone}' not found: {zone_info.get('error')}")
        
        # If zone filtering is active, filter out entities not in zone
        if zone and zone_entities:
            original_count = len(service_edges)
            service_edges = [e for e in service_edges if e.to_node in zone_entities]
            logger.info(f"Filtered {original_count - len(service_edges)} edges outside zone")
        
        if not service_edges:
            return []
            
        # Sort by timestamp to create temporal sequences
        service_edges.sort(key=lambda e: e.updated_at_ms)
        
        # Group into sessions using debounce logic
        sessions = []
        current_session = []
        last_timestamp = 0
        
        for edge in service_edges:
            # If gap is larger than debounce, start new session
            if edge.updated_at_ms - last_timestamp > self.debounce_ms:
                if current_session:
                    sessions.append(current_session)
                current_session = []
                
            current_session.append({
                "timestamp": edge.updated_at_ms,
                "service": edge.from_node.replace("ha.service:", ""),
                "entity": edge.to_node.replace("ha.entity:", ""),
                "edge": edge
            })
            last_timestamp = edge.updated_at_ms
            
        # Add final session
        if current_session:
            sessions.append(current_session)
            
        return sessions
        
    def _discover_patterns(self, sequences: List[List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
        """Discover A→B patterns from action sequences."""
        patterns = {}
        
        for session in sequences:
            # Look for A→B pairs within delta window
            for i, action_a in enumerate(session):
                for j, action_b in enumerate(session[i+1:], i+1):
                    # Check if B is within time window of A
                    time_delta = action_b["timestamp"] - action_a["timestamp"]
                    if time_delta > self.delta_window_ms:
                        break  # No more valid pairs in this session
                        
                    # Create pattern identifier
                    antecedent = f"{action_a['service']}:{action_a['entity']}"
                    consequent = f"{action_b['service']}:{action_b['entity']}"
                    
                    # Skip self-patterns  
                    if antecedent == consequent:
                        continue
                        
                    pattern_id = f"{antecedent}→{consequent}"
                    
                    if pattern_id not in patterns:
                        patterns[pattern_id] = {
                            "antecedent": antecedent,
                            "consequent": consequent,
                            "occurrences": [],
                            "sessions_with_pattern": set()
                        }
                        
                    patterns[pattern_id]["occurrences"].append({
                        "timestamp_a": action_a["timestamp"],
                        "timestamp_b": action_b["timestamp"],
                        "delta_ms": time_delta
                    })
                    patterns[pattern_id]["sessions_with_pattern"].add(id(session))
                    
        return patterns
        
    def _calculate_evidence(self, pattern_data: Dict[str, Any], all_sessions: List[List[Dict[str, Any]]]) -> PatternEvidence:
        """Calculate statistical evidence for a pattern."""
        total_sessions = len(all_sessions)
        pattern_sessions = len(pattern_data["sessions_with_pattern"])
        pattern_count = len(pattern_data["occurrences"])
        
        antecedent = pattern_data["antecedent"]
        consequent = pattern_data["consequent"]
        
        # Count sessions containing antecedent and consequent individually
        antecedent_sessions = 0
        consequent_sessions = 0
        
        for session in all_sessions:
            session_actions = set()
            for action in session:
                session_actions.add(f"{action['service']}:{action['entity']}")
                
            if antecedent.replace(":", ":") in session_actions:
                antecedent_sessions += 1
            if consequent.replace(":", ":") in session_actions:
                consequent_sessions += 1
                
        # Calculate metrics
        support = pattern_sessions / total_sessions if total_sessions > 0 else 0
        confidence = pattern_sessions / antecedent_sessions if antecedent_sessions > 0 else 0
        
        # P(B) = consequent_sessions / total_sessions
        p_b = consequent_sessions / total_sessions if total_sessions > 0 else 0
        lift = confidence / p_b if p_b > 0 else 0
        
        return PatternEvidence(
            support=support,
            confidence=confidence,
            lift=lift,
            count=pattern_count,
            total_sessions=total_sessions
        )