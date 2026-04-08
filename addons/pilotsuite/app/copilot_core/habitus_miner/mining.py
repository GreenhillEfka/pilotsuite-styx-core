"""A→B rule mining algorithms for Habitus Miner v0.1."""

from __future__ import annotations

import logging
import math
import statistics
from collections import defaultdict
from typing import Any

from .model import (
    NormEvent, 
    Rule, 
    RuleEvidence,
    MiningConfig, 
    EventStreamType, 
    RulesType
)

_LOGGER = logging.getLogger(__name__)


def _wilson_lower_bound(successes: int, trials: int, confidence: float = 0.95) -> float:
    """Calculate Wilson score interval lower bound for confidence estimation."""
    if trials == 0:
        return 0.0
    
    p = successes / trials
    z = 1.96 if confidence == 0.95 else 1.645  # z-score for confidence level
    
    denominator = 1 + z**2 / trials
    center_adjusted = p + z**2 / (2 * trials)
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * trials)) / trials)
    
    return max(0.0, (center_adjusted - margin) / denominator)


def _extract_context(event: NormEvent, features: list[str]) -> str | None:
    """Extract context bucket from event for stratification."""
    if not features or not event.context:
        return None
    
    # Simple bucket creation (v0.1) - can be extended
    ctx_values = []
    for feature in features:
        value = event.context.get(feature)
        if value:
            ctx_values.append(f"{feature}:{value}")
    
    return ";".join(ctx_values) if ctx_values else None


def _deduplicate_events(events: EventStreamType, config: MiningConfig) -> EventStreamType:
    """Remove duplicate/flapping events based on cooldown periods."""
    if not events:
        return []
    
    # Sort by timestamp
    events.sort(key=lambda e: e.ts)
    
    # Track last occurrence per entity+transition
    last_seen: dict[str, int] = {}
    deduplicated = []
    
    for event in events:
        key = f"{event.entity_id}:{event.transition}"
        cooldown = config.entity_cooldown.get(event.entity_id, config.default_cooldown)
        cooldown_ms = cooldown * 1000
        
        last_ts = last_seen.get(key, 0)
        if event.ts - last_ts >= cooldown_ms:
            deduplicated.append(event)
            last_seen[key] = event.ts
    
    _LOGGER.debug(
        "Deduplication: %d events -> %d events (removed %d)",
        len(events), len(deduplicated), len(events) - len(deduplicated)
    )
    
    return deduplicated


def _filter_events(events: EventStreamType, config: MiningConfig) -> EventStreamType:
    """Filter events by domain/entity inclusion/exclusion rules."""
    filtered = []
    
    for event in events:
        # Domain filters
        if config.include_domains and event.domain not in config.include_domains:
            continue
        if config.exclude_domains and event.domain in config.exclude_domains:
            continue
        
        # Entity filters  
        if config.include_entities and event.entity_id not in config.include_entities:
            continue
        if config.exclude_entities and event.entity_id in config.exclude_entities:
            continue
        
        filtered.append(event)
    
    _LOGGER.debug(
        "Domain/entity filtering: %d events -> %d events (removed %d)",
        len(events), len(filtered), len(events) - len(filtered)
    )
    
    return filtered


def _get_frequent_events(
    events: EventStreamType, 
    min_support_a: int, 
    min_support_b: int
) -> tuple[set[str], set[str]]:
    """Get frequent A and B event candidates based on minimum support."""
    counts = defaultdict(int)
    
    for event in events:
        counts[event.key] += 1
    
    a_candidates = {key for key, count in counts.items() if count >= min_support_a}
    b_candidates = {key for key, count in counts.items() if count >= min_support_b}
    
    _LOGGER.debug(
        "Frequent events: %d A candidates, %d B candidates from %d unique event types",
        len(a_candidates), len(b_candidates), len(counts)
    )
    
    return a_candidates, b_candidates


def _create_event_indices(events: EventStreamType) -> dict[str, list[int]]:
    """Create time-sorted indices for each event type."""
    indices = defaultdict(list)
    
    for event in events:
        indices[event.key].append(event.ts)
    
    # Sort timestamps for binary search
    for key in indices:
        indices[key].sort()
    
    return dict(indices)


def _count_ab_hits(
    a_key: str,
    b_key: str, 
    dt_ms: int,
    indices: dict[str, list[int]]
) -> tuple[int, list[tuple[int, int, int]], list[int]]:
    """Count A→B hits within time window and collect evidence."""
    import bisect
    
    a_times = indices.get(a_key, [])
    b_times = indices.get(b_key, [])
    
    if not a_times or not b_times:
        return 0, [], list(a_times)
    
    hits = 0
    hit_examples = []
    miss_examples = []
    
    for t_a in a_times:
        # Find first B event in window (t_a, t_a + dt_ms]
        start_idx = bisect.bisect_right(b_times, t_a)
        end_idx = bisect.bisect_right(b_times, t_a + dt_ms)
        
        if start_idx < end_idx:
            # Found at least one B in window
            t_b = b_times[start_idx]  # take first B
            latency_ms = t_b - t_a
            hits += 1
            
            # Collect evidence
            if len(hit_examples) < 10:  # limit evidence collection
                hit_examples.append((t_a, t_b, latency_ms))
        else:
            # No B found in window
            if len(miss_examples) < 10:
                miss_examples.append(t_a)
    
    return hits, hit_examples, miss_examples


def _calculate_baseline_pb(
    b_key: str,
    events: EventStreamType,
    dt_sec: int
) -> float:
    """Calculate baseline probability of B occurring in a random time window."""
    if not events:
        return 0.0
    
    # Get observation period
    events.sort(key=lambda e: e.ts)
    total_period_ms = events[-1].ts - events[0].ts
    
    if total_period_ms <= 0:
        return 0.0
    
    # Count B events
    b_count = sum(1 for e in events if e.key == b_key)
    
    # Estimate P(B in random dt_sec window) using window-based baseline
    dt_ms = dt_sec * 1000
    num_windows = max(1, total_period_ms // dt_ms)
    
    return min(1.0, b_count / num_windows)


def _calculate_rule_quality(
    n_a: int,
    n_ab: int, 
    baseline_p_b: float
) -> dict[str, float]:
    """Calculate quality metrics for a rule."""
    if n_a == 0:
        return {"confidence": 0.0, "confidence_lb": 0.0, "lift": 1.0, "leverage": 0.0}
    
    confidence = n_ab / n_a
    confidence_lb = _wilson_lower_bound(n_ab, n_a)
    
    lift = confidence / max(0.001, baseline_p_b)  # avoid division by zero
    leverage = confidence - baseline_p_b
    
    # Conviction: (1-P(B))/(1-confidence)
    conviction = None
    if confidence < 1.0 and baseline_p_b < 1.0:
        conviction = (1 - baseline_p_b) / (1 - confidence)
    
    return {
        "confidence": confidence,
        "confidence_lb": confidence_lb,
        "lift": lift,
        "leverage": leverage,
        "conviction": conviction,
    }


def _create_rule_evidence(
    hit_examples: list[tuple[int, int, int]],
    miss_examples: list[int],
    max_examples: int = 5
) -> RuleEvidence:
    """Create evidence object for explainability."""
    # Limit examples
    hit_examples = hit_examples[:max_examples]
    miss_examples = miss_examples[:max_examples]
    
    # Calculate latency statistics
    latencies_sec = [latency_ms / 1000 for _, _, latency_ms in hit_examples]
    quantiles = []
    
    if latencies_sec:
        try:
            quantiles = [
                statistics.quantiles(latencies_sec, n=4)[0],  # 25th percentile
                statistics.median(latencies_sec),             # 50th percentile  
                statistics.quantiles(latencies_sec, n=4)[2],  # 75th percentile
                statistics.quantiles(latencies_sec, n=10)[8], # 90th percentile
                statistics.quantiles(latencies_sec, n=100)[98] # 99th percentile
            ]
        except Exception:
            # Fallback for small sample sizes
            quantiles = [min(latencies_sec), statistics.median(latencies_sec), max(latencies_sec)]
    
    return RuleEvidence(
        hit_examples=hit_examples,
        miss_examples=miss_examples,
        latency_quantiles=quantiles
    )


def mine_ab_rules(
    events: EventStreamType,
    config: MiningConfig
) -> RulesType:
    """Mine A→B rules from event stream using the specified configuration."""
    _LOGGER.info("Starting A→B rule mining with %d events", len(events))
    
    # Preprocessing
    events = _filter_events(events, config)
    events = _deduplicate_events(events, config)
    
    if len(events) < config.min_support_A:
        _LOGGER.warning("Too few events after preprocessing: %d", len(events))
        return []
    
    # Get frequent event candidates
    a_candidates, b_candidates = _get_frequent_events(
        events, config.min_support_A, config.min_support_B
    )
    
    if not a_candidates or not b_candidates:
        _LOGGER.warning("No frequent events found")
        return []
    
    # Create time indices for efficient lookup
    indices = _create_event_indices(events)
    
    # Calculate observation period
    events.sort(key=lambda e: e.ts)
    observation_period_ms = events[-1].ts - events[0].ts
    observation_period_days = max(1, observation_period_ms // (24 * 3600 * 1000))
    
    # Mine rules for each time window
    all_rules = []
    
    for dt_sec in config.windows:
        _LOGGER.debug("Mining rules for time window: %d seconds", dt_sec)
        dt_ms = dt_sec * 1000
        
        for a_key in a_candidates:
            for b_key in b_candidates:
                # Apply self-rule filters
                if config.exclude_self_rules and a_key == b_key:
                    continue
                
                if config.exclude_same_entity:
                    a_entity = a_key.split(':')[0] if ':' in a_key else a_key
                    b_entity = b_key.split(':')[0] if ':' in b_key else b_key
                    if a_entity == b_entity:
                        continue
                
                # Count hits and evidence
                n_ab, hit_examples, miss_examples = _count_ab_hits(
                    a_key, b_key, dt_ms, indices
                )
                
                n_a = len(indices.get(a_key, []))
                n_b = len(indices.get(b_key, []))
                
                # Apply minimum thresholds
                if n_ab < config.min_hits:
                    continue
                
                # Calculate quality metrics
                baseline_p_b = _calculate_baseline_pb(b_key, events, dt_sec)
                quality = _calculate_rule_quality(n_a, n_ab, baseline_p_b)
                
                # Apply quality filters
                if quality["confidence"] < config.min_confidence:
                    continue
                if quality["confidence_lb"] < config.min_confidence_lb:
                    continue
                if quality["lift"] < config.min_lift:
                    continue
                if quality["leverage"] < config.min_leverage:
                    continue
                
                # Create evidence
                evidence = _create_rule_evidence(hit_examples, miss_examples, 
                                               config.max_evidence_examples)
                
                # Create rule
                rule = Rule(
                    A=a_key,
                    B=b_key,
                    dt_sec=dt_sec,
                    nA=n_a,
                    nB=n_b,
                    nAB=n_ab,
                    confidence=quality["confidence"],
                    confidence_lb=quality["confidence_lb"],
                    lift=quality["lift"],
                    leverage=quality["leverage"],
                    conviction=quality["conviction"],
                    observation_period_days=observation_period_days,
                    baseline_p_b=baseline_p_b,
                    evidence=evidence
                )
                
                all_rules.append(rule)
    
    # Sort by score and limit
    all_rules.sort(key=lambda r: r.score(), reverse=True)
    final_rules = all_rules[:config.max_rules]
    
    _LOGGER.info(
        "Mining complete: found %d rules (limited to %d)",
        len(all_rules), len(final_rules)
    )
    
    return final_rules


def mine_with_context_stratification(
    events: EventStreamType,
    config: MiningConfig
) -> RulesType:
    """Mine rules with context stratification (optional v0.1 feature)."""
    if not config.context_features:
        return mine_ab_rules(events, config)
    
    _LOGGER.info("Mining with context stratification: %s", config.context_features)
    
    # Group events by context
    context_groups: dict[str, EventStreamType] = defaultdict(list)
    global_events = []
    
    for event in events:
        context_bucket = _extract_context(event, config.context_features)
        if context_bucket:
            context_groups[context_bucket].append(event)
        global_events.append(event)  # Also include in global
    
    # Mine global rules
    global_rules = mine_ab_rules(global_events, config)
    
    # Mine context-specific rules
    for context, ctx_events in context_groups.items():
        if len(ctx_events) < config.min_support_A:
            continue
        
        _LOGGER.debug("Mining context '%s' with %d events", context, len(ctx_events))
        ctx_rules = mine_ab_rules(ctx_events, config)
        
        # TODO: Attach context variants to global rules in v0.2
        # For v0.1, we just mine separately
        for rule in ctx_rules:
            rule.A = f"{rule.A}@{context}"
            rule.B = f"{rule.B}@{context}"
        
        global_rules.extend(ctx_rules)
    
    # Re-sort and limit
    global_rules.sort(key=lambda r: r.score(), reverse=True)
    return global_rules[:config.max_rules]