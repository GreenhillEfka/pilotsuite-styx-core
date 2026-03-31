"""Feature Flags Advanced Engine — Slice 59.

Advanced feature flags for PilotSuite Core.

Features:
- Boolean and percentage rollouts
- User targeting
- A/B testing support
- Scheduled rollouts
- Flag dependencies
- Flag variants
- Evaluation context
"""
from __future__ import annotations

import logging
import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class FlagType(Enum):
    """Feature flag types."""
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    VARIANT = "variant"
    NUMERIC = "numeric"
    STRING = "string"
    JSON = "json"


class RolloutStrategy(Enum):
    """Rollout strategies."""
    ALL = "all"
    NONE = "none"
    PERCENTAGE = "percentage"
    USER_TARGETING = "user_targeting"
    SCHEDULED = "scheduled"
    CANARY = "canary"


@dataclass
class FlagVariant:
    """Flag variant for A/B testing."""
    variant_id: str
    name: str
    value: Any
    weight: float = 0.0  # 0.0-1.0
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "value": self.value,
            "weight": self.weight,
            "description": self.description,
        }


@dataclass
class FeatureFlag:
    """Feature flag definition."""
    flag_id: str
    name: str
    flag_type: FlagType
    default_value: Any
    enabled: bool = True
    rollout_strategy: RolloutStrategy = RolloutStrategy.ALL
    rollout_percentage: float = 100.0
    target_users: Set[str] = field(default_factory=set)
    excluded_users: Set[str] = field(default_factory=set)
    variants: List[FlagVariant] = field(default_factory=list)
    schedule_start: Optional[str] = None
    schedule_end: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "flag_id": self.flag_id,
            "name": self.name,
            "flag_type": self.flag_type.value,
            "default_value": self.default_value,
            "enabled": self.enabled,
            "rollout_strategy": self.rollout_strategy.value,
            "rollout_percentage": self.rollout_percentage,
            "target_users": list(self.target_users),
            "excluded_users": list(self.excluded_users),
            "variants": [v.to_dict() for v in self.variants],
            "schedule_start": self.schedule_start,
            "schedule_end": self.schedule_end,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class EvaluationResult:
    """Flag evaluation result."""
    flag_id: str
    value: Any
    variant_id: Optional[str] = None
    reason: str = "default"
    flag_enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "flag_id": self.flag_id,
            "value": self.value,
            "variant_id": self.variant_id,
            "reason": self.reason,
            "flag_enabled": self.flag_enabled,
        }


class FeatureFlagsEngine:
    """Advanced feature flags engine."""
    
    def __init__(self):
        self._flags: Dict[str, FeatureFlag] = {}
        self._evaluation_cache: Dict[str, Dict[str, EvaluationResult]] = {}
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_evaluations": 0,
            "enabled_evaluations": 0,
            "disabled_evaluations": 0,
            "by_flag": {},
            "by_variant": {},
        }
    
    def create_flag(self, name: str, flag_type: FlagType,
                   default_value: Any,
                   rollout_strategy: RolloutStrategy = RolloutStrategy.ALL,
                   rollout_percentage: float = 100.0,
                   variants: Optional[List[FlagVariant]] = None,
                   dependencies: Optional[List[str]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a feature flag."""
        flag_id = f"flag_{uuid.uuid4().hex[:16]}"
        
        flag = FeatureFlag(
            flag_id=flag_id,
            name=name,
            flag_type=flag_type,
            default_value=default_value,
            rollout_strategy=rollout_strategy,
            rollout_percentage=rollout_percentage,
            variants=variants or [],
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        
        with self._lock:
            self._flags[flag_id] = flag
        
        logger.info("Feature flag created: %s (%s)", name, flag_id)
        
        return flag_id
    
    def create_boolean_flag(self, name: str, default: bool = False,
                           rollout_percentage: float = 100.0) -> str:
        """Create a boolean feature flag."""
        return self.create_flag(
            name=name,
            flag_type=FlagType.BOOLEAN,
            default_value=default,
            rollout_percentage=rollout_percentage,
        )
    
    def create_percentage_flag(self, name: str, percentage: float,
                              default_value: Any = True) -> str:
        """Create a percentage rollout flag."""
        return self.create_flag(
            name=name,
            flag_type=FlagType.PERCENTAGE,
            default_value=default_value,
            rollout_strategy=RolloutStrategy.PERCENTAGE,
            rollout_percentage=percentage,
        )
    
    def create_variant_flag(self, name: str, variants: List[FlagVariant],
                           default_value: Any = None) -> str:
        """Create a variant flag for A/B testing."""
        # Normalize weights if needed
        total_weight = sum(v.weight for v in variants)
        if total_weight > 0 and total_weight != 1.0:
            for v in variants:
                v.weight = v.weight / total_weight
        
        return self.create_flag(
            name=name,
            flag_type=FlagType.VARIANT,
            default_value=default_value,
            rollout_strategy=RolloutStrategy.PERCENTAGE,
            rollout_percentage=100.0,
            variants=variants,
        )
    
    def update_flag(self, flag_id: str,
                   name: Optional[str] = None,
                   enabled: Optional[bool] = None,
                   rollout_percentage: Optional[float] = None,
                   target_users: Optional[Set[str]] = None,
                   excluded_users: Optional[Set[str]] = None,
                   schedule_start: Optional[str] = None,
                   schedule_end: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update feature flag."""
        with self._lock:
            flag = self._flags.get(flag_id)
            
            if not flag:
                return False
            
            if name is not None:
                flag.name = name
            if enabled is not None:
                flag.enabled = enabled
            if rollout_percentage is not None:
                flag.rollout_percentage = rollout_percentage
            if target_users is not None:
                flag.target_users = target_users
            if excluded_users is not None:
                flag.excluded_users = excluded_users
            if schedule_start is not None:
                flag.schedule_start = schedule_start
            if schedule_end is not None:
                flag.schedule_end = schedule_end
            if metadata is not None:
                flag.metadata = metadata
            
            flag.updated_at = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def delete_flag(self, flag_id: str) -> bool:
        """Delete feature flag."""
        with self._lock:
            if flag_id not in self._flags:
                return False
            
            del self._flags[flag_id]
            
            # Clear cache
            if flag_id in self._evaluation_cache:
                del self._evaluation_cache[flag_id]
        
        return True
    
    def get_flag(self, flag_id: str) -> Optional[FeatureFlag]:
        """Get flag by ID."""
        return self._flags.get(flag_id)
    
    def list_flags(self, enabled: Optional[bool] = None,
                  flag_type: Optional[FlagType] = None) -> List[FeatureFlag]:
        """List flags with filters."""
        with self._lock:
            flags = list(self._flags.values())
            
            if enabled is not None:
                flags = [f for f in flags if f.enabled == enabled]
            
            if flag_type is not None:
                flags = [f for f in flags if f.flag_type == flag_type]
            
            return flags
    
    def evaluate(self, flag_id: str, user_id: Optional[str] = None,
                context: Optional[Dict[str, Any]] = None,
                use_cache: bool = True) -> EvaluationResult:
        """Evaluate feature flag for user."""
        flag = self._flags.get(flag_id)
        
        if not flag:
            return EvaluationResult(
                flag_id=flag_id,
                value=None,
                reason="flag_not_found",
                flag_enabled=False,
            )
        
        # Check cache
        cache_key = user_id or "default"
        if use_cache and flag_id in self._evaluation_cache:
            if cache_key in self._evaluation_cache[flag_id]:
                self._stats["total_evaluations"] += 1
                return self._evaluation_cache[flag_id][cache_key]
        
        # Evaluate flag
        result = self._evaluate_flag(flag, user_id, context or {})
        
        # Update statistics
        self._stats["total_evaluations"] += 1
        self._stats["by_flag"][flag_id] = self._stats["by_flag"].get(flag_id, 0) + 1
        
        if result.flag_enabled:
            self._stats["enabled_evaluations"] += 1
        else:
            self._stats["disabled_evaluations"] += 1
        
        if result.variant_id:
            self._stats["by_variant"][result.variant_id] = \
                self._stats["by_variant"].get(result.variant_id, 0) + 1
        
        # Cache result
        if use_cache:
            if flag_id not in self._evaluation_cache:
                self._evaluation_cache[flag_id] = {}
            self._evaluation_cache[flag_id][cache_key] = result
        
        return result
    
    def _evaluate_flag(self, flag: FeatureFlag, user_id: Optional[str],
                      context: Dict[str, Any]) -> EvaluationResult:
        """Internal flag evaluation."""
        # Check if flag is enabled
        if not flag.enabled:
            return EvaluationResult(
                flag_id=flag.flag_id,
                value=flag.default_value,
                reason="flag_disabled",
                flag_enabled=False,
            )
        
        # Check schedule
        if not self._check_schedule(flag):
            return EvaluationResult(
                flag_id=flag.flag_id,
                value=flag.default_value,
                reason="outside_schedule",
                flag_enabled=False,
            )
        
        # Check dependencies
        if not self._check_dependencies(flag):
            return EvaluationResult(
                flag_id=flag.flag_id,
                value=flag.default_value,
                reason="dependency_not_met",
                flag_enabled=False,
            )
        
        # Check excluded users
        if user_id and user_id in flag.excluded_users:
            return EvaluationResult(
                flag_id=flag.flag_id,
                value=flag.default_value,
                reason="user_excluded",
                flag_enabled=False,
            )
        
        # Check rollout strategy
        if flag.rollout_strategy == RolloutStrategy.NONE:
            return EvaluationResult(
                flag_id=flag.flag_id,
                value=flag.default_value,
                reason="rollout_none",
                flag_enabled=False,
            )
        
        if flag.rollout_strategy == RolloutStrategy.ALL:
            return self._get_flag_value(flag, None)
        
        if flag.rollout_strategy == RolloutStrategy.USER_TARGETING:
            if user_id and user_id in flag.target_users:
                return self._get_flag_value(flag, None)
            else:
                return EvaluationResult(
                    flag_id=flag.flag_id,
                    value=flag.default_value,
                    reason="user_not_targeted",
                    flag_enabled=False,
                )
        
        if flag.rollout_strategy == RolloutStrategy.PERCENTAGE:
            if self._check_percentage(flag, user_id):
                return self._get_flag_value(flag, None)
            else:
                return EvaluationResult(
                    flag_id=flag.flag_id,
                    value=flag.default_value,
                    reason="percentage_rollout",
                    flag_enabled=False,
                )
        
        if flag.rollout_strategy == RolloutStrategy.CANARY:
            # Canary is similar to percentage but with variants
            return self._evaluate_variant(flag, user_id)
        
        # Default: return value based on flag type
        return self._get_flag_value(flag, None)
    
    def _check_schedule(self, flag: FeatureFlag) -> bool:
        """Check if current time is within schedule."""
        now = datetime.now(timezone.utc)
        
        if flag.schedule_start:
            start = datetime.fromisoformat(flag.schedule_start.replace('Z', '+00:00'))
            if now < start:
                return False
        
        if flag.schedule_end:
            end = datetime.fromisoformat(flag.schedule_end.replace('Z', '+00:00'))
            if now > end:
                return False
        
        return True
    
    def _check_dependencies(self, flag: FeatureFlag) -> bool:
        """Check if all dependencies are enabled."""
        for dep_id in flag.dependencies:
            dep_flag = self._flags.get(dep_id)
            
            if not dep_flag or not dep_flag.enabled:
                return False
        
        return True
    
    def _check_percentage(self, flag: FeatureFlag, user_id: Optional[str]) -> bool:
        """Check if user falls within percentage rollout."""
        if not user_id:
            # For anonymous users, use random
            import random
            return random.random() * 100 < flag.rollout_percentage
        
        # Consistent hashing based on user_id
        hash_value = int(hashlib.md5(f"{flag.flag_id}:{user_id}".encode()).hexdigest(), 16)
        bucket = (hash_value % 10000) / 100  # 0-100 with 2 decimals
        
        return bucket < flag.rollout_percentage
    
    def _evaluate_variant(self, flag: FeatureFlag,
                         user_id: Optional[str]) -> EvaluationResult:
        """Evaluate variant flag for A/B testing."""
        if not flag.variants:
            return self._get_flag_value(flag, None)
        
        if not user_id:
            # Random variant for anonymous users
            import random
            variant = self._select_variant_random(flag.variants, random.random())
            return EvaluationResult(
                flag_id=flag.flag_id,
                value=variant.value,
                variant_id=variant.variant_id,
                reason="variant_random",
                flag_enabled=True,
            )
        
        # Consistent variant selection based on user_id
        hash_value = int(hashlib.md5(f"{flag.flag_id}:{user_id}".encode()).hexdigest(), 16)
        bucket = (hash_value % 10000) / 100  # 0-100
        
        variant = self._select_variant_by_bucket(flag.variants, bucket)
        
        return EvaluationResult(
            flag_id=flag.flag_id,
            value=variant.value,
            variant_id=variant.variant_id,
            reason="variant_assigned",
            flag_enabled=True,
        )
    
    def _select_variant_random(self, variants: List[FlagVariant],
                               random_value: float) -> FlagVariant:
        """Select variant randomly based on weights."""
        cumulative = 0.0
        
        for variant in variants:
            cumulative += variant.weight
            if random_value <= cumulative:
                return variant
        
        return variants[-1]
    
    def _select_variant_by_bucket(self, variants: List[FlagVariant],
                                  bucket: float) -> FlagVariant:
        """Select variant by bucket (consistent hashing)."""
        cumulative = 0.0
        
        for variant in variants:
            cumulative += variant.weight * 100
            if bucket < cumulative:
                return variant
        
        return variants[-1]
    
    def _get_flag_value(self, flag: FeatureFlag,
                       variant_id: Optional[str]) -> EvaluationResult:
        """Get flag value based on type."""
        if flag.flag_type == FlagType.BOOLEAN:
            return EvaluationResult(
                flag_id=flag.flag_id,
                value=bool(flag.default_value),
                variant_id=variant_id,
                reason="flag_enabled",
                flag_enabled=True,
            )
        
        elif flag.flag_type == FlagType.VARIANT:
            # Should have been handled by _evaluate_variant
            return EvaluationResult(
                flag_id=flag.flag_id,
                value=flag.default_value,
                variant_id=variant_id,
                reason="default",
                flag_enabled=True,
            )
        
        else:
            return EvaluationResult(
                flag_id=flag.flag_id,
                value=flag.default_value,
                variant_id=variant_id,
                reason="flag_enabled",
                flag_enabled=True,
            )
    
    def is_enabled(self, flag_id: str, user_id: Optional[str] = None,
                  context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if flag is enabled for user."""
        result = self.evaluate(flag_id, user_id, context)
        
        if result.flag_enabled:
            # For boolean flags, also check the value
            if isinstance(result.value, bool):
                return result.value
            return True
        
        return False
    
    def get_value(self, flag_id: str, user_id: Optional[str] = None,
                 default: Any = None,
                 context: Optional[Dict[str, Any]] = None) -> Any:
        """Get flag value for user."""
        result = self.evaluate(flag_id, user_id, context)
        
        if result.value is not None:
            return result.value
        
        return default
    
    def add_target_user(self, flag_id: str, user_id: str) -> bool:
        """Add user to target list."""
        with self._lock:
            flag = self._flags.get(flag_id)
            
            if not flag:
                return False
            
            flag.target_users.add(user_id)
            flag.updated_at = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def remove_target_user(self, flag_id: str, user_id: str) -> bool:
        """Remove user from target list."""
        with self._lock:
            flag = self._flags.get(flag_id)
            
            if not flag:
                return False
            
            flag.target_users.discard(user_id)
            flag.updated_at = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def add_excluded_user(self, flag_id: str, user_id: str) -> bool:
        """Add user to excluded list."""
        with self._lock:
            flag = self._flags.get(flag_id)
            
            if not flag:
                return False
            
            flag.excluded_users.add(user_id)
            flag.updated_at = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def remove_excluded_user(self, flag_id: str, user_id: str) -> bool:
        """Remove user from excluded list."""
        with self._lock:
            flag = self._flags.get(flag_id)
            
            if not flag:
                return False
            
            flag.excluded_users.discard(user_id)
            flag.updated_at = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def add_variant(self, flag_id: str, variant: FlagVariant) -> bool:
        """Add variant to flag."""
        with self._lock:
            flag = self._flags.get(flag_id)
            
            if not flag:
                return False
            
            if flag.flag_type != FlagType.VARIANT:
                return False
            
            flag.variants.append(variant)
            flag.updated_at = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def clear_cache(self, flag_id: Optional[str] = None) -> int:
        """Clear evaluation cache."""
        with self._lock:
            if flag_id:
                if flag_id in self._evaluation_cache:
                    count = len(self._evaluation_cache[flag_id])
                    del self._evaluation_cache[flag_id]
                    return count
                return 0
            else:
                count = sum(len(cache) for cache in self._evaluation_cache.values())
                self._evaluation_cache.clear()
                return count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get feature flags statistics."""
        with self._lock:
            return {
                **self._stats,
                "total_flags": len(self._flags),
                "enabled_flags": len([f for f in self._flags.values() if f.enabled]),
                "cached_evaluations": sum(len(c) for c in self._evaluation_cache.values()),
            }


def create_feature_flags_engine() -> FeatureFlagsEngine:
    """Factory function to create feature flags engine."""
    return FeatureFlagsEngine()
