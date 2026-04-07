"""Storage for Habitus Miner rules and events."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .model import Rule, NormEvent, RulesType, EventStreamType

_LOGGER = logging.getLogger(__name__)


class HabitusMinerStore:
    """Privacy-first storage for discovered rules and processed events."""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # File paths
        self.rules_file = self.storage_dir / "discovered_rules.json"
        self.events_cache_file = self.storage_dir / "events_cache.jsonl"
        self.state_file = self.storage_dir / "miner_state.json"
        
        # In-memory cache
        self.rules: list[Rule] = []
        self.last_mining_ts: int | None = None
        self.total_events_processed: int = 0
        
        # Load existing data
        self._load_state()
        self._load_rules()
    
    def _load_state(self) -> None:
        """Load miner state from disk."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.last_mining_ts = state.get("last_mining_ts")
                    self.total_events_processed = state.get("total_events_processed", 0)
        except Exception as e:
            _LOGGER.warning("Failed to load miner state: %s", e)
    
    def _save_state(self) -> None:
        """Save miner state to disk."""
        try:
            state = {
                "last_mining_ts": self.last_mining_ts,
                "total_events_processed": self.total_events_processed,
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            _LOGGER.error("Failed to save miner state: %s", e)
    
    def _load_rules(self) -> None:
        """Load discovered rules from disk."""
        try:
            if self.rules_file.exists():
                with open(self.rules_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.rules = [self._rule_from_dict(r) for r in data.get("rules", [])]
        except Exception as e:
            _LOGGER.warning("Failed to load rules: %s", e)
            self.rules = []
    
    def _rule_to_dict(self, rule: Rule) -> dict[str, Any]:
        """Convert Rule to serializable dict."""
        result = {
            "A": rule.A,
            "B": rule.B,
            "dt_sec": rule.dt_sec,
            "nA": rule.nA,
            "nB": rule.nB,
            "nAB": rule.nAB,
            "confidence": rule.confidence,
            "confidence_lb": rule.confidence_lb,
            "lift": rule.lift,
            "leverage": rule.leverage,
            "conviction": rule.conviction,
            "observation_period_days": rule.observation_period_days,
            "baseline_p_b": rule.baseline_p_b,
            "created_at_ms": rule.created_at_ms,
        }
        
        # Evidence (simplified for v0.1)
        if rule.evidence:
            result["evidence"] = {
                "hit_examples": rule.evidence.hit_examples,
                "miss_examples": rule.evidence.miss_examples,
                "latency_quantiles": rule.evidence.latency_quantiles,
            }
        
        return result
    
    def _rule_from_dict(self, data: dict[str, Any]) -> Rule:
        """Convert dict to Rule object."""
        from .model import Rule, RuleEvidence
        
        evidence = None
        if "evidence" in data:
            ev_data = data["evidence"]
            evidence = RuleEvidence(
                hit_examples=ev_data.get("hit_examples", []),
                miss_examples=ev_data.get("miss_examples", []),
                latency_quantiles=ev_data.get("latency_quantiles", []),
            )
        
        return Rule(
            A=data["A"],
            B=data["B"],
            dt_sec=data["dt_sec"],
            nA=data["nA"],
            nB=data["nB"],
            nAB=data["nAB"],
            confidence=data["confidence"],
            confidence_lb=data["confidence_lb"],
            lift=data["lift"],
            leverage=data["leverage"],
            conviction=data.get("conviction"),
            observation_period_days=data["observation_period_days"],
            baseline_p_b=data["baseline_p_b"],
            created_at_ms=data["created_at_ms"],
            evidence=evidence,
        )
    
    def save_rules(self, rules: RulesType) -> None:
        """Save discovered rules to disk."""
        try:
            import time
            self.rules = rules
            data = {
                "version": 1,
                "generated_at_ms": int(time.time() * 1000),
                "total_rules": len(rules),
                "rules": [self._rule_to_dict(r) for r in rules],
            }
            
            with open(self.rules_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            _LOGGER.info("Saved %d rules to %s", len(rules), self.rules_file)
        except Exception as e:
            _LOGGER.error("Failed to save rules: %s", e)
    
    def get_rules(self, *, limit: int | None = None) -> RulesType:
        """Get discovered rules, optionally limited."""
        rules = sorted(self.rules, key=lambda r: r.score(), reverse=True)
        return rules[:limit] if limit else rules
    
    def cache_events(self, events: EventStreamType) -> None:
        """Cache processed events (for debugging/replay)."""
        try:
            # Keep only recent events to limit disk usage
            max_events = 10000
            if len(events) > max_events:
                events = events[-max_events:]
            
            with open(self.events_cache_file, 'w', encoding='utf-8') as f:
                for event in events:
                    event_dict = {
                        "ts": event.ts,
                        "key": event.key,
                        "entity_id": event.entity_id,
                        "domain": event.domain,
                        "transition": event.transition,
                        "context": event.context,
                    }
                    f.write(json.dumps(event_dict) + "\n")
            
            self.total_events_processed = len(events)
            self._save_state()
        except Exception as e:
            _LOGGER.error("Failed to cache events: %s", e)
    
    def load_cached_events(self) -> EventStreamType:
        """Load cached events from disk."""
        events = []
        try:
            if self.events_cache_file.exists():
                with open(self.events_cache_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            event = NormEvent(
                                ts=data["ts"],
                                key=data["key"],
                                entity_id=data["entity_id"],
                                domain=data["domain"],
                                transition=data["transition"],
                                context=data.get("context"),
                            )
                            events.append(event)
        except Exception as e:
            _LOGGER.error("Failed to load cached events: %s", e)
        
        return events
    
    def update_mining_timestamp(self, ts: int) -> None:
        """Update the last mining timestamp."""
        self.last_mining_ts = ts
        self._save_state()
    
    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        return {
            "total_rules": len(self.rules),
            "total_events_processed": self.total_events_processed,
            "last_mining_ts": self.last_mining_ts,
            "storage_dir": str(self.storage_dir),
            "files_exist": {
                "rules": self.rules_file.exists(),
                "events_cache": self.events_cache_file.exists(),
                "state": self.state_file.exists(),
            },
        }
    
    def clear_cache(self) -> None:
        """Clear all cached data (for testing/reset)."""
        try:
            for file in [self.rules_file, self.events_cache_file, self.state_file]:
                if file.exists():
                    file.unlink()
            
            self.rules = []
            self.last_mining_ts = None
            self.total_events_processed = 0
            
            _LOGGER.info("Cleared all cached data")
        except Exception as e:
            _LOGGER.error("Failed to clear cache: %s", e)