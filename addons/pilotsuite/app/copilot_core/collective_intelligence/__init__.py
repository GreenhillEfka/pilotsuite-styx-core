"""Collective Intelligence Module – Phase 5.

Implements:
- Federated Learning: Dezentrales Lernen ohne Daten-Sharing
- Model Aggregation: Zusammenführung lokaler Modelle
- Privacy-Preserving Patterns: Differential Privacy
- Knowledge Transfer: Cross-Home Knowledge Sharing

Features:
- Local Model Training
- Secure Aggregation Protocol
- Model Versioning
- Federated Averaging
"""

from .service import CollectiveIntelligenceService
from .federated_learner import FederatedLearner
from .model_aggregator import ModelAggregator
from .privacy_preserver import PrivacyAwareAggregator
from .knowledge_transfer import KnowledgeTransfer

__all__ = [
    "CollectiveIntelligenceService",
    "FederatedLearner",
    "ModelAggregator",
    "PrivacyAwareAggregator",
    "KnowledgeTransfer",
]
