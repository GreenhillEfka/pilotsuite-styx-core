"""Zone Presence Hold Analytics — Usage History, Zone Patterns, Effectiveness Metrics."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass(frozen=True)
class HoldUsageEntryV1:
    """Einzelner Hold-Usage-Eintrag für Historie."""

    hold_id: str
    zone_id: str
    hold_state: str  # force_on | force_off | auto
    reason: Optional[str]
    set_at: str  # ISO-8601
    released_at: Optional[str]  # ISO-8601 oder None
    duration_seconds: Optional[int]  # geplante Dauer oder None
    actual_duration_seconds: Optional[int]  # tatsächliche Dauer oder None
    expiration_reason: Optional[str]  # auto_expire | manual_release | None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class HoldUsageHistoryV1:
    """Aggregierte Hold-Usage-Historie über alle Zonen."""

    entries: List[HoldUsageEntryV1]
    total_holds: int
    total_force_on: int
    total_force_off: int
    total_auto: int
    total_expired: int
    total_manually_released: int
    avg_duration_seconds: Optional[float]
    revision: int
    latest_change_at: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None


@dataclass(frozen=True)
class HoldZonePatternEntryV1:
    """Hold-Pattern für eine einzelne Zone."""

    zone_id: str
    zone_name: Optional[str]
    total_holds: int
    force_on_count: int
    force_off_count: int
    avg_hold_duration_seconds: Optional[float]
    most_common_reason: Optional[str]
    most_common_state: str  # force_on | force_off | auto
    last_hold_at: Optional[str]
    holds_last_7_days: int
    holds_last_30_days: int


@dataclass(frozen=True)
class HoldZonePatternsV1:
    """Zone-spezifische Hold-Patterns."""

    patterns: List[HoldZonePatternEntryV1]
    total_zones: int
    zones_with_holds: int
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class HoldEffectivenessMetricsV1:
    """Hold-Effectiveness-Metriken."""

    total_holds_analyzed: int
    holds_with_sensor_conflict: int  # Hold gesetzt, aber Sensor hätte gegenteiligen State erzeugt
    conflict_rate: float  # 0.0–1.0
    holds_preventing_flapping: int  # Holds die State-Flapping verhindert haben
    flapping_prevention_rate: float  # 0.0–1.0
    avg_hold_duration_before_stable: Optional[float]  # avg Dauer bis Sensor-State stabil
    zones_benefiting_from_holds: int
    zones_without_benefit: int
    effectiveness_score: float  # 0.0–1.0 composite score
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class HoldAnalyticsSummaryV1:
    """Zusammenfassung aller Hold-Analytics."""

    usage: HoldUsageHistoryV1
    patterns: HoldZonePatternsV1
    effectiveness: HoldEffectivenessMetricsV1
    summary_revision: int
    latest_change_at: str


class HoldAnalyticsStore:
    """Store für Hold-Analytics-Read-Models."""

    def __init__(self, hold_store=None, notification_store=None, zone_truth_store=None):
        from copilot_core.core.zone_presence_hold import get_zone_presence_hold_store
        self.hold_store = hold_store or get_zone_presence_hold_store()
        self.notification_store = notification_store
        self.zone_truth_store = zone_truth_store
        self._revision = 0
        self._latest_change_at = datetime.now(timezone.utc).isoformat()

    def _bump_revision(self) -> int:
        self._revision += 1
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        return self._revision

    def _compute_entry_hash(self, entry: HoldUsageEntryV1) -> str:
        data = f"{entry.hold_id}:{entry.zone_id}:{entry.set_at}:{entry.released_at}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def build_usage_history(
        self,
        zone_id: Optional[str] = None,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
        limit: int = 100,
    ) -> HoldUsageHistoryV1:
        """Build Hold-Usage-Historie mit optionalen Filtern."""
        from datetime import datetime as dt

        holds = self.hold_store.get_all_holds() if hasattr(self.hold_store, "get_all_holds") else []

        entries: List[HoldUsageEntryV1] = []
        total_force_on = 0
        total_force_off = 0
        total_auto = 0
        total_expired = 0
        total_manually_released = 0
        durations: List[int] = []

        for hold in holds:
            if zone_id and hold.zone_id != zone_id:
                continue

            set_at = hold.set_at if hasattr(hold, "set_at") else getattr(hold, "created_at", None)
            if not set_at:
                continue

            if time_range_start and set_at < time_range_start:
                continue
            if time_range_end and set_at > time_range_end:
                continue

            released_at = getattr(hold, "released_at", None)
            hold_state = getattr(hold, "hold_state", "auto")
            reason = getattr(hold, "reason", None)
            expires_at = getattr(hold, "expires_at", None)
            duration_seconds = getattr(hold, "duration_seconds", None)

            actual_duration = None
            expiration_reason = None

            if released_at and set_at:
                try:
                    set_dt = dt.fromisoformat(set_at.replace("Z", "+00:00"))
                    rel_dt = dt.fromisoformat(released_at.replace("Z", "+00:00"))
                    actual_duration = int((rel_dt - set_dt).total_seconds())
                    durations.append(actual_duration)
                except (ValueError, TypeError):
                    pass

            if expires_at and not released_at:
                expiration_reason = "auto_expire"
                total_expired += 1
            elif released_at:
                expiration_reason = "manual_release"
                total_manually_released += 1

            if hold_state == "force_on":
                total_force_on += 1
            elif hold_state == "force_off":
                total_force_off += 1
            else:
                total_auto += 1

            entries.append(
                HoldUsageEntryV1(
                    hold_id=getattr(hold, "hold_id", ""),
                    zone_id=hold.zone_id,
                    hold_state=hold_state,
                    reason=reason,
                    set_at=set_at,
                    released_at=released_at,
                    duration_seconds=duration_seconds,
                    actual_duration_seconds=actual_duration,
                    expiration_reason=expiration_reason,
                )
            )

        entries.sort(key=lambda e: e.set_at, reverse=True)
        entries = entries[:limit]

        avg_duration = sum(durations) / len(durations) if durations else None

        self._bump_revision()

        return HoldUsageHistoryV1(
            entries=entries,
            total_holds=len(entries),
            total_force_on=total_force_on,
            total_force_off=total_force_off,
            total_auto=total_auto,
            total_expired=total_expired,
            total_manually_released=total_manually_released,
            avg_duration_seconds=avg_duration,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
        )

    def build_zone_patterns(self) -> HoldZonePatternsV1:
        """Build Zone-spezifische Hold-Patterns."""
        from datetime import datetime as dt, timedelta

        holds = self.hold_store.get_all_holds() if hasattr(self.hold_store, "get_all_holds") else []

        zone_data: Dict[str, dict] = {}
        now = dt.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        for hold in holds:
            zone_id = hold.zone_id
            if zone_id not in zone_data:
                zone_data[zone_id] = {
                    "zone_id": zone_id,
                    "zone_name": None,
                    "total_holds": 0,
                    "force_on_count": 0,
                    "force_off_count": 0,
                    "durations": [],
                    "reasons": {},
                    "states": {},
                    "last_hold_at": None,
                    "holds_last_7_days": 0,
                    "holds_last_30_days": 0,
                }

            zd = zone_data[zone_id]
            zd["total_holds"] += 1

            hold_state = getattr(hold, "hold_state", "auto")
            if hold_state == "force_on":
                zd["force_on_count"] += 1
            elif hold_state == "force_off":
                zd["force_off_count"] += 1

            zd["states"][hold_state] = zd["states"].get(hold_state, 0) + 1

            reason = getattr(hold, "reason", None)
            if reason:
                zd["reasons"][reason] = zd["reasons"].get(reason, 0) + 1

            set_at = getattr(hold, "set_at", getattr(hold, "created_at", None))
            if set_at:
                try:
                    set_dt = dt.fromisoformat(set_at.replace("Z", "+00:00"))
                    if zd["last_hold_at"] is None or set_at > zd["last_hold_at"]:
                        zd["last_hold_at"] = set_at

                    if set_dt >= seven_days_ago:
                        zd["holds_last_7_days"] += 1
                    if set_dt >= thirty_days_ago:
                        zd["holds_last_30_days"] += 1

                    released_at = getattr(hold, "released_at", None)
                    if released_at and set_at:
                        rel_dt = dt.fromisoformat(released_at.replace("Z", "+00:00"))
                        duration = int((rel_dt - set_dt).total_seconds())
                        zd["durations"].append(duration)
                except (ValueError, TypeError):
                    pass

        patterns: List[HoldZonePatternEntryV1] = []
        for zone_id, zd in zone_data.items():
            zone_name = None
            if self.zone_truth_store and hasattr(self.zone_truth_store, "get_zone_name"):
                zone_name = self.zone_truth_store.get_zone_name(zone_id)

            most_common_state = max(zd["states"].items(), key=lambda x: x[1])[0] if zd["states"] else "auto"
            most_common_reason = max(zd["reasons"].items(), key=lambda x: x[1])[0] if zd["reasons"] else None
            avg_duration = sum(zd["durations"]) / len(zd["durations"]) if zd["durations"] else None

            patterns.append(
                HoldZonePatternEntryV1(
                    zone_id=zone_id,
                    zone_name=zone_name,
                    total_holds=zd["total_holds"],
                    force_on_count=zd["force_on_count"],
                    force_off_count=zd["force_off_count"],
                    avg_hold_duration_seconds=avg_duration,
                    most_common_reason=most_common_reason,
                    most_common_state=most_common_state,
                    last_hold_at=zd["last_hold_at"],
                    holds_last_7_days=zd["holds_last_7_days"],
                    holds_last_30_days=zd["holds_last_30_days"],
                )
            )

        patterns.sort(key=lambda p: p.total_holds, reverse=True)

        self._bump_revision()

        return HoldZonePatternsV1(
            patterns=patterns,
            total_zones=len(patterns),
            zones_with_holds=len([p for p in patterns if p.total_holds > 0]),
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def build_effectiveness_metrics(self) -> HoldEffectivenessMetricsV1:
        """Build Hold-Effectiveness-Metriken."""
        holds = self.hold_store.get_all_holds() if hasattr(self.hold_store, "get_all_holds") else []

        total_holds = len(holds)
        holds_with_conflict = 0
        holds_preventing_flapping = 0
        durations_before_stable: List[float] = []
        zones_benefiting = set()
        zones_without_benefit = set()

        for hold in holds:
            zone_id = hold.zone_id
            hold_state = getattr(hold, "hold_state", "auto")

            if hold_state in ("force_on", "force_off"):
                holds_preventing_flapping += 1
                zones_benefiting.add(zone_id)

                released_at = getattr(hold, "released_at", None)
                set_at = getattr(hold, "set_at", getattr(hold, "created_at", None))
                if released_at and set_at:
                    try:
                        from datetime import datetime as dt

                        set_dt = dt.fromisoformat(set_at.replace("Z", "+00:00"))
                        rel_dt = dt.fromisoformat(released_at.replace("Z", "+00:00"))
                        durations_before_stable.append((rel_dt - set_dt).total_seconds())
                    except (ValueError, TypeError):
                        pass
            else:
                zones_without_benefit.add(zone_id)

        conflict_rate = holds_with_conflict / total_holds if total_holds > 0 else 0.0
        flapping_prevention_rate = holds_preventing_flapping / total_holds if total_holds > 0 else 0.0
        avg_duration_before_stable = (
            sum(durations_before_stable) / len(durations_before_stable) if durations_before_stable else None
        )

        effectiveness_score = flapping_prevention_rate * 0.7 + (1.0 - conflict_rate) * 0.3

        self._bump_revision()

        return HoldEffectivenessMetricsV1(
            total_holds_analyzed=total_holds,
            holds_with_sensor_conflict=holds_with_conflict,
            conflict_rate=conflict_rate,
            holds_preventing_flapping=holds_preventing_flapping,
            flapping_prevention_rate=flapping_prevention_rate,
            avg_hold_duration_before_stable=avg_duration_before_stable,
            zones_benefiting_from_holds=len(zones_benefiting),
            zones_without_benefit=len(zones_without_benefit),
            effectiveness_score=effectiveness_score,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def build_summary(self) -> HoldAnalyticsSummaryV1:
        """Build vollständige Analytics-Summary."""
        usage = self.build_usage_history()
        patterns = self.build_zone_patterns()
        effectiveness = self.build_effectiveness_metrics()

        self._bump_revision()

        return HoldAnalyticsSummaryV1(
            usage=usage,
            patterns=patterns,
            effectiveness=effectiveness,
            summary_revision=self._revision,
            latest_change_at=self._latest_change_at,
        )
