"""State Consistency Checker — P2-007.

Validates entity/zone state invariants after state transitions.
Runs pre/post condition checks on state mutations.
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ViolationSeverity(Enum):
    FATAL = "fatal"
    ERROR = "error"
    WARN = "warn"


@dataclass
class StateViolation:
    severity: ViolationSeverity
    zone_id: str
    invariant: str
    expected: Any
    actual: Any
    message: str


class StateInvariant:
    def __init__(self, name: str, check_fn: Callable[["ZoneStateSnapshot"], Optional[StateViolation]]):
        self.name = name
        self.check_fn = check_fn

    def validate(self, snapshot: "ZoneStateSnapshot") -> Optional[StateViolation]:
        try:
            return self.check_fn(snapshot)
        except Exception as e:
            return StateViolation(
                severity=ViolationSeverity.ERROR,
                zone_id=snapshot.zone_id,
                invariant=self.name,
                expected=None, actual=None,
                message=f"Invariant check crashed: {e}",
            )


@dataclass
class ZoneStateSnapshot:
    zone_id: str
    state: Any
    confidence: float
    active_sensors: List[str]
    inactive_sensors: List[str]
    present_since: Optional[str] = None
    absent_since: Optional[str] = None
    hold_state: str = "auto"
    evidence_strength: str = "none"


def inv_no_active_and_absent_together(s: ZoneStateSnapshot) -> Optional[StateViolation]:
    if s.present_since and s.absent_since:
        return StateViolation(
            severity=ViolationSeverity.FATAL, zone_id=s.zone_id,
            invariant="no_active_and_absent_together",
            expected="present_since XOR absent_since",
            actual=f"both set", message="Zone cannot be present AND absent")


def inv_active_sensors_not_inactive(s: ZoneStateSnapshot) -> Optional[StateViolation]:
    overlap = set(s.active_sensors) & set(s.inactive_sensors)
    if overlap:
        return StateViolation(
            severity=ViolationSeverity.FATAL, zone_id=s.zone_id,
            invariant="active_sensors_not_inactive",
            expected=f"disjoint sets, actual overlap={overlap}",
            actual=f"active={s.active_sensors}", message="Sensor both active and inactive")


def inv_confidence_in_unit_range(s: ZoneStateSnapshot) -> Optional[StateViolation]:
    if not (0.0 <= s.confidence <= 1.0):
        return StateViolation(
            severity=ViolationSeverity.ERROR, zone_id=s.zone_id,
            invariant="confidence_in_unit_range", expected="[0.0, 1.0]",
            actual=s.confidence, message=f"Confidence out of range: {s.confidence}")


def inv_present_since_requires_present(s: ZoneStateSnapshot) -> Optional[StateViolation]:
    if s.present_since and str(s.state) in ("absent", "extended_absent"):
        return StateViolation(
            severity=ViolationSeverity.ERROR, zone_id=s.zone_id,
            invariant="present_since_requires_present",
            expected="present state", actual=s.state,
            message="present_since set but zone not present")


def inv_no_sensors_implies_absent(s: ZoneStateSnapshot) -> Optional[StateViolation]:
    if not s.active_sensors and not s.inactive_sensors and str(s.state) == "present":
        return StateViolation(
            severity=ViolationSeverity.WARN, zone_id=s.zone_id,
            invariant="no_sensors_implies_absent", expected="absent/uncertain",
            actual="present with no sensors", message="Zone present but sensorless")


DEFAULT_INVARIANTS = [
    StateInvariant("no_active_and_absent_together", inv_no_active_and_absent_together),
    StateInvariant("active_sensors_not_inactive", inv_active_sensors_not_inactive),
    StateInvariant("confidence_in_unit_range", inv_confidence_in_unit_range),
    StateInvariant("present_since_requires_present", inv_present_since_requires_present),
    StateInvariant("no_sensors_implies_absent", inv_no_sensors_implies_absent),
]


class StateConsistencyChecker:
    def __init__(self, invariants: Optional[List[StateInvariant]] = None):
        self.invariants = invariants or DEFAULT_INVARIANTS

    def check(self, snapshot: ZoneStateSnapshot) -> List[StateViolation]:
        violations = []
        for inv in self.invariants:
            v = inv.validate(snapshot)
            if v:
                violations.append(v)
                logger.warning(f"[{v.severity.value}] {v.zone_id}/{inv.name}: {v.message}")
        return violations

    def check_batch(self, snapshots: List[ZoneStateSnapshot]) -> Dict[str, List[StateViolation]]:
        results: Dict[str, List[StateViolation]] = {}
        for snap in snapshots:
            viols = self.check(snap)
            if viols:
                results[snap.zone_id] = viols
        return results
