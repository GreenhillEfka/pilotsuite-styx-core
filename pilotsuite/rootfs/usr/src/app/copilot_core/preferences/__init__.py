"""Preferences Package — Multi-User Preference System.

This package provides a complete multi-user preference system with:
- Per-user preference storage (user_profiles.py)
- Context-aware recommendations (context_aware.py)
- Multi-user conflict resolution (conflict_resolution.py)
- Preference learning from behavior (learning.py)

Architecture:
    preferences/
        __init__.py       — package exports and get_preferences() factory
        user_profiles.py  — UserProfile dataclass + UserProfiles manager
        context_aware.py  — Context-aware preference matching
        conflict_resolution.py — Multi-user conflict detection/resolution
        learning.py       — Behavioral preference learning

All modules are privacy-first: data remains local, no external API calls.
"""
from __future__ import annotations

from copilot_core.preferences.user_profiles import (
    UserProfile,
    UserProfiles,
    get_user_profiles,
    init_user_profiles,
)
from copilot_core.preferences.context_aware import (
    ContextAwareMatcher,
    get_context_aware_matcher,
)
from copilot_core.preferences.conflict_resolution import (
    ConflictDetail,
    ConflictState,
    ConflictResolver,
    get_conflict_resolver,
    init_conflict_resolver,
)
from copilot_core.preferences.learning import (
    BehavioralLearner,
    get_behavioral_learner,
    init_behavioral_learner,
)

__all__ = [
    # user_profiles
    "UserProfile",
    "UserProfiles",
    "get_user_profiles",
    "init_user_profiles",
    # context_aware
    "ContextAwareMatcher",
    "get_context_aware_matcher",
    # conflict_resolution
    "ConflictDetail",
    "ConflictState",
    "ConflictResolver",
    "get_conflict_resolver",
    "init_conflict_resolver",
    # learning
    "BehavioralLearner",
    "get_behavioral_learner",
    "init_behavioral_learner",
]
