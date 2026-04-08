"""
Candidate Management Module - Automation suggestion lifecycle.

This module handles the complete lifecycle of automation suggestions:
- Discovery: Patterns from brain graph → candidate creation
- Presentation: Candidates → HA Repairs UI 
- Action: User accepts/dismisses/defers → state updates
- Cleanup: Remove old accepted/dismissed candidates

Privacy-first: All data stored locally, no external transmission.
"""

from .store import Candidate, CandidateStore, CandidateState
from .api import candidates_bp, init_candidates_api

__all__ = [
    "Candidate", 
    "CandidateStore", 
    "CandidateState",
    "candidates_bp", 
    "init_candidates_api"
]