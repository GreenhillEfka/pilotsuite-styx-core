"""Collective Intelligence Models."""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from enum import Enum


class AggregationMethod(Enum):
    """Federated aggregation strategies."""
    FEDERATED_AVERAGING = "fed_avg"
    FEDERATED_MEDIAN = "fed_median"
    FEDERATED_TRIMMED_MEAN = "fed_trimmed_mean"
    WEIGHTED_AVERAGE = "weighted_avg"


@dataclass
class ModelUpdate:
    """Represents a local model update from a participating node."""
    node_id: str
    model_version: str
    weights: Dict[str, Any]  # Model weights as dict
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    privacy_budget: float = 1.0  # Used for differential privacy
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelUpdate":
        """Create from dictionary."""
        return cls(**data)

    @property
    def update_id(self) -> str:
        """Generate unique ID for this update."""
        content = f"{self.node_id}:{self.model_version}:{self.timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class AggregatedModel:
    """Represents the aggregated global model."""
    model_version: str
    weights: Dict[str, Any]
    aggregation_method: AggregationMethod
    participants: List[str]
    metrics: Dict[str, float]
    timestamp: float = field(default_factory=time.time)
    privacy_loss: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_version": self.model_version,
            "weights": self.weights,
            "aggregation_method": self.aggregation_method.value,
            "participants": self.participants,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
            "privacy_loss": self.privacy_loss,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AggregatedModel":
        """Create from dictionary."""
        if "aggregation_method" in data:
            data["aggregation_method"] = AggregationMethod(data["aggregation_method"])
        return cls(**data)


@dataclass
class FederatedRound:
    """Represents one round of federated learning."""
    round_id: str
    model_version: str
    participating_nodes: List[str]
    updates: List[ModelUpdate]
    aggregated_model: Optional[AggregatedModel] = None
    timestamp_start: float = field(default_factory=time.time)
    timestamp_end: Optional[float] = None

    def complete(self, aggregated: AggregatedModel):
        """Mark round as complete with aggregated model."""
        self.aggregated_model = aggregated
        self.timestamp_end = time.time()

    @property
    def round_duration(self) -> Optional[float]:
        """Get duration in seconds."""
        if self.timestamp_end:
            return self.timestamp_end - self.timestamp_start
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "round_id": self.round_id,
            "model_version": self.model_version,
            "participating_nodes": self.participating_nodes,
            "updates": [u.to_dict() for u in self.updates],
            "aggregated_model": self.aggregated_model.to_dict() if self.aggregated_model else None,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "round_duration": self.round_duration,
        }


@dataclass
class KnowledgeItem:
    """Represents transferable knowledge between homes."""
    knowledge_id: str
    source_node_id: str
    knowledge_type: str  # e.g., "habitus_pattern", "energy_saving", "mood_prediction"
    payload: Dict[str, Any]
    confidence: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def knowledge_hash(self) -> str:
        """Generate hash for deduplication."""
        content = json.dumps(self.payload, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeItem":
        """Create from dictionary."""
        return cls(**data)
