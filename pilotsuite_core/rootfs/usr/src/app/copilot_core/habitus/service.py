"""
Habitus Service - High-level pattern mining orchestration.

This service coordinates pattern discovery and candidate creation:
- Runs habitus mining periodically or on-demand  
- Creates candidates from discovered patterns
- Provides API endpoints for pattern exploration
- Integrates with existing Core Add-on architecture
"""
import time
import logging
from typing import Dict, List, Optional, Any

from .miner import HabitusMiner, PatternEvidence
from ..brain_graph.service import BrainGraphService
from ..candidates.store import CandidateStore, Candidate

logger = logging.getLogger(__name__)


class HabitusService:
    """High-level service for habitus pattern mining and candidate creation."""
    
    def __init__(self, 
                 brain_service: BrainGraphService,
                 candidate_store: CandidateStore,
                 miner_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the habitus service.
        
        Args:
            brain_service: Brain graph service for pattern analysis
            candidate_store: Candidate store for suggestion persistence  
            miner_config: Optional miner configuration overrides
        """
        self.brain_service = brain_service
        self.candidate_store = candidate_store
        
        # Initialize miner with optional config overrides
        miner_params = {
            "brain_service": brain_service,
            "min_confidence": 0.6,
            "min_support": 0.1,
            "min_lift": 1.2,
            "delta_window_minutes": 15,
            "debounce_minutes": 5
        }
        if miner_config:
            miner_params.update(miner_config)
            
        self.miner = HabitusMiner(**miner_params)
        self.last_mining_run = 0
        
    def mine_and_create_candidates(
        self, 
        lookback_hours: int = 72,
        force: bool = False,
        zone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run pattern mining and create candidates for qualifying patterns.
        
        Args:
            lookback_hours: How far back to analyze patterns
            force: If True, run even if recently executed
            zone: Optional zone ID to filter patterns (e.g., "kitchen")
                  When specified, only patterns within this zone are mined.
            
        Returns:
            Results summary with patterns found and candidates created
        """
        now = time.time()
        
        # Throttle automatic runs (minimum 1 hour gap)
        if not force and (now - self.last_mining_run) < 3600:
            return {
                "status": "skipped",
                "reason": "Recent run within 1 hour", 
                "last_run_ago": int(now - self.last_mining_run)
            }
            
        logger.info(f"Starting habitus mining run (lookback: {lookback_hours}h, force: {force}, zone: {zone})")
        
        try:
            # Discover patterns (optionally zone-filtered)
            patterns = self.miner.mine_patterns(lookback_hours, zone=zone)
            
            results = {
                "status": "completed",
                "timestamp": int(now * 1000),
                "lookback_hours": lookback_hours,
                "zone": zone,
                "patterns_found": len(patterns),
                "candidates_created": 0,
                "patterns": patterns
            }
            
            # Create candidates for new patterns
            new_candidates = []
            for pattern_id, pattern_data in patterns.items():
                # Check if we already have a candidate for this pattern
                existing = self._find_existing_candidate(pattern_id)
                
                if not existing:
                    candidate = self._create_candidate_from_pattern(pattern_id, pattern_data, zone=zone)
                    new_candidates.append(candidate)
                    logger.info(f"Created candidate {candidate.candidate_id} for pattern {pattern_id}")
                    
            results["candidates_created"] = len(new_candidates)
            results["new_candidates"] = [c.candidate_id for c in new_candidates]
            
            self.last_mining_run = now
            logger.info(f"Habitus mining completed: {len(patterns)} patterns, {len(new_candidates)} new candidates")
            
            return results
            
        except Exception as e:
            logger.error(f"Habitus mining failed: {e}")
            return {
                "status": "error",
                "timestamp": int(now * 1000),
                "error": str(e)
            }
            
    def get_pattern_stats(self) -> Dict[str, Any]:
        """Get statistics about pattern mining capability."""
        # Basic stats from brain graph
        graph_stats = self.brain_service.get_stats()
        
        # Count existing candidates by pattern
        all_candidates = self.candidate_store.list_candidates()
        pattern_candidates = {}
        for candidate in all_candidates:
            pattern_id = candidate.pattern_id
            if pattern_id:
                if pattern_id not in pattern_candidates:
                    pattern_candidates[pattern_id] = {"total": 0, "by_state": {}}
                pattern_candidates[pattern_id]["total"] += 1
                state = candidate.state
                pattern_candidates[pattern_id]["by_state"][state] = pattern_candidates[pattern_id]["by_state"].get(state, 0) + 1
                
        return {
            "graph_nodes": graph_stats.get("node_count", 0),
            "graph_edges": graph_stats.get("edge_count", 0),
            "patterns_with_candidates": len(pattern_candidates),
            "last_mining_run": int(self.last_mining_run),
            "mining_config": {
                "min_confidence": self.miner.min_confidence,
                "min_support": self.miner.min_support,
                "min_lift": self.miner.min_lift,
                "delta_window_minutes": self.miner.delta_window_ms // (60 * 1000),
                "debounce_minutes": self.miner.debounce_ms // (60 * 1000)
            }
        }
        
    def _find_existing_candidate(self, pattern_id: str) -> Optional[Candidate]:
        """Check if we already have a candidate for this pattern."""
        all_candidates = self.candidate_store.list_candidates()
        for candidate in all_candidates:
            if candidate.pattern_id == pattern_id:
                # Don't create duplicates for dismissed or accepted patterns
                if candidate.state in ["dismissed", "accepted"]:
                    return candidate
                # Allow new candidates for deferred patterns if retry time passed
                if candidate.state == "deferred":
                    if candidate.retry_after and time.time() < candidate.retry_after:
                        return candidate
        return None
        
    def _create_candidate_from_pattern(
        self, 
        pattern_id: str, 
        pattern_data: Dict[str, Any],
        zone: Optional[str] = None
    ) -> Candidate:
        """Create a new candidate from a discovered pattern."""
        # Parse antecedent and consequent
        antecedent = pattern_data["antecedent"]  # e.g., "light.turn_on:light.living_room"
        consequent = pattern_data["consequent"]  # e.g., "media_player.play_media:media_player.living_room"
        
        # Extract service and entity info for metadata
        try:
            ant_service, ant_entity = antecedent.split(":", 1)
            cons_service, cons_entity = consequent.split(":", 1)
        except ValueError:
            # Fallback if parsing fails
            ant_service = ant_entity = antecedent
            cons_service = cons_entity = consequent
        
        metadata = {
            "antecedent": {
                "service": ant_service,
                "entity": ant_entity,
                "full": antecedent
            },
            "consequent": {
                "service": cons_service, 
                "entity": cons_entity,
                "full": consequent
            },
            "discovered_at": pattern_data["discovered_at"],
            "discovery_method": "habitus_miner_v2",
            "zone_filter": zone  # Track which zone this was filtered by
        }
        
        candidate_id = self.candidate_store.add_candidate(
            pattern_id=pattern_id,
            evidence=pattern_data["evidence"],
            metadata=metadata
        )
        
        return self.candidate_store.get_candidate(candidate_id)
        
    def list_recent_patterns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently discovered patterns from candidates."""
        all_candidates = self.candidate_store.list_candidates()
        
        # Sort by creation time, newest first
        recent_candidates = sorted(
            [c for c in all_candidates if c.pattern_id], 
            key=lambda x: x.created_at, 
            reverse=True
        )[:limit]
        
        patterns = []
        for candidate in recent_candidates:
            pattern_info = {
                "pattern_id": candidate.pattern_id,
                "candidate_id": candidate.candidate_id,
                "state": candidate.state,
                "evidence": candidate.evidence,
                "created_at": candidate.created_at,
                "metadata": candidate.metadata
            }
            patterns.append(pattern_info)
            
        return patterns