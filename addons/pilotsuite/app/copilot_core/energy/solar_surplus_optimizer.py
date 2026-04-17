"""Solar surplus policy kernel for recommendation-first energy optimization.

This module stays Core-local and pure: it turns forecast surplus windows plus
shiftable device candidates into deterministic scheduling recommendations
without importing Home Assistant runtime surfaces.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence


def _parse_iso_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class SolarSurplusSlot:
    """A scored forecast window that can absorb flexible demand."""

    timestamp: str
    window_hours: float
    available_surplus_kwh: float
    expected_import_price_ct_kwh: float
    expected_export_price_ct_kwh: float = 8.0
    confidence: float = 1.0

    @property
    def starts_at(self) -> datetime:
        return _parse_iso_timestamp(self.timestamp)


@dataclass(frozen=True)
class SolarSurplusCandidate:
    """A shiftable device/job that could consume PV surplus."""

    device_id: str
    device_name: str
    energy_kwh: float
    duration_hours: float
    earliest_start: str
    latest_start: str
    priority: int = 3
    interruptible: bool = False

    @property
    def earliest_start_at(self) -> datetime:
        return _parse_iso_timestamp(self.earliest_start)

    @property
    def latest_start_at(self) -> datetime:
        return _parse_iso_timestamp(self.latest_start)


@dataclass(frozen=True)
class SolarSurplusAction:
    """Recommendation output for a single candidate."""

    device_id: str
    device_name: str
    action: str
    recommended_start: str
    reason: str
    confidence: float
    expected_self_consumption_gain_pct: float
    expected_savings_eur: float
    expected_grid_relief_kwh: float
    slot_timestamp: str | None
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SolarSurplusSummary:
    """Aggregate view over generated recommendations."""

    generated_at: str
    horizon_hours: int
    total_slots: int
    total_candidates: int
    recommendations_count: int
    expected_self_consumption_gain_pct: float
    expected_savings_eur: float
    expected_grid_relief_kwh: float

    def to_dict(self) -> dict:
        return asdict(self)


class SolarSurplusOptimizer:
    """Pure policy kernel for recommendation-first PV-surplus scheduling."""

    def __init__(
        self,
        *,
        minimum_surplus_kwh: float = 0.25,
        minimum_recommendation_coverage: float = 0.35,
        schedule_now_window_minutes: int = 30,
    ):
        self._minimum_surplus_kwh = max(0.0, minimum_surplus_kwh)
        self._minimum_recommendation_coverage = min(max(minimum_recommendation_coverage, 0.0), 1.0)
        self._schedule_now_window_minutes = max(0, schedule_now_window_minutes)

    def recommend(
        self,
        slots: Sequence[SolarSurplusSlot] | Iterable[SolarSurplusSlot],
        candidates: Sequence[SolarSurplusCandidate] | Iterable[SolarSurplusCandidate],
        *,
        now: datetime | None = None,
    ) -> tuple[list[SolarSurplusAction], SolarSurplusSummary]:
        ordered_slots = sorted(list(slots), key=lambda slot: slot.starts_at)
        ordered_candidates = list(candidates)
        reference_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

        actions = [self._recommend_for_candidate(candidate, ordered_slots, reference_now) for candidate in ordered_candidates]
        recommended = [action for action in actions if action.action in {"schedule_now", "schedule_at"}]
        total_relief = sum(action.expected_grid_relief_kwh for action in recommended)
        total_savings = sum(action.expected_savings_eur for action in recommended)
        total_candidate_energy = sum(candidate.energy_kwh for candidate in ordered_candidates)
        total_gain_pct = 0.0
        if total_candidate_energy > 0:
            total_gain_pct = min(100.0, (total_relief / total_candidate_energy) * 100.0)

        horizon_hours = 0
        if ordered_slots:
            start = ordered_slots[0].starts_at
            end = max(slot.starts_at for slot in ordered_slots)
            horizon_hours = max(1, int(round((end - start).total_seconds() / 3600)) + 1)

        summary = SolarSurplusSummary(
            generated_at=_iso_utc(reference_now),
            horizon_hours=horizon_hours,
            total_slots=len(ordered_slots),
            total_candidates=len(ordered_candidates),
            recommendations_count=len(recommended),
            expected_self_consumption_gain_pct=round(total_gain_pct, 2),
            expected_savings_eur=round(total_savings, 2),
            expected_grid_relief_kwh=round(total_relief, 2),
        )
        return actions, summary

    def _recommend_for_candidate(
        self,
        candidate: SolarSurplusCandidate,
        slots: Sequence[SolarSurplusSlot],
        now: datetime,
    ) -> SolarSurplusAction:
        feasible_slots = [slot for slot in slots if self._is_feasible(slot, candidate)]
        if not feasible_slots:
            return SolarSurplusAction(
                device_id=candidate.device_id,
                device_name=candidate.device_name,
                action="do_not_shift",
                recommended_start=candidate.earliest_start,
                reason="no feasible surplus slot inside the allowed start window",
                confidence=0.0,
                expected_self_consumption_gain_pct=0.0,
                expected_savings_eur=0.0,
                expected_grid_relief_kwh=0.0,
                slot_timestamp=None,
                score=0.0,
            )

        best_slot = max(feasible_slots, key=lambda slot: self._score_slot(slot, candidate))
        score = self._score_slot(best_slot, candidate)
        coverage = self._coverage(best_slot, candidate)
        relief_kwh = min(candidate.energy_kwh, max(best_slot.available_surplus_kwh, 0.0))
        price_delta = max(best_slot.expected_import_price_ct_kwh - best_slot.expected_export_price_ct_kwh, 0.0)
        savings_eur = relief_kwh * price_delta / 100.0
        confidence = round(min(1.0, best_slot.confidence * (0.7 + coverage * 0.3)), 2)

        if coverage < self._minimum_recommendation_coverage:
            action = "delay"
            reason = (
                f"best slot at {best_slot.timestamp} only covers {coverage * 100:.0f}% "
                f"of the {candidate.device_name} cycle"
            )
        else:
            seconds_until_start = (best_slot.starts_at - now).total_seconds()
            if abs(seconds_until_start) <= self._schedule_now_window_minutes * 60:
                action = "schedule_now"
            else:
                action = "schedule_at"
            reason = (
                f"pv surplus can cover {coverage * 100:.0f}% of the cycle at "
                f"{best_slot.expected_import_price_ct_kwh:.1f} ct/kWh import price"
            )

        return SolarSurplusAction(
            device_id=candidate.device_id,
            device_name=candidate.device_name,
            action=action,
            recommended_start=best_slot.timestamp,
            reason=reason,
            confidence=confidence,
            expected_self_consumption_gain_pct=round(coverage * 100.0, 2),
            expected_savings_eur=round(savings_eur, 2),
            expected_grid_relief_kwh=round(relief_kwh, 2),
            slot_timestamp=best_slot.timestamp,
            score=round(score, 4),
        )

    def _is_feasible(self, slot: SolarSurplusSlot, candidate: SolarSurplusCandidate) -> bool:
        if slot.available_surplus_kwh < self._minimum_surplus_kwh:
            return False
        if slot.starts_at < candidate.earliest_start_at or slot.starts_at > candidate.latest_start_at:
            return False
        if candidate.interruptible:
            return True
        return slot.window_hours >= candidate.duration_hours

    def _coverage(self, slot: SolarSurplusSlot, candidate: SolarSurplusCandidate) -> float:
        if candidate.energy_kwh <= 0:
            return 0.0
        return min(1.0, max(slot.available_surplus_kwh, 0.0) / candidate.energy_kwh)

    def _score_slot(self, slot: SolarSurplusSlot, candidate: SolarSurplusCandidate) -> float:
        coverage = self._coverage(slot, candidate)
        price_signal = min(1.0, max(slot.expected_import_price_ct_kwh - slot.expected_export_price_ct_kwh, 0.0) / 40.0)
        priority_signal = min(1.0, max(0.2, (6 - candidate.priority) / 5.0))
        confidence_signal = min(1.0, max(0.0, slot.confidence))
        return (
            coverage * 0.55
            + price_signal * 0.20
            + priority_signal * 0.15
            + confidence_signal * 0.10
        )


__all__ = [
    "SolarSurplusAction",
    "SolarSurplusCandidate",
    "SolarSurplusOptimizer",
    "SolarSurplusSlot",
    "SolarSurplusSummary",
]
