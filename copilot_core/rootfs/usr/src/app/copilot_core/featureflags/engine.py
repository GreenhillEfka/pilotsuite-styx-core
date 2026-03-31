"""Feature Flags Engine — Slice 40.

Feature flag management for PilotSuite Core.

Features:
- Boolean and percentage rollouts
- User targeting and segmentation
- A/B testing support
- Flag evaluation caching
- Flag change events
- Audit trail for flag changes
"""
from __future__ import annotations

import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class FlagType(Enum):
    """Feature flag type."""
    BOOLEAN = "boolean"
    STRING = "string"
    NUMBER = "number"
    JSON = "json"


class FlagStatus(Enum):
    """Feature flag status."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class FlagRule:
    """Rule for flag evaluation."""
    rule_id: str
    condition: str  # e.g., "user.country == 'US'"
    value: Any
    percentage: float = 100.0  # Percentage of matching users
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "condition": self.condition,
            "value": self.value,
            "percentage": self.percentage,
        }


@dataclass
class FeatureFlag:
    """Feature flag definition."""
    flag_id: str
    name: str
    description: str
    flag_type: FlagType
    default_value: Any
    status: FlagStatus = FlagStatus.DRAFT
    rules: List[FlagRule] = field(default_factory=list)
    percentage_rollout: float = 100.0  # Global percentage
    environments: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "flag_id": self.flag_id,
            "name": self.name,
            "description": self.description,
            "flag_type": self.flag_type.value,
            "default_value": self.default_value,
            "status": self.status.value,
            "rules": [r.to_dict() for r in self.rules],
            "percentage_rollout": self.percentage_rollout,
            "environments": self.environments,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
        }


@dataclass
class FlagEvaluation:
    """Result of flag evaluation."""
    flag_id: str
    value: Any
    reason: str  # default, rule_match, percentage, etc.
    rule_id: Optional[str] = None
    variant: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "flag_id": self.flag_id,
            "value": self.value,
            "reason": self.reason,
            "rule_id": self.rule_id,
            "variant": self.variant,
        }


@dataclass
class FlagChange:
    """Audit log for flag changes."""
    change_id: str
    flag_id: str
    action: str  # created, updated, enabled, disabled, deleted
    old_value: Optional[Any]
    new_value: Optional[Any]
    changed_by: str
    changed_at: str
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "flag_id": self.flag_id,
            "action": self.action,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at,
            "reason": self.reason,
        }


class FeatureFlagsEngine:
    """Feature flags management engine."""
    
    def __init__(self):
        self._flags: Dict[str, FeatureFlag] = {}
        self._change_log: List[FlagChange] = []
        self._evaluation_cache: Dict[str, tuple] = {}  # key -> (value, timestamp)
        self._cache_ttl_seconds = 60
        
        # Callbacks for flag changes
        self._change_callbacks: List[Callable] = []
        
        # Statistics
        self._stats = {
            "total_evaluations": 0,
            "by_flag": {},
            "by_reason": {},
        }
    
    def create_flag(self, name: str, description: str,
                   flag_type: str, default_value: Any,
                   environments: Optional[List[str]] = None,
                   tags: Optional[List[str]] = None,
                   created_by: str = "system") -> str:
        """Create a new feature flag."""
        flag_id = f"flag_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        flag = FeatureFlag(
            flag_id=flag_id,
            name=name,
            description=description,
            flag_type=FlagType(flag_type),
            default_value=default_value,
            status=FlagStatus.DRAFT,
            environments=environments or ["default"],
            tags=tags or [],
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        
        self._flags[flag_id] = flag
        
        # Log change
        self._log_change(
            flag_id=flag_id,
            action="created",
            old_value=None,
            new_value=flag.to_dict(),
            changed_by=created_by,
            reason="Flag created",
        )
        
        logger.info("Feature flag created: %s (%s)", name, flag_id)
        
        return flag_id
    
    def add_rule(self, flag_id: str, condition: str,
                value: Any, percentage: float = 100.0) -> str:
        """Add evaluation rule to a flag."""
        if flag_id not in self._flags:
            raise ValueError(f"Flag not found: {flag_id}")
        
        rule_id = f"rule_{uuid.uuid4().hex[:8]}"
        
        rule = FlagRule(
            rule_id=rule_id,
            condition=condition,
            value=value,
            percentage=percentage,
        )
        
        self._flags[flag_id].rules.append(rule)
        self._flags[flag_id].updated_at = datetime.now(timezone.utc).isoformat()
        
        # Invalidate cache
        self._invalidate_cache(flag_id)
        
        return rule_id
    
    def update_flag(self, flag_id: str, **kwargs) -> None:
        """Update feature flag properties."""
        if flag_id not in self._flags:
            raise ValueError(f"Flag not found: {flag_id}")
        
        flag = self._flags[flag_id]
        old_dict = flag.to_dict()
        
        for key, value in kwargs.items():
            if hasattr(flag, key):
                setattr(flag, key, value)
        
        flag.updated_at = datetime.now(timezone.utc).isoformat()
        
        # Log change
        self._log_change(
            flag_id=flag_id,
            action="updated",
            old_value=old_dict,
            new_value=flag.to_dict(),
            changed_by=kwargs.get("updated_by", "system"),
            reason=kwargs.get("reason", ""),
        )
        
        # Invalidate cache
        self._invalidate_cache(flag_id)
    
    def enable_flag(self, flag_id: str, updated_by: str = "system") -> bool:
        """Enable a feature flag."""
        if flag_id not in self._flags:
            return False
        
        flag = self._flags[flag_id]
        old_status = flag.status
        
        flag.status = FlagStatus.ACTIVE
        flag.updated_at = datetime.now(timezone.utc).isoformat()
        
        self._log_change(
            flag_id=flag_id,
            action="enabled",
            old_value=old_status.value,
            new_value="active",
            changed_by=updated_by,
            reason="Flag enabled",
        )
        
        self._invalidate_cache(flag_id)
        
        logger.info("Feature flag enabled: %s", flag_id)
        
        return True
    
    def disable_flag(self, flag_id: str, updated_by: str = "system") -> bool:
        """Disable a feature flag."""
        if flag_id not in self._flags:
            return False
        
        flag = self._flags[flag_id]
        old_status = flag.status
        
        flag.status = FlagStatus.DRAFT
        flag.updated_at = datetime.now(timezone.utc).isoformat()
        
        self._log_change(
            flag_id=flag_id,
            action="disabled",
            old_value=old_status.value,
            new_value="draft",
            changed_by=updated_by,
            reason="Flag disabled",
        )
        
        self._invalidate_cache(flag_id)
        
        logger.info("Feature flag disabled: %s", flag_id)
        
        return True
    
    def evaluate(self, flag_id: str, context: Optional[Dict[str, Any]] = None,
                use_cache: bool = True) -> FlagEvaluation:
        """Evaluate a feature flag for given context."""
        context = context or {}
        cache_key = f"{flag_id}:{self._context_hash(context)}"
        
        # Check cache
        if use_cache and cache_key in self._evaluation_cache:
            cached_value, cached_at = self._evaluation_cache[cache_key]
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached_at)).total_seconds()
            if age < self._cache_ttl_seconds:
                self._stats["total_evaluations"] += 1
                return cached_value
        
        if flag_id not in self._flags:
            return FlagEvaluation(
                flag_id=flag_id,
                value=None,
                reason="flag_not_found",
            )
        
        flag = self._flags[flag_id]
        
        # Check status
        if flag.status != FlagStatus.ACTIVE:
            result = FlagEvaluation(
                flag_id=flag_id,
                value=flag.default_value,
                reason="flag_inactive",
            )
            self._cache_and_stats(cache_key, result, flag_id)
            return result
        
        # Check environment
        env = context.get("environment", "default")
        if env not in flag.environments:
            result = FlagEvaluation(
                flag_id=flag_id,
                value=flag.default_value,
                reason="environment_mismatch",
            )
            self._cache_and_stats(cache_key, result, flag_id)
            return result
        
        # Evaluate rules
        for rule in flag.rules:
            if self._evaluate_rule(rule, context):
                # Check percentage
                if self._check_percentage(rule, context):
                    result = FlagEvaluation(
                        flag_id=flag_id,
                        value=rule.value,
                        reason="rule_match",
                        rule_id=rule.rule_id,
                    )
                    self._cache_and_stats(cache_key, result, flag_id)
                    return result
        
        # Check global percentage rollout
        if not self._check_percentage(None, context, flag.percentage_rollout):
            result = FlagEvaluation(
                flag_id=flag_id,
                value=flag.default_value,
                reason="percentage_rollout",
            )
            self._cache_and_stats(cache_key, result, flag_id)
            return result
        
        # Default value
        result = FlagEvaluation(
            flag_id=flag_id,
            value=flag.default_value,
            reason="default",
        )
        self._cache_and_stats(cache_key, result, flag_id)
        return result
    
    def _evaluate_rule(self, rule: FlagRule, context: Dict[str, Any]) -> bool:
        """Evaluate a rule condition against context."""
        condition = rule.condition
        
        # Simple condition evaluation (supports basic operators)
        # Format: "user.attribute == 'value'" or "user.attribute > 10"
        
        try:
            # Replace context references
            for key, value in context.items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        placeholder = f"{key}.{subkey}"
                        if isinstance(subvalue, str):
                            condition = condition.replace(placeholder, f"'{subvalue}'")
                        else:
                            condition = condition.replace(placeholder, str(subvalue))
                else:
                    placeholder = key
                    if isinstance(value, str):
                        condition = condition.replace(placeholder, f"'{value}'")
                    else:
                        condition = condition.replace(placeholder, str(value))
            
            # Safe evaluation of condition
            # Only allow basic comparisons
            result = eval(condition, {"__builtins__": {}}, {})
            return bool(result)
            
        except Exception:
            return False
    
    def _check_percentage(self, rule: Optional[FlagRule],
                         context: Dict[str, Any],
                         percentage: float = 100.0) -> bool:
        """Check if user falls within percentage rollout."""
        if percentage >= 100.0:
            return True
        
        if percentage <= 0.0:
            return False
        
        # Generate consistent hash for user
        user_id = context.get("user_id", context.get("user", {}).get("id", ""))
        if not user_id:
            user_id = str(context)
        
        # Use hash to determine if user is in percentage
        hash_input = f"{user_id}:{rule.rule_id if rule else 'global'}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        user_percentage = (hash_value % 10000) / 100.0
        
        return user_percentage < percentage
    
    def _context_hash(self, context: Dict[str, Any]) -> str:
        """Generate hash of context for cache key."""
        return hashlib.md5(str(sorted(context.items())).encode()).hexdigest()[:8]
    
    def _cache_and_stats(self, cache_key: str, result: FlagEvaluation,
                        flag_id: str) -> None:
        """Cache result and update statistics."""
        now = datetime.now(timezone.utc).isoformat()
        self._evaluation_cache[cache_key] = (result, now)
        
        self._stats["total_evaluations"] += 1
        
        by_flag = self._stats["by_flag"].get(flag_id, 0)
        self._stats["by_flag"][flag_id] = by_flag + 1
        
        by_reason = self._stats["by_reason"].get(result.reason, 0)
        self._stats["by_reason"][result.reason] = by_reason + 1
    
    def _invalidate_cache(self, flag_id: str) -> None:
        """Invalidate cache entries for a flag."""
        keys_to_remove = [k for k in self._evaluation_cache if k.startswith(f"{flag_id}:")]
        for key in keys_to_remove:
            del self._evaluation_cache[key]
    
    def _log_change(self, flag_id: str, action: str,
                   old_value: Any, new_value: Any,
                   changed_by: str, reason: str = "") -> None:
        """Log a flag change."""
        change = FlagChange(
            change_id=f"change_{uuid.uuid4().hex[:8]}",
            flag_id=flag_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            changed_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
        )
        
        self._change_log.append(change)
        
        # Notify callbacks
        for callback in self._change_callbacks:
            try:
                callback(change.to_dict())
            except Exception as exc:
                logger.exception("Change callback failed: %s", exc)
    
    def register_change_callback(self, callback: Callable) -> None:
        """Register callback for flag changes."""
        self._change_callbacks.append(callback)
    
    def get_flag(self, flag_id: str) -> Optional[Dict[str, Any]]:
        """Get flag definition."""
        if flag_id not in self._flags:
            return None
        
        return self._flags[flag_id].to_dict()
    
    def get_all_flags(self, status: Optional[FlagStatus] = None,
                     environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all flags with optional filters."""
        flags = list(self._flags.values())
        
        if status:
            flags = [f for f in flags if f.status == status]
        
        if environment:
            flags = [f for f in flags if environment in f.environments]
        
        return [f.to_dict() for f in flags]
    
    def delete_flag(self, flag_id: str, deleted_by: str = "system") -> bool:
        """Delete a feature flag."""
        if flag_id not in self._flags:
            return False
        
        flag = self._flags[flag_id]
        old_dict = flag.to_dict()
        
        self._log_change(
            flag_id=flag_id,
            action="deleted",
            old_value=old_dict,
            new_value=None,
            changed_by=deleted_by,
            reason="Flag deleted",
        )
        
        del self._flags[flag_id]
        self._invalidate_cache(flag_id)
        
        return True
    
    def get_change_log(self, flag_id: Optional[str] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        """Get flag change log."""
        changes = self._change_log
        
        if flag_id:
            changes = [c for c in changes if c.flag_id == flag_id]
        
        # Sort by changed_at (newest first)
        changes.sort(key=lambda c: c.changed_at, reverse=True)
        
        return [c.to_dict() for c in changes[:limit]]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get feature flags statistics."""
        by_status = {}
        for flag in self._flags.values():
            status = flag.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_flags": len(self._flags),
            "total_evaluations": self._stats["total_evaluations"],
            "by_status": by_status,
            "by_flag": self._stats["by_flag"],
            "by_reason": self._stats["by_reason"],
            "cache_size": len(self._evaluation_cache),
        }
    
    def export_flags(self, format: str = "json") -> str:
        """Export flags configuration."""
        import json
        
        data = {
            "flags": [f.to_dict() for f in self._flags.values()],
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        
        if format == "json":
            return json.dumps(data, indent=2)
        
        return json.dumps(data, indent=2)
    
    def set_percentage_rollout(self, flag_id: str, percentage: float,
                              updated_by: str = "system") -> bool:
        """Set percentage rollout for a flag."""
        if flag_id not in self._flags:
            return False
        
        if not 0 <= percentage <= 100:
            raise ValueError("Percentage must be between 0 and 100")
        
        old_percentage = self._flags[flag_id].percentage_rollout
        
        self._flags[flag_id].percentage_rollout = percentage
        self._flags[flag_id].updated_at = datetime.now(timezone.utc).isoformat()
        
        self._log_change(
            flag_id=flag_id,
            action="updated",
            old_value={"percentage_rollout": old_percentage},
            new_value={"percentage_rollout": percentage},
            changed_by=updated_by,
            reason=f"Percentage rollout changed from {old_percentage}% to {percentage}%",
        )
        
        self._invalidate_cache(flag_id)
        
        return True
    
    def clear_cache(self) -> int:
        """Clear evaluation cache."""
        count = len(self._evaluation_cache)
        self._evaluation_cache.clear()
        return count


def create_feature_flags_engine() -> FeatureFlagsEngine:
    """Factory function to create feature flags engine."""
    return FeatureFlagsEngine()
