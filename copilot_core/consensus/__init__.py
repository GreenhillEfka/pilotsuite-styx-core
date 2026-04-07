"""
Consensus Engine for Agent Decision-Making

Provides voting mechanisms, decision logging, and auto-resolution
for multi-agent consensus in the PilotSuite ecosystem.
"""

from .consensus_engine import (
    ConsensusEngine,
    Decision,
    VoteType,
    VoteWeight,
    DecisionStatus,
    DecisionLog,
)

__all__ = [
    "ConsensusEngine",
    "Decision",
    "VoteType",
    "VoteWeight",
    "DecisionStatus",
    "DecisionLog",
]
