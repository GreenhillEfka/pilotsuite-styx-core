"""Appliance Fingerprinting — Device identification from power signatures (v5.12.0).

Learns characteristic power draw patterns (fingerprints) for household
appliances and identifies running devices from real-time power data.

Features:
- Record power signatures per appliance (startup, running, shutdown phases)
- Build device fingerprint library
- Match live power readings to known fingerprints
- Track usage statistics per device (runs, total kWh, avg duration)
"""

from __future__ import annotations

import hashlib
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class PowerSample:
    """Single power measurement."""

    timestamp: str
    watts: float
    device_id: str = ""


@dataclass
class Fingerprint:
    """Characteristic power signature for an appliance."""

    device_id: str
    device_name: str
    device_type: str  # washer, dryer, dishwasher, oven, ev_charger, etc.
    avg_power_watts: float
    peak_power_watts: float
    min_power_watts: float
    stddev_watts: float
    typical_duration_minutes: float
    typical_kwh: float
    sample_count: int
    phases: list[dict]  # [{name, avg_watts, duration_pct}]
    created_at: str
    updated_at: str


@dataclass
class DeviceMatch:
    """Result of matching live power to a known fingerprint."""

    device_id: str
    device_name: str
    device_type: str
    confidence: float  # 0-1
    matched_phase: str
    estimated_remaining_minutes: float
    current_power_watts: float


@dataclass
class UsageStats:
    """Usage statistics for a fingerprinted device."""

    device_id: str
    device_name: str
    total_runs: int
    total_kwh: float
    avg_duration_minutes: float
    avg_power_watts: float
    last_run: str
    runs_this_week: int
    runs_this_month: int


# ── Constants ───────────────────────────────────────────────────────────────

# Minimum samples to create a fingerprint
MIN_SAMPLES = 3

# Power change threshold to detect start/stop (watts)
POWER_CHANGE_THRESHOLD = 50.0

# Match confidence thresholds
CONFIDENCE_HIGH = 0.80
CONFIDENCE_MEDIUM = 0.50

# Known appliance archetypes for initial bootstrapping
_ARCHETYPES: dict[str, dict] = {
    "washer": {
        "avg_watts": 500, "peak_watts": 2200, "duration_min": 90,
        "phases": [
            {"name": "Heizen", "avg_watts": 2000, "duration_pct": 15},
            {"name": "Waschen", "avg_watts": 300, "duration_pct": 60},
            {"name": "Schleudern", "avg_watts": 500, "duration_pct": 25},
        ],
    },
    "dryer": {
        "avg_watts": 2500, "peak_watts": 3000, "duration_min": 120,
        "phases": [
            {"name": "Aufheizen", "avg_watts": 2800, "duration_pct": 20},
            {"name": "Trocknen", "avg_watts": 2500, "duration_pct": 70},
            {"name": "Abkuehlen", "avg_watts": 200, "duration_pct": 10},
        ],
    },
    "dishwasher": {
        "avg_watts": 1200, "peak_watts": 2100, "duration_min": 120,
        "phases": [
            {"name": "Vorspuelen", "avg_watts": 100, "duration_pct": 10},
            {"name": "Heizen", "avg_watts": 2000, "duration_pct": 25},
            {"name": "Waschen", "avg_watts": 800, "duration_pct": 50},
            {"name": "Trocknen", "avg_watts": 600, "duration_pct": 15},
        ],
    },
    "oven": {
        "avg_watts": 2500, "peak_watts": 3500, "duration_min": 60,
        "phases": [
            {"name": "Aufheizen", "avg_watts": 3200, "duration_pct": 30},
            {"name": "Halten", "avg_watts": 1500, "duration_pct": 70},
        ],
    },
    "ev_charger": {
        "avg_watts": 7400, "peak_watts": 11000, "duration_min": 240,
        "phases": [
            {"name": "Laden", "avg_watts": 7400, "duration_pct": 95},
            {"name": "Balancing", "avg_watts": 500, "duration_pct": 5},
        ],
    },
    "heat_pump": {
        "avg_watts": 2000, "peak_watts": 4000, "duration_min": 180,
        "phases": [
            {"name": "Anlauf", "avg_watts": 3500, "duration_pct": 10},
            {"name": "Betrieb", "avg_watts": 1800, "duration_pct": 80},
            {"name": "Abtauen", "avg_watts": 2500, "duration_pct": 10},
        ],
    },
}


# ── Main Engine ─────────────────────────────────────────────────────────────

class ApplianceFingerprinter:
    """Learns and identifies appliance power signatures."""

    def __init__(self) -> None:
        self._fingerprints: dict[str, Fingerprint] = {}
        self._recordings: dict[str, list[list[PowerSample]]] = defaultdict(list)
        self._usage_log: dict[str, list[dict]] = defaultdict(list)
        self._active_devices: dict[str, dict] = {}

        # Bootstrap with archetypes
        self._bootstrap_archetypes()

    # ── Public API ──────────────────────────────────────────────────────

    def record_signature(
        self,
        device_id: str,
        device_name: str,
        device_type: str,
        samples: list[dict],
    ) -> Fingerprint:
        """Record a power signature for learning.

        Parameters
        ----------
        device_id : unique identifier
        device_name : human-readable name
        device_type : category (washer, dryer, etc.)
        samples : list of {timestamp, watts} dicts
        """
        parsed = [
            PowerSample(
                timestamp=s.get("timestamp", datetime.now().isoformat()),
                watts=float(s.get("watts", 0)),
                device_id=device_id,
            )
            for s in samples
        ]

        self._recordings[device_id].append(parsed)

        # Build / update fingerprint
        fp = self._build_fingerprint(device_id, device_name, device_type)
        self._fingerprints[device_id] = fp
        return fp

    def identify(self, current_watts: float) -> list[DeviceMatch]:
        """Match current power reading to known fingerprints.

        Returns list of possible matches sorted by confidence.
        """
        if current_watts < POWER_CHANGE_THRESHOLD:
            return []

        matches: list[DeviceMatch] = []

        for fp in self._fingerprints.values():
            confidence, phase = self._match_score(current_watts, fp)
            if confidence >= CONFIDENCE_MEDIUM:
                remaining = self._estimate_remaining(current_watts, fp, phase)
                matches.append(DeviceMatch(
                    device_id=fp.device_id,
                    device_name=fp.device_name,
                    device_type=fp.device_type,
                    confidence=round(confidence, 3),
                    matched_phase=phase,
                    estimated_remaining_minutes=round(remaining, 1),
                    current_power_watts=current_watts,
                ))

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches

    def get_fingerprint(self, device_id: str) -> Optional[Fingerprint]:
        """Get fingerprint for a specific device."""
        return self._fingerprints.get(device_id)

    def get_all_fingerprints(self) -> list[dict]:
        """Get all fingerprints as dicts."""
        return [asdict(fp) for fp in self._fingerprints.values()]

    def log_device_run(
        self,
        device_id: str,
        duration_minutes: float,
        energy_kwh: float,
        avg_watts: float,
    ) -> None:
        """Log a completed device run for usage statistics."""
        self._usage_log[device_id].append({
            "timestamp": datetime.now().isoformat(),
            "duration_minutes": duration_minutes,
            "energy_kwh": energy_kwh,
            "avg_watts": avg_watts,
        })

    def get_usage_stats(self, device_id: str) -> Optional[UsageStats]:
        """Get usage statistics for a device."""
        fp = self._fingerprints.get(device_id)
        if not fp:
            return None

        logs = self._usage_log.get(device_id, [])
        if not logs:
            return UsageStats(
                device_id=device_id,
                device_name=fp.device_name,
                total_runs=0,
                total_kwh=0.0,
                avg_duration_minutes=fp.typical_duration_minutes,
                avg_power_watts=fp.avg_power_watts,
                last_run="",
                runs_this_week=0,
                runs_this_month=0,
            )

        now = datetime.now()
        week_ago = (now - timedelta(days=7)).isoformat()
        month_ago = (now - timedelta(days=30)).isoformat()

        total_kwh = sum(l["energy_kwh"] for l in logs)
        avg_dur = statistics.mean(l["duration_minutes"] for l in logs)
        avg_watts = statistics.mean(l["avg_watts"] for l in logs)
        runs_week = sum(1 for l in logs if l["timestamp"] >= week_ago)
        runs_month = sum(1 for l in logs if l["timestamp"] >= month_ago)

        return UsageStats(
            device_id=device_id,
            device_name=fp.device_name,
            total_runs=len(logs),
            total_kwh=round(total_kwh, 2),
            avg_duration_minutes=round(avg_dur, 1),
            avg_power_watts=round(avg_watts, 0),
            last_run=logs[-1]["timestamp"],
            runs_this_week=runs_week,
            runs_this_month=runs_month,
        )

    def get_all_usage_stats(self) -> list[dict]:
        """Get usage stats for all fingerprinted devices."""
        stats = []
        for device_id in self._fingerprints:
            s = self.get_usage_stats(device_id)
            if s:
                stats.append(asdict(s))
        return stats

    # ── Internal ────────────────────────────────────────────────────────

    def _bootstrap_archetypes(self) -> None:
        """Seed fingerprint library with known appliance archetypes."""
        now = datetime.now().isoformat()
        for dtype, arch in _ARCHETYPES.items():
            device_id = f"archetype_{dtype}"
            kwh = arch["avg_watts"] * arch["duration_min"] / 60000.0
            self._fingerprints[device_id] = Fingerprint(
                device_id=device_id,
                device_name=dtype.replace("_", " ").title(),
                device_type=dtype,
                avg_power_watts=arch["avg_watts"],
                peak_power_watts=arch["peak_watts"],
                min_power_watts=arch.get("min_watts", 50),
                stddev_watts=arch["avg_watts"] * 0.3,
                typical_duration_minutes=arch["duration_min"],
                typical_kwh=round(kwh, 2),
                sample_count=0,
                phases=arch["phases"],
                created_at=now,
                updated_at=now,
            )

    def _build_fingerprint(
        self, device_id: str, device_name: str, device_type: str,
    ) -> Fingerprint:
        """Build/update fingerprint from all recorded signatures."""
        all_samples: list[PowerSample] = []
        durations: list[float] = []

        for recording in self._recordings[device_id]:
            all_samples.extend(recording)
            if len(recording) >= 2:
                try:
                    t0 = datetime.fromisoformat(recording[0].timestamp)
                    t1 = datetime.fromisoformat(recording[-1].timestamp)
                    durations.append((t1 - t0).total_seconds() / 60.0)
                except (ValueError, TypeError):
                    pass

        watts_values = [s.watts for s in all_samples]
        if not watts_values:
            watts_values = [0.0]

        avg_w = statistics.mean(watts_values)
        peak_w = max(watts_values)
        min_w = min(watts_values)
        std_w = statistics.stdev(watts_values) if len(watts_values) > 1 else 0.0
        avg_dur = statistics.mean(durations) if durations else 60.0
        typical_kwh = avg_w * avg_dur / 60000.0

        # Derive phases from recordings
        phases = self._detect_phases(watts_values)

        now = datetime.now().isoformat()
        existing = self._fingerprints.get(device_id)
        created = existing.created_at if existing else now

        return Fingerprint(
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            avg_power_watts=round(avg_w, 0),
            peak_power_watts=round(peak_w, 0),
            min_power_watts=round(min_w, 0),
            stddev_watts=round(std_w, 1),
            typical_duration_minutes=round(avg_dur, 1),
            typical_kwh=round(typical_kwh, 3),
            sample_count=len(self._recordings[device_id]),
            phases=phases,
            created_at=created,
            updated_at=now,
        )

    @staticmethod
    def _detect_phases(watts_values: list[float]) -> list[dict]:
        """Simple phase detection by splitting into high/medium/low power segments."""
        if len(watts_values) < 3:
            return [{"name": "Betrieb", "avg_watts": statistics.mean(watts_values) if watts_values else 0, "duration_pct": 100}]

        overall_avg = statistics.mean(watts_values)
        overall_std = statistics.stdev(watts_values) if len(watts_values) > 1 else 0

        high_thresh = overall_avg + overall_std * 0.5
        low_thresh = max(overall_avg - overall_std * 0.5, 0)

        high_samples = [w for w in watts_values if w >= high_thresh]
        mid_samples = [w for w in watts_values if low_thresh <= w < high_thresh]
        low_samples = [w for w in watts_values if w < low_thresh]

        total = len(watts_values)
        phases = []

        if high_samples:
            phases.append({
                "name": "Hochlast",
                "avg_watts": round(statistics.mean(high_samples), 0),
                "duration_pct": round(len(high_samples) / total * 100, 1),
            })
        if mid_samples:
            phases.append({
                "name": "Normalbetrieb",
                "avg_watts": round(statistics.mean(mid_samples), 0),
                "duration_pct": round(len(mid_samples) / total * 100, 1),
            })
        if low_samples:
            phases.append({
                "name": "Niedriglast",
                "avg_watts": round(statistics.mean(low_samples), 0),
                "duration_pct": round(len(low_samples) / total * 100, 1),
            })

        return phases if phases else [{"name": "Betrieb", "avg_watts": round(overall_avg, 0), "duration_pct": 100}]

    @staticmethod
    def _match_score(watts: float, fp: Fingerprint) -> tuple[float, str]:
        """Score how well a power reading matches a fingerprint."""
        best_conf = 0.0
        best_phase = ""

        # Match against each phase
        for phase in fp.phases:
            phase_watts = phase["avg_watts"]
            if phase_watts == 0:
                continue
            # Gaussian-like score
            diff = abs(watts - phase_watts)
            sigma = max(fp.stddev_watts, phase_watts * 0.2)
            score = math.exp(-0.5 * (diff / sigma) ** 2)
            if score > best_conf:
                best_conf = score
                best_phase = phase["name"]

        # Also try overall average
        if fp.avg_power_watts > 0:
            diff = abs(watts - fp.avg_power_watts)
            sigma = max(fp.stddev_watts, fp.avg_power_watts * 0.2)
            overall_score = math.exp(-0.5 * (diff / sigma) ** 2)
            if overall_score > best_conf:
                best_conf = overall_score
                best_phase = "Normalbetrieb"

        return best_conf, best_phase

    @staticmethod
    def _estimate_remaining(watts: float, fp: Fingerprint, phase: str) -> float:
        """Rough estimate of remaining run time based on matched phase."""
        total_min = fp.typical_duration_minutes

        # Find phase position
        elapsed_pct = 0.0
        for p in fp.phases:
            if p["name"] == phase:
                # Assume we're halfway through this phase
                elapsed_pct += p["duration_pct"] / 2
                break
            elapsed_pct += p["duration_pct"]

        remaining_pct = max(0, 100 - elapsed_pct) / 100.0
        return total_min * remaining_pct
