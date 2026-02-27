"""Data models for Habitus Miner v0.1."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class NormEvent:
    """Normalized event for mining.
    
    Represents a discrete state transition at a specific timestamp.
    """
    ts: int  # timestamp in milliseconds 
    key: str  # normalized event key: "entity_id:transition" (e.g., "light.kitchen:on")
    entity_id: str
    domain: str  
    transition: str  # e.g., "on", "off", ":on", ":off"
    context: dict[str, str] | None = None
    
    def __post_init__(self):
        # Ensure key format consistency
        if ":" not in self.key:
            self.key = f"{self.entity_id}:{self.transition}"


@dataclass 
class RuleEvidence:
    """Evidence and explainability data for a rule."""
    hit_examples: list[tuple[int, int, int]]  # (tA, tB, latency_ms) for top hits
    miss_examples: list[int]  # tA timestamps where A occurred but no B followed
    latency_quantiles: list[float]  # [p25, p50, p75, p90, p99] in seconds
    latency_histogram: dict[str, int] | None = None  # bucket_label -> count
    context_stats: dict[str, dict[str, Any]] | None = None  # context bucket -> stats


@dataclass
class Rule:
    """A discovered A→B rule with quality metrics and explainability."""
    A: str  # event key for antecedent 
    B: str  # event key for consequent
    dt_sec: int  # time window in seconds
    
    # Count statistics
    nA: int  # total A events (trials)
    nB: int  # total B events (for baseline)
    nAB: int  # A events followed by B within window (hits)
    
    # Quality metrics
    confidence: float  # P(B|A) = nAB / nA
    confidence_lb: float  # Wilson lower bound for stability
    lift: float  # confidence / P(B)
    leverage: float  # P(A,B) - P(A)*P(B)
    
    # Metadata (non-default fields must come first)
    observation_period_days: int
    baseline_p_b: float  # baseline probability of B
    conviction: float | None = None  # (1-P(B))/(1-confidence)
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    
    # Evidence for explainability
    evidence: RuleEvidence | None = None
    
    # Context-specific rules (if context stratification was used)
    context_variants: dict[str, 'Rule'] | None = None
    
    def score(self, w_conf: float = 0.35, w_lift: float = 0.25,
              w_evidence: float = 0.20, w_stability: float = 0.20) -> float:
        """Combined score for ranking rules using multi-criteria Bayesian approach.

        Components:
        1. Confidence (Wilson LB): stable confidence estimate (lower bound)
        2. Lift (log): information gain over baseline (diminishing returns)
        3. Evidence (log): sample size credibility
        4. Stability: temporal consistency (rules seen across multiple days)

        The score function is designed so that:
        - High confidence alone isn't enough (could be low-support noise)
        - High lift alone isn't enough (could be rare coincidence)
        - Both together with evidence across days → strong pattern
        """
        import math

        # Wilson LB confidence: already accounts for sample size uncertainty
        conf_score = self.confidence_lb

        # Log-lift: diminishing returns for very high lift
        # log(1) = 0 for lift=1 (no improvement), increases smoothly
        lift_score = math.log(max(1.01, self.lift))
        # Normalize to ~[0, 1] range (lift rarely exceeds ~20)
        lift_score = min(1.0, lift_score / 3.0)

        # Log-evidence: credibility from sample size
        # log(1+n) gives diminishing returns for large n
        evidence_score = math.log(1 + self.nAB)
        # Normalize: 10 hits → ~0.6, 50 hits → ~0.85, 100 hits → ~0.92
        evidence_score = min(1.0, evidence_score / math.log(1 + 100))

        # Temporal stability: days observed vs total observation period
        # A rule seen on 3 days out of 7 is more reliable than 3 out of 3
        if self.observation_period_days > 0:
            # Estimate days with hits (rough: nAB / avg_hits_per_active_day)
            est_active_days = min(
                self.observation_period_days,
                max(1, self.nAB / max(1, self.nA / max(1, self.observation_period_days)))
            )
            stability = est_active_days / self.observation_period_days
            # Prefer rules that appear consistently (>50% of days)
            stability = 1.0 / (1.0 + math.exp(-6.0 * (stability - 0.4)))
        else:
            stability = 0.5

        return (w_conf * conf_score +
                w_lift * lift_score +
                w_evidence * evidence_score +
                w_stability * stability)


@dataclass
class MiningConfig:
    """Configuration for the mining process."""
    # Time windows to try (in seconds)
    windows: list[int] = field(default_factory=lambda: [30, 120, 600, 3600])
    
    # Minimum support thresholds
    min_support_A: int = 20  # minimum A events needed
    min_support_B: int = 20  # minimum B events needed  
    min_hits: int = 10       # minimum AB hits needed
    
    # Quality filters
    min_confidence: float = 0.5
    min_confidence_lb: float = 0.3  # Wilson lower bound threshold
    min_lift: float = 1.2
    min_leverage: float = 0.05
    
    # Output limits
    max_rules: int = 200
    max_evidence_examples: int = 5
    
    # Deduplication/debouncing (seconds)
    entity_cooldown: dict[str, int] = field(default_factory=dict)  # entity -> cooldown_sec
    default_cooldown: int = 2  # default cooldown for state flapping
    
    # Context features for stratification
    context_features: list[str] = field(default_factory=list)  # e.g., ["time_of_day", "weekday"]
    
    # Domain/entity filters
    include_domains: list[str] | None = None
    exclude_domains: list[str] | None = None 
    include_entities: list[str] | None = None
    exclude_entities: list[str] | None = None
    
    # Anti-noise settings
    exclude_self_rules: bool = True  # exclude A==B rules
    exclude_same_entity: bool = False  # exclude rules within same entity
    min_stability_days: int = 3  # rule must appear across multiple days
    
    # Privacy settings
    anonymize_entity_ids: bool = False  # replace with domain-based labels


EventStreamType = list[NormEvent]
RulesType = list[Rule]