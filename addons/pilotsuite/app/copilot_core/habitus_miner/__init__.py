"""Habitus Miner module (v0.2).

Privacy-first A→B rule discovery from Smart-Home event streams.
Focuses on explainability and anti-noise measures.

v0.2 adds zone-based mining with TagZoneIntegration.
"""

from .mining import mine_ab_rules, mine_with_context_stratification
from .model import NormEvent, Rule, MiningConfig, EventStreamType, RulesType
from .service import HabitusMinerService
from .store import HabitusMinerStore
from .zone_mining import (
    ZoneBasedMiner,
    ZoneMiningConfig,
    ZoneMiningResult,
)

__all__ = [
    # v0.1 API
    "mine_ab_rules",
    "mine_with_context_stratification",
    "NormEvent",
    "Rule",
    "MiningConfig",
    "EventStreamType",
    "RulesType",
    "HabitusMinerService",
    "HabitusMinerStore",
    # v0.2 API
    "ZoneBasedMiner",
    "ZoneMiningConfig",
    "ZoneMiningResult",
]

__version__ = "0.2.0"