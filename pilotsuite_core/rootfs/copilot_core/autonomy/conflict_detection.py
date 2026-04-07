"""Conflict Detection — Erkennung von Automation-Konflikten (SOTA 2026).

Konflikt-Typen:
1. Trigger Conflict — Gleiche Trigger, unterschiedliche Actions
2. Action Conflict — Gleiche Entities, widersprüchliche Commands
3. Timing Conflict — Zeitliche Überschneidungen
4. Resource Conflict — Konkurrierende Ressourcen-Nutzung
5. Logic Conflict — Logisch widersprüchliche Regeln

Detection:
- Rule Analysis bei Erstellung
- Runtime Conflict Detection
- Conflict Resolution Suggestions
- Conflict Score (0-1)

Integration:
- Rule Engine → Conflict Detection
- Dashboard → Conflict Visualization
- Auto-Resolution Vorschläge
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import threading
from collections import defaultdict

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# CONFLICT TYPES
# =============================================================================

class ConflictType(str, Enum):
    """Konflikt-Typen."""
    
    TRIGGER = "trigger"  # Gleiche Trigger, unterschiedliche Actions
    ACTION = "action"  # Gleiche Entities, widersprüchliche Commands
    TIMING = "timing"  # Zeitliche Überschneidungen
    RESOURCE = "resource"  # Konkurrierende Ressourcen
    LOGIC = "logic"  # Logisch widersprüchlich


class ConflictSeverity(str, Enum):
    """Konflikt-Schweregrad."""
    
    LOW = "low"  # Minor conflict, can coexist
    MEDIUM = "medium"  # May cause issues
    HIGH = "high"  # Will cause problems
    CRITICAL = "critical"  # Must be resolved


@dataclass
class Conflict:
    """Erkannter Konflikt."""
    
    conflict_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    rule_ids: List[str]
    description: str
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolution_suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.value,
        }


# =============================================================================
# CONFLICT DETECTOR
# =============================================================================

class ConflictDetector:
    """Detector für Automation-Konflikte."""
    
    # Widersprüchliche Commands
    CONFLICTING_COMMANDS: Dict[str, List[str]] = {
        "turn_on": ["turn_off"],
        "turn_off": ["turn_on"],
        "open": ["close"],
        "close": ["open"],
        "lock": ["unlock"],
        "unlock": ["lock"],
        "increase": ["decrease"],
        "decrease": ["increase"],
    }
    
    def __init__(self):
        self._conflicts: Dict[str, Conflict] = {}
        self._rules: Dict[str, Dict[str, Any]] = {}  # rule_id → rule_data
        self._lock = threading.Lock()
        _LOGGER.info("ConflictDetector initialized")
    
    def register_rule(self, rule_id: str, rule_data: Dict[str, Any]) -> List[Conflict]:
        """Rule registrieren und auf Konflikte prüfen."""
        with self._lock:
            self._rules[rule_id] = rule_data
        
        # Check for conflicts with existing rules
        conflicts = []
        
        for existing_id, existing_data in self._rules.items():
            if existing_id == rule_id:
                continue
            
            conflict = self._check_conflict(rule_id, rule_data, existing_id, existing_data)
            if conflict:
                conflicts.append(conflict)
                with self._lock:
                    self._conflicts[conflict.conflict_id] = conflict
        
        return conflicts
    
    def unregister_rule(self, rule_id: str) -> None:
        """Rule entfernen."""
        with self._lock:
            self._rules.pop(rule_id, None)
            
            # Remove conflicts involving this rule
            to_remove = [
                cid for cid, conflict in self._conflicts.items()
                if rule_id in conflict.rule_ids
            ]
            for cid in to_remove:
                del self._conflicts[cid]
    
    def _check_conflict(
        self,
        rule_id1: str,
        rule_data1: Dict[str, Any],
        rule_id2: str,
        rule_data2: Dict[str, Any],
    ) -> Optional[Conflict]:
        """Konflikt zwischen zwei Rules prüfen."""
        # Check trigger conflict
        trigger_conflict = self._check_trigger_conflict(
            rule_id1, rule_data1.get("trigger", {}),
            rule_id2, rule_data2.get("trigger", {}),
        )
        if trigger_conflict:
            return trigger_conflict
        
        # Check action conflict
        action_conflict = self._check_action_conflict(
            rule_id1, rule_data1.get("action", {}),
            rule_id2, rule_data2.get("action", {}),
        )
        if action_conflict:
            return action_conflict
        
        # Check timing conflict
        timing_conflict = self._check_timing_conflict(
            rule_id1, rule_data1,
            rule_id2, rule_data2,
        )
        if timing_conflict:
            return timing_conflict
        
        return None
    
    def _check_trigger_conflict(
        self,
        rule_id1: str,
        trigger1: Dict[str, Any],
        rule_id2: str,
        trigger2: Dict[str, Any],
    ) -> Optional[Conflict]:
        """Trigger-Konflikt prüfen."""
        # Check if triggers overlap significantly
        common_keys = set(trigger1.keys()) & set(trigger2.keys())
        if not common_keys:
            return None
        
        # Check if values are compatible
        for key in common_keys:
            val1 = trigger1.get(key)
            val2 = trigger2.get(key)
            
            # Same trigger condition → potential conflict
            if val1 == val2:
                conflict_id = f"trigger_{rule_id1}_{rule_id2}"
                return Conflict(
                    conflict_id=conflict_id,
                    conflict_type=ConflictType.TRIGGER,
                    severity=ConflictSeverity.MEDIUM,
                    rule_ids=[rule_id1, rule_id2],
                    description=f"Both rules trigger on {key}={val1}",
                    resolution_suggestions=[
                        "Add additional conditions to differentiate rules",
                        "Merge rules into single rule with combined action",
                        "Adjust trigger thresholds",
                    ],
                )
        
        return None
    
    def _check_action_conflict(
        self,
        rule_id1: str,
        action1: Dict[str, Any],
        rule_id2: str,
        action2: Dict[str, Any],
    ) -> Optional[Conflict]:
        """Action-Konflikt prüfen."""
        module1 = action1.get("module")
        module2 = action2.get("module")
        
        if module1 != module2:
            return None  # Different modules, no conflict
        
        command1 = action1.get("command")
        command2 = action2.get("command")
        
        # Check for conflicting commands
        conflicting = self.CONFLICTING_COMMANDS.get(command1, [])
        if command2 in conflicting:
            conflict_id = f"action_{rule_id1}_{rule_id2}"
            return Conflict(
                conflict_id=conflict_id,
                conflict_type=ConflictType.ACTION,
                severity=ConflictSeverity.HIGH,
                rule_ids=[rule_id1, rule_id2],
                description=f"Conflicting commands: {command1} vs {command2} on {module1}",
                resolution_suggestions=[
                    "Add mutually exclusive conditions",
                    "Prioritize one rule over the other",
                    "Combine into single rule with conditional logic",
                ],
            )
        
        return None
    
    def _check_timing_conflict(
        self,
        rule_id1: str,
        rule_data1: Dict[str, Any],
        rule_id2: str,
        rule_data2: Dict[str, Any],
    ) -> Optional[Conflict]:
        """Timing-Konflikt prüfen."""
        trigger1 = rule_data1.get("trigger", {})
        trigger2 = rule_data2.get("trigger", {})
        
        # Check time-based conflicts
        if "time_is" in trigger1 and "time_is" in trigger2:
            if trigger1["time_is"] == trigger2["time_is"]:
                conflict_id = f"timing_{rule_id1}_{rule_id2}"
                return Conflict(
                    conflict_id=conflict_id,
                    conflict_type=ConflictType.TIMING,
                    severity=ConflictSeverity.LOW,
                    rule_ids=[rule_id1, rule_id2],
                    description=f"Both rules trigger at same time: {trigger1['time_is']}",
                    resolution_suggestions=[
                        "Stagger execution times",
                        "Add priority to one rule",
                    ],
                )
        
        # Check time range overlaps
        if "time_range" in trigger1 and "time_range" in trigger2:
            range1 = trigger1["time_range"]
            range2 = trigger2["time_range"]
            
            if self._ranges_overlap(range1, range2):
                conflict_id = f"timing_{rule_id1}_{rule_id2}"
                return Conflict(
                    conflict_id=conflict_id,
                    conflict_type=ConflictType.TIMING,
                    severity=ConflictSeverity.LOW,
                    rule_ids=[rule_id1, rule_id2],
                    description=f"Overlapping time ranges: {range1} vs {range2}",
                    resolution_suggestions=[
                        "Adjust time ranges to not overlap",
                        "Add priority to one rule",
                    ],
                )
        
        return None
    
    def _ranges_overlap(self, range1: List[str], range2: List[str]) -> bool:
        """Prüfen ob Zeitbereiche sich überschneiden."""
        if len(range1) != 2 or len(range2) != 2:
            return False
        
        start1, end1 = range1
        start2, end2 = range2
        
        # Simple overlap check
        return not (end1 <= start2 or end2 <= start1)
    
    def get_conflicts_for_rule(self, rule_id: str) -> List[Conflict]:
        """Konflikte für Rule holen."""
        with self._lock:
            return [
                c for c in self._conflicts.values()
                if rule_id in c.rule_ids
            ]
    
    def get_all_conflicts(self) -> List[Conflict]:
        """Alle Konflikte."""
        with self._lock:
            return list(self._conflicts.values())
    
    def resolve_conflict(self, conflict_id: str, resolution: str) -> bool:
        """Konflikt als gelöst markieren."""
        with self._lock:
            if conflict_id in self._conflicts:
                self._conflicts[conflict_id].metadata["resolved"] = True
                self._conflicts[conflict_id].metadata["resolution"] = resolution
                return True
            return False
    
    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_type = defaultdict(int)
            by_severity = defaultdict(int)
            
            for conflict in self._conflicts.values():
                by_type[conflict.conflict_type.value] += 1
                by_severity[conflict.severity.value] += 1
            
            return {
                "total_conflicts": len(self._conflicts),
                "total_rules": len(self._rules),
                "by_type": dict(by_type),
                "by_severity": dict(by_severity),
                "unresolved": sum(1 for c in self._conflicts.values() if not c.metadata.get("resolved", False)),
            }


# =============================================================================
# Singleton
# =============================================================================

_detector_instance: Optional[ConflictDetector] = None


def get_conflict_detector() -> ConflictDetector:
    """Singleton-Zugriff."""
    global _detector_instance
    
    if _detector_instance is None:
        _detector_instance = ConflictDetector()
    
    return _detector_instance
