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
    
    def score(self, w_conf: float = 0.5, w_lift: float = 0.3, w_evidence: float = 0.2) -> float:
        """Combined score for ranking rules."""
        import math
        conf_score = self.confidence_lb  # stable confidence
        lift_score = math.log(max(1.01, self.lift))  # log lift (diminishing returns)
        evidence_score = math.log(1 + self.nAB)  # log evidence count
        
        return (w_conf * conf_score + 
                w_lift * lift_score + 
                w_evidence * evidence_score)


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