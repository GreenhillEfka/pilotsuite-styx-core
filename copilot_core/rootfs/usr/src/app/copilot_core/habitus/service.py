"""
Habitus Service - High-level pattern mining orchestration.

This service coordinates pattern discovery and candidate creation:
- Runs habitus mining periodically or on-demand  
- Creates candidates from discovered patterns
- Provides API endpoints for pattern exploration
- Integrates with existing Core Add-on architecture
"""
import json
import os
import threading
import time
import logging
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Any

from .miner import HabitusMiner, PatternEvidence
from ..brain_graph.service import BrainGraphService
from ..candidates.store import CandidateStore, Candidate

logger = logging.getLogger(__name__)


class HabitusService:
    """High-level service for habitus pattern mining and candidate creation."""
    
    _DEFAULT_CONFIG: dict[str, Any] = {
        "enabled": True,
        "lookback_hours": 72,
        # Pattern filters
        "min_confidence": 0.6,
        "min_support": 0.1,
        "min_lift": 1.2,
        # Time windows
        "delta_window_minutes": 15,
        "debounce_minutes": 5,
        # Scheduling / safety
        "mine_on_event_ingest": True,
        "min_events_per_batch": 5,
        "min_interval_minutes": 60,
        # Edge types to consider (brain graph)
        "edge_types": ["targets", "affects"],
        # Candidate creation caps
        "max_new_candidates_per_run": 25,
    }

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

        self._config_lock = threading.RLock()
        self._config_path = Path(
            os.environ.get("HABITUS_CONFIG_PATH", "/data/habitus_config.json")
        )
        self._config: dict[str, Any] = dict(self._DEFAULT_CONFIG)
        self._load_config_from_disk()
        
        # Initialize miner with optional config overrides
        miner_params = {
            "brain_service": brain_service,
            "min_confidence": float(self._config.get("min_confidence", 0.6)),
            "min_support": float(self._config.get("min_support", 0.1)),
            "min_lift": float(self._config.get("min_lift", 1.2)),
            "delta_window_minutes": int(self._config.get("delta_window_minutes", 15)),
            "debounce_minutes": int(self._config.get("debounce_minutes", 5)),
        }
        if miner_config:
            miner_params.update(miner_config)
            
        self.miner = HabitusMiner(**miner_params)
        self.last_mining_run = 0

    # ------------------------------------------------------------------
    # Config (persisted) — used by dashboard module config panels
    # ------------------------------------------------------------------

    def get_config(self) -> dict[str, Any]:
        with self._config_lock:
            return dict(self._config)

    def set_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Merge+validate config updates and persist to disk."""
        if not isinstance(updates, dict):
            return self.get_config()

        with self._config_lock:
            cfg = dict(self._config)
            cfg.update(updates)
            cfg = self._validate_config(cfg)
            self._config = cfg
            self._persist_config_to_disk()
            self._apply_config_to_miner(cfg)
            return dict(cfg)

    def _validate_config(self, cfg: dict[str, Any]) -> dict[str, Any]:
        """Clamp types/ranges to keep mining safe."""
        out = dict(self._DEFAULT_CONFIG)
        out.update(cfg or {})

        def _as_bool(key: str, default: bool) -> bool:
            val = out.get(key, default)
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return bool(val)
            if isinstance(val, str):
                return val.strip().lower() in {"1", "true", "yes", "on"}
            return default

        def _as_int(key: str, default: int, *, lo: int, hi: int) -> int:
            try:
                val = int(out.get(key, default))
            except (TypeError, ValueError):
                val = default
            return max(lo, min(hi, val))

        def _as_float(key: str, default: float, *, lo: float, hi: float) -> float:
            try:
                val = float(out.get(key, default))
            except (TypeError, ValueError):
                val = default
            return max(lo, min(hi, val))

        out["enabled"] = _as_bool("enabled", True)
        out["lookback_hours"] = _as_int("lookback_hours", 72, lo=1, hi=168)
        out["min_confidence"] = _as_float("min_confidence", 0.6, lo=0.0, hi=1.0)
        out["min_support"] = _as_float("min_support", 0.1, lo=0.0, hi=1.0)
        out["min_lift"] = _as_float("min_lift", 1.2, lo=0.0, hi=100.0)
        out["delta_window_minutes"] = _as_int("delta_window_minutes", 15, lo=1, hi=240)
        out["debounce_minutes"] = _as_int("debounce_minutes", 5, lo=0, hi=240)
        out["mine_on_event_ingest"] = _as_bool("mine_on_event_ingest", True)
        out["min_events_per_batch"] = _as_int("min_events_per_batch", 5, lo=1, hi=5000)
        out["min_interval_minutes"] = _as_int("min_interval_minutes", 60, lo=1, hi=1440)
        out["max_new_candidates_per_run"] = _as_int("max_new_candidates_per_run", 25, lo=1, hi=500)

        edge_types = out.get("edge_types", ["targets", "affects"])
        if isinstance(edge_types, str):
            edge_types = [s.strip() for s in edge_types.split(",") if s.strip()]
        if not isinstance(edge_types, list):
            edge_types = ["targets", "affects"]
        allowed = {"targets", "affects", "triggered_by", "correlates", "in_zone", "located_in"}
        out["edge_types"] = [t for t in edge_types if isinstance(t, str) and t in allowed] or ["targets", "affects"]

        return out

    def _load_config_from_disk(self) -> None:
        """Best-effort load persisted config."""
        try:
            path = self._config_path
            if not path.exists():
                return
            raw = json.loads(path.read_text(encoding="utf-8") or "{}")
            if isinstance(raw, dict):
                self._config = self._validate_config({**self._config, **raw})
        except Exception:
            # Never fail startup due to config.
            return

    def _persist_config_to_disk(self) -> None:
        path = self._config_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self._config, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception:
            # Non-fatal: config persists in memory.
            return

    def _apply_config_to_miner(self, cfg: dict[str, Any]) -> None:
        """Apply validated config to the miner instance."""
        try:
            self.miner.min_confidence = float(cfg.get("min_confidence", self.miner.min_confidence))
            self.miner.min_support = float(cfg.get("min_support", self.miner.min_support))
            self.miner.min_lift = float(cfg.get("min_lift", self.miner.min_lift))
            self.miner.delta_window_ms = int(cfg.get("delta_window_minutes", 15)) * 60 * 1000
            self.miner.debounce_ms = int(cfg.get("debounce_minutes", 5)) * 60 * 1000
        except Exception:
            return
        
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

        cfg = self.get_config()
        if not cfg.get("enabled", True):
            return {
                "status": "disabled",
                "timestamp": int(now * 1000),
            }
        self._apply_config_to_miner(cfg)
        lookback_hours = int(cfg.get("lookback_hours", lookback_hours or 72))
        
        # Throttle automatic runs
        min_interval_sec = int(cfg.get("min_interval_minutes", 60)) * 60
        if not force and (now - self.last_mining_run) < min_interval_sec:
            return {
                "status": "skipped",
                "reason": "Recent run within configured interval",
                "last_run_ago": int(now - self.last_mining_run)
            }
            
        logger.info(f"Starting habitus mining run (lookback: {lookback_hours}h, force: {force}, zone: {zone})")
        
        try:
            # Discover patterns (optionally zone-filtered)
            edge_types = set(cfg.get("edge_types") or ["targets", "affects"])
            patterns = self.miner.mine_patterns(lookback_hours, zone=zone, edge_types=edge_types)
            
            results = {
                "status": "completed",
                "timestamp": int(now * 1000),
                "lookback_hours": lookback_hours,
                "zone": zone,
                "patterns_found": len(patterns),
                "candidates_created": 0,
                "patterns": patterns
            }
            
            # Create candidates for new patterns (cap per run)
            new_candidates = []
            max_new = int(cfg.get("max_new_candidates_per_run", 25))
            for pattern_id, pattern_data in patterns.items():
                # Check if we already have a candidate for this pattern
                existing = self._find_existing_candidate(pattern_id)
                
                if not existing:
                    candidate = self._create_candidate_from_pattern(pattern_id, pattern_data, zone=zone)
                    new_candidates.append(candidate)
                    logger.info(f"Created candidate {candidate.candidate_id} for pattern {pattern_id}")
                if len(new_candidates) >= max_new:
                    break
                    
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
        
    def get_patterns_and_trends(self) -> Dict[str, Any]:
        """Return miner patterns, top rules, and trend data.

        Delegates to the miner's ``get_patterns_and_trends`` method and
        enriches the response with service-level metadata (last mining run,
        mining config, candidate counts).
        """
        miner_data = self.miner.get_patterns_and_trends()

        # Enrich with service-level stats
        all_candidates = self.candidate_store.list_candidates()
        pattern_candidate_count = sum(
            1 for c in all_candidates if c.pattern_id
        )
        states: Dict[str, int] = {}
        for c in all_candidates:
            states[c.state] = states.get(c.state, 0) + 1

        miner_data["last_mining_run"] = int(self.last_mining_run)
        miner_data["candidates_total"] = len(all_candidates)
        miner_data["candidates_with_pattern"] = pattern_candidate_count
        miner_data["candidates_by_state"] = states
        miner_data["mining_config"] = {
            "min_confidence": self.miner.min_confidence,
            "min_support": self.miner.min_support,
            "min_lift": self.miner.min_lift,
            "delta_window_minutes": self.miner.delta_window_ms // (60 * 1000),
            "debounce_minutes": self.miner.debounce_ms // (60 * 1000),
        }

        return miner_data

    def get_zone_statistics(self, zone: Optional[str] = None) -> Dict[str, Any]:
        """Return zone-level mining statistics.

        If *zone* is provided, returns stats for that zone only.
        Otherwise, returns stats for all zones that have patterns.

        The statistics include:
        - Number of patterns discovered per zone
        - Top patterns per zone
        - Presence history (from brain graph zone edges)
        """
        # Gather zone info from brain graph
        graph_stats = self.brain_service.get_stats()
        zone_nodes = []
        try:
            all_nodes = self.brain_service.store.get_nodes()
            zone_nodes = [n for n in all_nodes if n.node_id.startswith("zone:")]
        except Exception:
            pass

        zones_result: Dict[str, Any] = {}
        for zn in zone_nodes:
            zid = zn.node_id
            zone_name = zid.replace("zone:", "")

            if zone and zone_name != zone and zid != zone:
                continue

            # Get entities in zone
            zone_info = self.brain_service.get_zone_entities(zid)
            entity_count = len(zone_info.get("entities", [])) if "error" not in zone_info else 0

            # Mine patterns for this zone (lightweight: use last run data if available)
            zone_patterns = {}
            for pid, pdata in self.miner._last_patterns.items():
                ant = pdata.get("antecedent", "")
                cons = pdata.get("consequent", "")
                # Check if either entity belongs to this zone
                zone_entities_set = set()
                if "error" not in zone_info:
                    for ent in zone_info.get("entities", []):
                        zone_entities_set.add(ent.get("id", ""))
                for entity_ref in zone_entities_set:
                    if entity_ref in ant or entity_ref in cons:
                        zone_patterns[pid] = pdata
                        break

            zones_result[zone_name] = {
                "zone_id": zid,
                "entity_count": entity_count,
                "pattern_count": len(zone_patterns),
                "top_patterns": sorted(
                    zone_patterns.values(),
                    key=lambda p: p.get("evidence", {}).get("confidence", 0),
                    reverse=True,
                )[:5],
                "node_score": round(getattr(zn, "score", 0.0), 3),
            }

        return {
            "zones": zones_result,
            "total_zones": len(zone_nodes),
            "graph_nodes": graph_stats.get("node_count", 0),
            "graph_edges": graph_stats.get("edge_count", 0),
        }

    def detect_anomalies(self, lookback_hours: int = 24) -> Dict[str, Any]:
        """Basic anomaly detection based on pattern deviations.

        Compares the most recent mining results against the historical
        trend snapshots to flag sudden changes in pattern confidence or
        the appearance/disappearance of previously stable patterns.

        Returns a dict with:
          - anomalies: list of detected anomaly descriptions
          - stats: summary counters
        """
        anomalies: List[Dict[str, Any]] = []
        trends = self.miner._trend_snapshots

        if len(trends) < 2:
            return {
                "anomalies": [],
                "stats": {"total": 0, "reason": "insufficient_trend_data"},
            }

        latest = trends[-1]
        previous = trends[-2]

        # 1. Sudden drop in pattern count
        if previous.total_patterns > 0 and latest.total_patterns == 0:
            anomalies.append({
                "type": "pattern_drop",
                "severity": "warning",
                "message": f"All {previous.total_patterns} patterns disappeared",
                "timestamp": latest.timestamp,
            })
        elif previous.total_patterns > 0:
            drop_ratio = 1.0 - (latest.total_patterns / previous.total_patterns)
            if drop_ratio > 0.5:
                anomalies.append({
                    "type": "pattern_drop",
                    "severity": "info",
                    "message": f"Pattern count dropped by {int(drop_ratio * 100)}% "
                               f"({previous.total_patterns} -> {latest.total_patterns})",
                    "timestamp": latest.timestamp,
                })

        # 2. Significant confidence shift
        if previous.avg_confidence > 0 and latest.avg_confidence > 0:
            conf_delta = abs(latest.avg_confidence - previous.avg_confidence)
            if conf_delta > 0.2:
                direction = "increased" if latest.avg_confidence > previous.avg_confidence else "decreased"
                anomalies.append({
                    "type": "confidence_shift",
                    "severity": "info",
                    "message": f"Average confidence {direction} by {conf_delta:.2f} "
                               f"({previous.avg_confidence:.2f} -> {latest.avg_confidence:.2f})",
                    "timestamp": latest.timestamp,
                })

        # 3. New patterns that never appeared before
        for pid in self.miner._last_patterns:
            history = self.miner._pattern_history.get(pid, [])
            if len(history) == 1:
                anomalies.append({
                    "type": "new_pattern",
                    "severity": "info",
                    "message": f"New pattern discovered: {pid}",
                    "pattern_id": pid,
                    "timestamp": latest.timestamp,
                })

        return {
            "anomalies": anomalies,
            "stats": {
                "total": len(anomalies),
                "by_type": dict(Counter(a["type"] for a in anomalies)),
                "latest_trend": latest.to_dict() if latest else {},
            },
        }

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
