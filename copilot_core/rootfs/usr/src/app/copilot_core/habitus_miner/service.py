"""Habitus Miner service for A→B rule discovery from Home Assistant events."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from .model import NormEvent, Rule, MiningConfig, EventStreamType, RulesType
from .store import HabitusMinerStore
from .mining import mine_ab_rules, mine_with_context_stratification
from .feedback_store import HabitusFeedbackStore

_LOGGER = logging.getLogger(__name__)


class HabitusMinerService:
    """Main service for discovering behavioral patterns in Smart Home events."""

    def __init__(
        self,
        storage_dir: Path,
        config: MiningConfig | None = None,
        vector_store: Any = None,
        embedding_engine: Any = None,
        integration_bus: Any = None,
    ):
        self.storage_dir = Path(storage_dir)
        self.config = config or MiningConfig()
        self.store = HabitusMinerStore(self.storage_dir)
        self.feedback_store = HabitusFeedbackStore(self.storage_dir)
        self._vector_store = vector_store
        self._embedding_engine = embedding_engine
        self._integration_bus = integration_bus
    
    def normalize_ha_event(self, ha_event: dict[str, Any]) -> NormEvent | None:
        """Convert Home Assistant event to normalized event.
        
        Expected HA event format:
        {
            "time_fired": "2026-02-08T06:44:12.345Z",
            "event_type": "state_changed",
            "data": {
                "entity_id": "light.kitchen",
                "old_state": {"state": "off", "attributes": {...}},
                "new_state": {"state": "on", "attributes": {...}},
            },
            "context": {"source": "manual", "user_id": "...", ...}
        }
        """
        try:
            # Extract basic info
            event_type = ha_event.get("event_type")
            if event_type != "state_changed":
                return None
            
            data = ha_event.get("data", {})
            entity_id = data.get("entity_id")
            if not entity_id or not isinstance(entity_id, str):
                return None
            
            # Parse states
            old_state = data.get("old_state")
            new_state = data.get("new_state") 
            
            if not new_state or not isinstance(new_state, dict):
                return None
            
            old_val = old_state.get("state") if old_state else None
            new_val = new_state.get("state")
            
            # Only process actual state transitions
            if old_val == new_val:
                return None
            
            # Skip unavailable/unknown states
            if new_val in ("unavailable", "unknown", ""):
                return None
            
            # Parse timestamp
            time_fired = ha_event.get("time_fired")
            if isinstance(time_fired, str):
                # Parse ISO timestamp
                from datetime import datetime
                dt = datetime.fromisoformat(time_fired.replace('Z', '+00:00'))
                ts_ms = int(dt.timestamp() * 1000)
            elif isinstance(time_fired, (int, float)):
                ts_ms = int(time_fired * 1000)
            else:
                ts_ms = int(time.time() * 1000)
            
            # Extract domain
            domain = entity_id.split('.', 1)[0] if '.' in entity_id else ""
            
            # Create normalized transition (without colon prefix)
            transition = new_val  # e.g., "on", "off", "heat"

            # Extract context (privacy-aware)
            context = {}
            ha_context = ha_event.get("context", {})
            
            # Safe context extraction
            if "source" in ha_context:
                context["source"] = str(ha_context["source"])
            
            # Time-based context
            dt = datetime.fromtimestamp(ts_ms / 1000)
            context["hour"] = str(dt.hour)
            context["weekday"] = str(dt.weekday())  # 0=Monday, 6=Sunday
            
            if 6 <= dt.hour <= 11:
                context["time_of_day"] = "morning"
            elif 12 <= dt.hour <= 17:
                context["time_of_day"] = "day"
            elif 18 <= dt.hour <= 22:
                context["time_of_day"] = "evening"
            else:
                context["time_of_day"] = "night"
            
            # Anonymize entity_id if configured
            if self.config.anonymize_entity_ids:
                entity_id = f"{domain}.{hash(entity_id) % 1000}"
            
            return NormEvent(
                ts=ts_ms,
                key=f"{entity_id}:{transition}",  # e.g., "light.kitchen:on"
                entity_id=entity_id,
                domain=domain,
                transition=transition,
                context=context
            )
        
        except Exception as e:
            _LOGGER.warning("Failed to normalize HA event: %s", e)
            return None
    
    def process_ha_events(self, ha_events: list[dict[str, Any]]) -> EventStreamType:
        """Convert list of HA events to normalized event stream."""
        events = []
        
        for ha_event in ha_events:
            norm_event = self.normalize_ha_event(ha_event)
            if norm_event:
                events.append(norm_event)
        
        _LOGGER.info(
            "Processed %d HA events -> %d normalized events", 
            len(ha_events), len(events)
        )
        
        return events
    
    def mine_from_ha_events(self, ha_events: list[dict[str, Any]]) -> RulesType:
        """Mine rules directly from HA events."""
        events = self.process_ha_events(ha_events)
        return self.mine_rules(events)
    
    def mine_rules(self, events: EventStreamType) -> RulesType:
        """Mine A→B rules from normalized events."""
        if not events:
            _LOGGER.warning("No events provided for mining")
            return []
        
        _LOGGER.info("Mining rules from %d events with config: %s", 
                    len(events), self.config)
        
        start_time = time.time()
        
        # Use context stratification if enabled
        if self.config.context_features:
            rules = mine_with_context_stratification(events, self.config)
        else:
            rules = mine_ab_rules(events, self.config)
        
        mining_time = time.time() - start_time
        
        _LOGGER.info(
            "Mining completed in %.2fs: found %d rules",
            mining_time, len(rules)
        )

        # Apply feedback weights from previous user decisions
        rules = self._apply_feedback_weights(rules)

        # Cache events and save rules
        self.store.cache_events(events)
        self.store.save_rules(rules)
        self.store.update_mining_timestamp(int(time.time() * 1000))

        # Embed new rules in RAG vector store and publish discovery events
        if rules:
            self._embed_rules_in_rag(rules)
            self._publish_pattern_events(rules)

        return rules

    def _apply_feedback_weights(self, rules: RulesType) -> RulesType:
        """Apply persistent feedback weights to mined rules.

        Accepted patterns get boosted confidence, rejected patterns get
        suppressed.  Rules whose weighted confidence drops below the
        configured min_confidence are removed.
        """
        weights = self.feedback_store.get_feedback_weights()
        if not weights:
            return rules

        adjusted = []
        suppressed = 0
        for rule in rules:
            # Build pattern key matching the feedback store format
            pattern_key = f"{rule.A}->{rule.B}"
            w = weights.get(pattern_key)
            if w is None:
                adjusted.append(rule)
                continue

            # Apply weight multiplier to confidence
            rule.confidence = min(1.0, rule.confidence * w)
            from .mining import _wilson_lower_bound
            # Recalculate lower bound based on adjusted confidence
            rule.confidence_lb = _wilson_lower_bound(
                int(rule.nAB * w), rule.nA
            ) if rule.nA > 0 else 0.0

            # Suppress rules that fall below threshold after feedback
            if rule.confidence < self.config.min_confidence:
                suppressed += 1
                continue
            adjusted.append(rule)

        if suppressed:
            _LOGGER.info("Feedback suppressed %d rules below confidence threshold", suppressed)

        # Re-sort by score
        adjusted.sort(key=lambda r: r.score(), reverse=True)
        return adjusted

    def _embed_rules_in_rag(self, rules: RulesType) -> None:
        """Embed discovered rules in vector store for semantic search.

        Only embeds when the embedding engine uses Ollama (semantic
        embeddings).  Hash-based local embeddings (bag-of-words) produce
        vectors without real semantic meaning, so skipping them avoids
        polluting the vector store with useless data.
        """
        vs = self._vector_store
        ee = self._embedding_engine
        if not vs or not ee or not hasattr(ee, "embed_text_sync"):
            return
        # Skip if embedding engine is hash-only (no semantic value)
        if hasattr(ee, "config") and not getattr(ee.config, "use_ollama", False):
            _LOGGER.debug("Skipping RAG embedding — hash-only engine has no semantic value")
            return

        embedded = 0
        for rule in rules:
            try:
                a_entity = rule.A.rsplit(":", 1)[0] if ":" in rule.A else rule.A
                b_entity = rule.B.rsplit(":", 1)[0] if ":" in rule.B else rule.B
                zone_id = getattr(rule, "zone_id", "") or ""
                text = (
                    f"Wenn {a_entity} sich aendert, "
                    f"folgt {b_entity} innerhalb von {rule.dt_sec} Sekunden "
                    f"mit {rule.confidence:.0%} Wahrscheinlichkeit"
                    f" ({rule.lift:.1f}x haeufiger als Zufall, {rule.nAB} Beobachtungen)"
                )
                if zone_id:
                    text += f" in Zone {zone_id}"
                vector = ee.embed_text_sync(text)
                rule_key = f"{rule.A}_{rule.B}_{rule.dt_sec}"
                vs.upsert_sync(
                    entry_id=f"pattern:{rule_key}",
                    vector=vector,
                    entry_type="pattern",
                    metadata={
                        "a_entity": a_entity,
                        "b_entity": b_entity,
                        "confidence": rule.confidence,
                        "lift": rule.lift,
                        "support": rule.nAB,
                        "zone_id": getattr(rule, "zone_id", "") or "",
                    },
                )
                embedded += 1
            except Exception:
                _LOGGER.debug("Failed to embed rule %s → %s in RAG", rule.A, rule.B, exc_info=True)

        if embedded:
            _LOGGER.info("Embedded %d/%d rules in RAG vector store", embedded, len(rules))

    def _publish_pattern_events(self, rules: RulesType) -> None:
        """Publish pattern.discovered events on the integration bus."""
        bus = self._integration_bus
        if not bus or not hasattr(bus, "publish"):
            return

        for rule in rules:
            try:
                a_entity = rule.A.rsplit(":", 1)[0] if ":" in rule.A else rule.A
                b_entity = rule.B.rsplit(":", 1)[0] if ":" in rule.B else rule.B
                bus.publish("pattern.discovered", {
                    "rule_key": f"{rule.A}_{rule.B}_{rule.dt_sec}",
                    "a_entity": a_entity,
                    "b_entity": b_entity,
                    "confidence": rule.confidence,
                    "lift": rule.lift,
                    "support": rule.nAB,
                    "zone_id": getattr(rule, "zone_id", "") or "",
                })
            except Exception:
                _LOGGER.debug("Failed to publish pattern.discovered event", exc_info=True)
    
    def get_rules(
        self, 
        *, 
        limit: int | None = None,
        min_score: float | None = None,
        a_filter: str | None = None,
        b_filter: str | None = None,
        domain_filter: str | None = None
    ) -> RulesType:
        """Get discovered rules with optional filtering."""
        rules = self.store.get_rules(limit=None)  # Get all first
        
        # Apply filters
        if min_score is not None:
            rules = [r for r in rules if r.score() >= min_score]
        
        if a_filter:
            rules = [r for r in rules if a_filter.lower() in r.A.lower()]
        
        if b_filter:
            rules = [r for r in rules if b_filter.lower() in r.B.lower()]
        
        if domain_filter:
            rules = [r for r in rules 
                    if (domain_filter in r.A.split(':')[0] if ':' in r.A else False) or
                       (domain_filter in r.B.split(':')[0] if ':' in r.B else False)]
        
        # Sort by score and apply limit
        rules.sort(key=lambda r: r.score(), reverse=True)
        
        return rules[:limit] if limit else rules
    
    def explain_rule(self, rule: Rule) -> dict[str, Any]:
        """Generate human-readable explanation for a rule."""
        # Parse A and B events
        def parse_event_key(key: str) -> tuple[str, str, str]:
            if ':' in key:
                entity_part, transition = key.rsplit(':', 1)
                domain = entity_part.split('.', 1)[0] if '.' in entity_part else ""
                return entity_part, domain, transition
            return key, "", ""
        
        a_entity, a_domain, a_transition = parse_event_key(rule.A)
        b_entity, b_domain, b_transition = parse_event_key(rule.B)
        
        # Create explanation
        explanation = {
            "rule_summary": f"When {a_entity} → {a_transition}, then {b_entity} → {b_transition} (within {rule.dt_sec}s)",
            "confidence": {
                "percentage": f"{rule.confidence:.1%}",
                "description": f"In {rule.nAB} out of {rule.nA} cases",
                "stability": f"Lower bound: {rule.confidence_lb:.1%}" 
            },
            "lift": {
                "value": f"{rule.lift:.2f}",
                "description": "Times more likely than baseline" if rule.lift > 1 else "As likely as baseline"
            },
            "evidence": {
                "observation_period": f"{rule.observation_period_days} days",
                "total_a_events": rule.nA,
                "successful_patterns": rule.nAB,
                "failed_patterns": rule.nA - rule.nAB,
            }
        }
        
        # Add timing information
        if rule.evidence and rule.evidence.latency_quantiles:
            q = rule.evidence.latency_quantiles
            if len(q) >= 3:
                explanation["timing"] = {
                    "typical_delay": f"{q[1]:.1f}s (median)",
                    "delay_range": f"{q[0]:.1f}s - {q[-1]:.1f}s",
                    "quartiles": [f"{x:.1f}s" for x in q]
                }
        
        # Add examples
        if rule.evidence:
            if rule.evidence.hit_examples:
                explanation["examples"] = []
                for t_a, t_b, latency_ms in rule.evidence.hit_examples[:3]:
                    from datetime import datetime
                    dt_a = datetime.fromtimestamp(t_a / 1000)
                    explanation["examples"].append({
                        "timestamp": dt_a.strftime("%Y-%m-%d %H:%M:%S"),
                        "delay": f"{latency_ms / 1000:.1f}s"
                    })
        
        return explanation
    
    def export_rules_summary(self, rules: RulesType | None = None) -> dict[str, Any]:
        """Export rules summary for UI/API consumption."""
        if rules is None:
            rules = self.get_rules()
        
        # Group by domains
        domain_stats = {}
        for rule in rules:
            a_domain = rule.A.split('.', 1)[0] if '.' in rule.A else "unknown"
            b_domain = rule.B.split('.', 1)[0] if '.' in rule.B else "unknown"
            
            key = f"{a_domain} → {b_domain}"
            if key not in domain_stats:
                domain_stats[key] = {"count": 0, "avg_confidence": 0, "rules": []}
            
            domain_stats[key]["count"] += 1
            domain_stats[key]["avg_confidence"] += rule.confidence
            domain_stats[key]["rules"].append(rule.A + " → " + rule.B)
        
        # Calculate averages
        for key in domain_stats:
            stats = domain_stats[key]
            stats["avg_confidence"] /= stats["count"]
            stats["avg_confidence"] = round(stats["avg_confidence"], 3)
            stats["rules"] = stats["rules"][:5]  # Top 5 examples
        
        return {
            "total_rules": len(rules),
            "avg_confidence": round(sum(r.confidence for r in rules) / len(rules), 3) if rules else 0,
            "avg_lift": round(sum(r.lift for r in rules) / len(rules), 3) if rules else 0,
            "top_rules": [
                {
                    "A": rule.A,
                    "B": rule.B,
                    "confidence": round(rule.confidence, 3),
                    "lift": round(rule.lift, 2),
                    "score": round(rule.score(), 3),
                    "window_sec": rule.dt_sec
                }
                for rule in rules[:10]
            ],
            "domain_patterns": domain_stats,
            "last_mining": self.store.last_mining_ts,
            "storage_stats": self.store.get_stats(),
        }
    
    def update_config(self, **kwargs) -> None:
        """Update mining configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                _LOGGER.info("Updated config %s = %s", key, value)
    
    def apply_feedback(self, rule_a: str, rule_b: str, accepted: bool) -> bool:
        """Apply user feedback to a rule's confidence.

        When a suggestion based on a rule is accepted, the rule's nAB count
        is incremented (raising confidence).  When rejected, nA is
        incremented without nAB (lowering confidence).  The rule is then
        re-scored and persisted.

        Feedback is also recorded in the persistent feedback store so that
        future mining runs apply the same reinforcement/suppression.

        Returns True if the rule was found and updated.
        """
        rules = self.store.rules
        target = None
        for rule in rules:
            if rule.A == rule_a and rule.B == rule_b:
                target = rule
                break

        if target is None:
            _LOGGER.warning("Feedback for unknown rule %s -> %s", rule_a, rule_b)
            return False

        if accepted:
            target.nA += 1
            target.nAB += 1
        else:
            target.nA += 1
            # nAB stays the same -> confidence drops

        # Recalculate confidence
        target.confidence = target.nAB / target.nA if target.nA > 0 else 0.0
        from .mining import _wilson_lower_bound
        target.confidence_lb = _wilson_lower_bound(target.nAB, target.nA)

        self.store.save_rules(rules)

        # Persist feedback for future mining runs
        pattern_key = f"{rule_a}->{rule_b}"
        action = "accepted" if accepted else "rejected"
        self.feedback_store.record_feedback(pattern_key, action)

        _LOGGER.info(
            "Feedback applied to %s -> %s: accepted=%s, new confidence=%.3f",
            rule_a, rule_b, accepted, target.confidence,
        )
        return True

    def reset_cache(self) -> None:
        """Reset all cached data including feedback."""
        self.store.clear_cache()
        self.feedback_store.clear()
        _LOGGER.info("Reset all cached data including feedback")