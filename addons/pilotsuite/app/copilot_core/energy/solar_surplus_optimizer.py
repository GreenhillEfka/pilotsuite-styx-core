"""Solar surplus policy kernel for recommendation-first energy optimization.

This module stays Core-local and pure: it turns forecast surplus windows plus
shiftable device candidates into deterministic scheduling recommendations
without importing Home Assistant runtime surfaces.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class _AlignedForecastPoint:
    timestamp: str | None
    payload: dict[str, Any]


def _parse_iso_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_record(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return {
            key: attr
            for key, attr in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            raise ValueError
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            raise ValueError
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def _ceil_to_hour(dt: datetime) -> datetime:
    normalized = dt.astimezone(timezone.utc)
    floored = normalized.replace(minute=0, second=0, microsecond=0)
    if floored == normalized:
        return floored
    return floored + timedelta(hours=1)


def _floor_to_hour(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _hour_in_window(hour: int, min_hour: int, max_hour: int) -> bool:
    if min_hour <= max_hour:
        return min_hour <= hour <= max_hour
    return hour >= min_hour or hour <= max_hour


def _next_allowed_hour(anchor: datetime, min_hour: int, max_hour: int) -> datetime:
    candidate = _ceil_to_hour(anchor)
    if _hour_in_window(candidate.hour, min_hour, max_hour):
        return candidate

    for offset in range(0, 49):
        probe = candidate + timedelta(hours=offset)
        if _hour_in_window(probe.hour, min_hour, max_hour):
            return probe
    return candidate


def _previous_allowed_hour(anchor: datetime, min_hour: int, max_hour: int) -> datetime:
    candidate = _floor_to_hour(anchor)
    if _hour_in_window(candidate.hour, min_hour, max_hour):
        return candidate

    for offset in range(0, 49):
        probe = candidate - timedelta(hours=offset)
        if _hour_in_window(probe.hour, min_hour, max_hour):
            return probe
    return candidate


def _normalized_timestamp(record: Mapping[str, Any], index: int, reference_time: datetime | None) -> str | None:
    raw_timestamp = record.get("timestamp")
    if isinstance(raw_timestamp, str) and raw_timestamp:
        return _iso_utc(_parse_iso_timestamp(raw_timestamp))
    if reference_time is None:
        return None
    return _iso_utc(_floor_to_hour(reference_time) + timedelta(hours=index))


def _normalize_forecast_points(
    forecast: Sequence[Any] | Iterable[Any] | None,
    *,
    reference_time: datetime | None = None,
) -> list[_AlignedForecastPoint]:
    normalized: list[_AlignedForecastPoint] = []
    for index, point in enumerate(list(forecast or [])):
        payload = _coerce_record(point)
        normalized.append(
            _AlignedForecastPoint(
                timestamp=_normalized_timestamp(payload, index, reference_time),
                payload=payload,
            )
        )
    return normalized


def _aligned_point(
    points: Sequence[_AlignedForecastPoint],
    by_timestamp: Mapping[str, dict[str, Any]],
    *,
    index: int,
    timestamp: str | None,
) -> dict[str, Any] | None:
    if timestamp and timestamp in by_timestamp:
        return by_timestamp[timestamp]
    if index >= len(points):
        return None
    if points[index].timestamp is None:
        return points[index].payload
    return None


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

    @classmethod
    def from_forecast_point(
        cls,
        pv_point: Any,
        *,
        load_point: Any = None,
        price_point: Any = None,
        timestamp: str | None = None,
        default_import_price_ct_kwh: float = 30.0,
        default_export_price_ct_kwh: float = 8.0,
    ) -> SolarSurplusSlot:
        pv_data = _coerce_record(pv_point)
        load_data = _coerce_record(load_point)
        price_data = _coerce_record(price_point)

        resolved_timestamp = (
            timestamp
            or pv_data.get("timestamp")
            or load_data.get("timestamp")
            or price_data.get("timestamp")
            or "1970-01-01T00:00:00Z"
        )
        window_hours = max(
            0.25,
            _coerce_float(
                pv_data.get("window_hours", pv_data.get("duration_hours")),
                1.0,
            ),
        )
        pv_energy_kwh = _coerce_float(pv_data.get("pv_energy_wh"), 0.0) / 1000.0
        if pv_energy_kwh <= 0:
            pv_energy_kwh = _coerce_float(pv_data.get("pv_energy_kwh"), 0.0)
        if pv_energy_kwh <= 0:
            pv_energy_kwh = _coerce_float(pv_data.get("pv_power_kw"), 0.0) * window_hours

        load_energy_kwh = _coerce_float(load_data.get("predicted_consumption_kwh"), 0.0)
        if load_energy_kwh <= 0:
            load_energy_kwh = _coerce_float(load_data.get("predicted_consumption_kw"), 0.0) * window_hours

        confidence = _coerce_float(load_data.get("confidence"), _coerce_float(pv_data.get("confidence"), 1.0))
        import_price = _coerce_float(
            price_data.get("price_ct_kwh", price_data.get("import_price_ct_kwh")),
            default_import_price_ct_kwh,
        )
        export_price = _coerce_float(
            price_data.get("export_price_ct_kwh", price_data.get("feed_in_tariff_ct_kwh")),
            default_export_price_ct_kwh,
        )
        available_surplus_kwh = max(0.0, pv_energy_kwh - load_energy_kwh)

        return cls(
            timestamp=_iso_utc(_parse_iso_timestamp(str(resolved_timestamp))),
            window_hours=round(window_hours, 3),
            available_surplus_kwh=round(available_surplus_kwh, 3),
            expected_import_price_ct_kwh=round(import_price, 3),
            expected_export_price_ct_kwh=round(export_price, 3),
            confidence=round(min(1.0, max(0.0, confidence)), 2),
        )

    @classmethod
    def from_forecasts(
        cls,
        pv_forecast: Sequence[Any] | Iterable[Any],
        *,
        load_forecast: Sequence[Any] | Iterable[Any] | None = None,
        price_forecast: Sequence[Any] | Iterable[Any] | None = None,
        reference_time: datetime | None = None,
        default_import_price_ct_kwh: float = 30.0,
        default_export_price_ct_kwh: float = 8.0,
    ) -> list[SolarSurplusSlot]:
        pv_points = _normalize_forecast_points(pv_forecast, reference_time=reference_time)
        if not pv_points:
            return []

        load_points = _normalize_forecast_points(load_forecast, reference_time=reference_time)
        price_points = _normalize_forecast_points(price_forecast, reference_time=reference_time)
        load_by_timestamp = {
            point.timestamp: point.payload
            for point in load_points
            if point.timestamp
        }
        price_by_timestamp = {
            point.timestamp: point.payload
            for point in price_points
            if point.timestamp
        }

        slots: list[SolarSurplusSlot] = []
        for index, pv_point in enumerate(pv_points):
            if pv_point.timestamp is None:
                continue
            load_point = _aligned_point(load_points, load_by_timestamp, index=index, timestamp=pv_point.timestamp)
            price_point = _aligned_point(price_points, price_by_timestamp, index=index, timestamp=pv_point.timestamp)

            if load_points and load_point is None:
                continue
            if price_points and price_point is None:
                continue

            slots.append(
                cls.from_forecast_point(
                    pv_point.payload,
                    load_point=load_point,
                    price_point=price_point,
                    timestamp=pv_point.timestamp,
                    default_import_price_ct_kwh=default_import_price_ct_kwh,
                    default_export_price_ct_kwh=default_export_price_ct_kwh,
                )
            )
        return slots


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

    @classmethod
    def from_shiftable_device(
        cls,
        device: Any,
        *,
        reference_time: datetime,
    ) -> SolarSurplusCandidate | None:
        payload = _coerce_record(device)
        device_id = str(payload.get("device_id", "")).strip()
        if not device_id:
            return None

        current_state = str(payload.get("current_state", "idle") or "idle").strip().lower()
        if current_state not in {"idle", "ready", "pending"}:
            return None

        anchor = _ceil_to_hour(reference_time)
        duration_hours = _coerce_float(payload.get("duration_hours"), 0.0)
        energy_kwh = _coerce_float(payload.get("energy_kwh"), 0.0)
        power_kw = _coerce_float(payload.get("power_kw"), 0.0)

        if duration_hours <= 0 and energy_kwh > 0 and power_kw > 0:
            duration_hours = energy_kwh / power_kw
        if duration_hours <= 0:
            duration_hours = 1.0
        if energy_kwh <= 0 and power_kw > 0:
            energy_kwh = power_kw * duration_hours
        if energy_kwh <= 0:
            energy_kwh = duration_hours

        min_start_hour = max(0, min(23, _coerce_int(payload.get("min_start_hour"), anchor.hour)))
        max_start_hour = max(0, min(23, _coerce_int(payload.get("max_start_hour"), 23)))
        flexibility_hours = max(0.0, _coerce_float(payload.get("flexibility_hours"), 4.0))

        earliest_start_at = _next_allowed_hour(anchor, min_start_hour, max_start_hour)
        latest_deadline = anchor + timedelta(hours=flexibility_hours)
        latest_start_at = _previous_allowed_hour(latest_deadline, min_start_hour, max_start_hour)
        if earliest_start_at > latest_deadline:
            return None

        must_complete_by = payload.get("must_complete_by")
        if isinstance(must_complete_by, str) and must_complete_by:
            latest_finish = _parse_iso_timestamp(must_complete_by)
            latest_start_at = min(
                latest_start_at,
                _floor_to_hour(latest_finish - timedelta(hours=duration_hours)),
            )
            if latest_start_at + timedelta(hours=duration_hours) > latest_finish:
                return None

        if latest_start_at < earliest_start_at:
            latest_start_at = earliest_start_at

        return cls(
            device_id=device_id,
            device_name=str(payload.get("name") or payload.get("device_name") or device_id),
            energy_kwh=round(max(0.0, energy_kwh), 3),
            duration_hours=round(max(0.25, duration_hours), 3),
            earliest_start=_iso_utc(earliest_start_at),
            latest_start=_iso_utc(latest_start_at),
            priority=max(1, min(5, _coerce_int(payload.get("priority"), 3))),
            interruptible=_coerce_bool(payload.get("interruptible"), False),
        )

    @classmethod
    def from_shiftable_devices(
        cls,
        devices: Sequence[Any] | Iterable[Any],
        *,
        reference_time: datetime,
    ) -> list[SolarSurplusCandidate]:
        candidates: list[SolarSurplusCandidate] = []
        for device in list(devices):
            candidate = cls.from_shiftable_device(device, reference_time=reference_time)
            if candidate is not None:
                candidates.append(candidate)
        return candidates


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

    def get_recommendations_as_dict(
        self,
        *,
        pv_forecast: Sequence[Any] | Iterable[Any],
        shiftable_devices: Sequence[Any] | Iterable[Any],
        load_forecast: Sequence[Any] | Iterable[Any] | None = None,
        price_forecast: Sequence[Any] | Iterable[Any] | None = None,
        reference_time: datetime | None = None,
        now: datetime | None = None,
        default_import_price_ct_kwh: float = 30.0,
        default_export_price_ct_kwh: float = 8.0,
    ) -> dict[str, Any]:
        """Build one normalized recommendation batch for service/API callers.

        This is the thin reporting surface for VFM-012: callers can hand over
        existing forecast payloads and shiftable-device profiles, while this
        method keeps normalization, recommendation generation, and response
        shaping in one deterministic Core-local seam.
        """

        report_reference = (reference_time or now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        slots = SolarSurplusSlot.from_forecasts(
            pv_forecast,
            load_forecast=load_forecast,
            price_forecast=price_forecast,
            reference_time=report_reference,
            default_import_price_ct_kwh=default_import_price_ct_kwh,
            default_export_price_ct_kwh=default_export_price_ct_kwh,
        )
        candidates = SolarSurplusCandidate.from_shiftable_devices(
            shiftable_devices,
            reference_time=report_reference,
        )
        actions, summary = self.recommend(slots, candidates, now=now or report_reference)

        return {
            "generated_at": summary.generated_at,
            "summary": summary.to_dict(),
            "recommendations": [action.to_dict() for action in actions],
            "slots": [asdict(slot) for slot in slots],
            "candidates": [asdict(candidate) for candidate in candidates],
        }

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
