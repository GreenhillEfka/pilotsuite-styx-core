"""Energy Service - Energy monitoring, anomaly detection, and load shifting.

Provides:
- Energy consumption monitoring via HA entity discovery
- Anomaly detection for unusual patterns
- Load shifting opportunity detection
- Suggestion explainability
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EnergySnapshot:
    """Complete energy status snapshot."""
    timestamp: str
    total_consumption_today: float  # kWh
    total_production_today: float  # kWh (solar/PV)
    current_power: float  # Watts
    peak_power_today: float  # Watts
    anomalies_detected: int
    shifting_opportunities: int
    baselines: dict[str, float]  # device_type -> avg kWh/day


@dataclass
class EnergyAnomaly:
    """Detected energy anomaly."""
    id: str
    timestamp: str
    device_id: str
    device_type: str
    expected_value: float
    actual_value: float
    deviation_percent: float
    severity: str  # low, medium, high
    description: str


@dataclass
class ShiftingOpportunity:
    """Load shifting opportunity."""
    id: str
    timestamp: str
    device_type: str
    reason: str  # e.g., "solar_oversupply", "off_peak_pricing"
    current_cost: float  # EUR/kWh
    optimal_cost: float  # EUR/kWh
    savings_estimate: float  # EUR
    suggested_time_window: tuple[str, str]  # start, end
    confidence: float  # 0-1


# Common HA entity patterns for energy sensors
_CONSUMPTION_PATTERNS = [
    "sensor.energy_consumption_total",
    "sensor.total_energy_consumption",
    "sensor.electricity_consumption",
    "sensor.grid_consumption",
]
_PRODUCTION_PATTERNS = [
    "sensor.energy_production_total",
    "sensor.solar_production_total",
    "sensor.pv_production_total",
    "sensor.solar_energy",
    "sensor.pv_energy",
]
_POWER_PATTERNS = [
    "sensor.power_consumption_now",
    "sensor.power_consumption",
    "sensor.current_power",
    "sensor.grid_power",
]


class EnergyService:
    """Service for energy monitoring and optimization."""

    def __init__(self, hass=None, off_peak_hours: list[int] | None = None):
        """Initialize energy service.

        Args:
            hass: Home Assistant instance (None = standalone/testing mode).
            off_peak_hours: Custom off-peak hour list (default: 0-5, 22-23).
        """
        self.hass = hass
        self._cache: dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes
        self._last_update = 0.0
        self._cache_lock = threading.Lock()

        # Off-peak hours (configurable)
        self._off_peak_hours = off_peak_hours or [0, 1, 2, 3, 4, 5, 22, 23]

        # Baselines (learned over time, these are reasonable defaults)
        self._baselines: dict[str, dict[str, float]] = {
            "washer": {"daily_kwh": 1.5, "peak_watts": 500},
            "dryer": {"daily_kwh": 3.5, "peak_watts": 3000},
            "dishwasher": {"daily_kwh": 1.4, "peak_watts": 1200},
            "ev_charger": {"daily_kwh": 10.0, "peak_watts": 7700},
            "heat_pump": {"daily_kwh": 15.0, "peak_watts": 2500},
            "hvac": {"daily_kwh": 8.0, "peak_watts": 2000},
        }

        # Anomaly thresholds
        self._anomaly_thresholds = {
            "low": 0.15,      # 15% deviation
            "medium": 0.30,   # 30% deviation
            "high": 0.50,     # 50% deviation
        }

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        return (time.time() - self._last_update) < self._cache_ttl

    def _get_timestamp(self) -> str:
        """Get current ISO 8601 UTC timestamp."""
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    @property
    def _hass_available(self) -> bool:
        """Check if HA is available for entity queries."""
        return self.hass is not None and hasattr(self.hass, "states")

    def _read_entity(self, entity_id: str) -> float | None:
        """Safely read a float value from an HA entity."""
        if not self._hass_available:
            return None
        try:
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unavailable", "unknown", ""):
                return float(state.state)
        except (ValueError, TypeError, AttributeError):
            pass
        return None

    def _find_entity_value(self, patterns: list[str]) -> float | None:
        """Try multiple entity patterns and return the first valid value."""
        for entity_id in patterns:
            val = self._read_entity(entity_id)
            if val is not None:
                return val
        return None

    def _find_single_entity_value(self, entity_id: str) -> float | None:
        """Read a single entity's numeric value (v5.1.0 — zone energy API)."""
        return self._read_entity(entity_id)

    def _get_all_energy_entities(self) -> list[str]:
        """Get all energy-related entities from HA."""
        if not self._hass_available:
            return []

        energy_entities = []
        try:
            states = self.hass.states.all() if hasattr(self.hass.states, "all") else []
            for state in states:
                entity_id = state.entity_id
                if any(kw in entity_id for kw in [
                    "energy", "power", "utility_meter",
                    "pv", "solar", "inverter"
                ]):
                    energy_entities.append(entity_id)
        except Exception as e:
            logger.warning("Error fetching energy entities: %s", e)

        return energy_entities

    def _get_consumption_today(self) -> float:
        """Get total energy consumption for today from HA."""
        if not self._hass_available:
            # Standalone/test mode baseline for deterministic snapshots.
            return 12.0
        val = self._find_entity_value(_CONSUMPTION_PATTERNS)
        if val is not None:
            return val
        logger.debug("No consumption entity found, returning 0.0")
        return 0.0

    def _get_production_today(self) -> float:
        """Get total energy production (solar/PV) for today from HA."""
        if not self._hass_available:
            # Standalone/test mode baseline for deterministic snapshots.
            return 2.5
        val = self._find_entity_value(_PRODUCTION_PATTERNS)
        if val is not None:
            return val
        logger.debug("No production entity found, returning 0.0")
        return 0.0

    def _get_current_power(self) -> float:
        """Get current power draw in Watts from HA."""
        if not self._hass_available:
            # Standalone/test mode baseline for deterministic snapshots.
            return 850.0
        val = self._find_entity_value(_POWER_PATTERNS)
        if val is not None:
            return val
        logger.debug("No power entity found, returning 0.0")
        return 0.0

    def _get_peak_power_today(self) -> float:
        """Get peak power draw today from HA."""
        # Peak tracking: use current power as minimum estimate
        current = self._get_current_power()
        cached_peak = self._cache.get("peak_power", 0.0)
        peak = max(current, cached_peak)
        self._cache["peak_power"] = peak
        return peak

    def get_energy_snapshot(self) -> EnergySnapshot:
        """Get complete energy snapshot."""
        with self._cache_lock:
            if self._is_cache_valid() and "snapshot" in self._cache:
                return self._cache["snapshot"]

        snapshot = EnergySnapshot(
            timestamp=self._get_timestamp(),
            total_consumption_today=self._get_consumption_today(),
            total_production_today=self._get_production_today(),
            current_power=self._get_current_power(),
            peak_power_today=self._get_peak_power_today(),
            anomalies_detected=len(self._detect_anomalies()),
            shifting_opportunities=len(self._detect_shifting_opportunities()),
            baselines=self._get_baselines()
        )

        with self._cache_lock:
            self._cache["snapshot"] = snapshot
            self._last_update = time.time()

        return snapshot

    def _get_baselines(self) -> dict[str, float]:
        """Get energy baselines per device type."""
        return {
            device: data["daily_kwh"]
            for device, data in self._baselines.items()
        }

    def detect_anomalies(self) -> list[EnergyAnomaly]:
        """Detect energy consumption anomalies."""
        return self._detect_anomalies()

    def _detect_anomalies(self) -> list[EnergyAnomaly]:
        """Internal anomaly detection."""
        anomalies = []

        current_consumption = self._get_consumption_today()
        if current_consumption <= 0:
            return anomalies

        expected_total = sum(b["daily_kwh"] for b in self._baselines.values())
        expected_total = expected_total * 0.6  # Assume 60% of baseline devices active

        if expected_total > 0:
            deviation = (current_consumption - expected_total) / expected_total

            if abs(deviation) >= self._anomaly_thresholds["high"]:
                severity = "high"
            elif abs(deviation) >= self._anomaly_thresholds["medium"]:
                severity = "medium"
            elif abs(deviation) >= self._anomaly_thresholds["low"]:
                severity = "low"
            else:
                severity = None

            if severity:
                direction = "above" if deviation > 0 else "below"
                anomaly = EnergyAnomaly(
                    id=self._generate_id("anomaly"),
                    timestamp=self._get_timestamp(),
                    device_id="total_consumption",
                    device_type="aggregate",
                    expected_value=expected_total,
                    actual_value=current_consumption,
                    deviation_percent=deviation * 100,
                    severity=severity,
                    description=f"Consumption {abs(deviation)*100:.1f}% {direction} expected"
                )
                anomalies.append(anomaly)

        # Device-specific anomaly checks
        device_checks = [
            ("washer", "sensor.washer_energy"),
            ("dryer", "sensor.dryer_energy"),
            ("dishwasher", "sensor.dishwasher_energy"),
            ("ev_charger", "sensor.ev_charger_energy"),
        ]

        for device_type, entity_id in device_checks:
            current = self._read_entity(entity_id)
            if current is not None:
                expected = self._baselines.get(device_type, {}).get("daily_kwh", 0)
                if expected > 0:
                    deviation = (current - expected) / expected
                    if abs(deviation) >= self._anomaly_thresholds["medium"]:
                        severity = "high" if abs(deviation) >= self._anomaly_thresholds["high"] else "medium"
                        direction = "above" if deviation > 0 else "below"
                        anomaly = EnergyAnomaly(
                            id=self._generate_id("anomaly"),
                            timestamp=self._get_timestamp(),
                            device_id=entity_id,
                            device_type=device_type,
                            expected_value=expected,
                            actual_value=current,
                            deviation_percent=deviation * 100,
                            severity=severity,
                            description=f"{device_type} consumption {abs(deviation)*100:.1f}% {direction} expected"
                        )
                        anomalies.append(anomaly)

        return anomalies

    def detect_shifting_opportunities(self) -> list[ShiftingOpportunity]:
        """Detect load shifting opportunities."""
        return self._detect_shifting_opportunities()

    def _detect_shifting_opportunities(self) -> list[ShiftingOpportunity]:
        """Internal load shifting detection."""
        opportunities = []
        now = datetime.now(timezone.utc)
        current_hour = now.hour

        production = self._get_production_today()
        consumption = self._get_consumption_today()

        # Solar oversupply detection
        if production > 0 and consumption > 0 and production > consumption * 1.5:
            opp = ShiftingOpportunity(
                id=self._generate_id("shift"),
                timestamp=self._get_timestamp(),
                device_type="dishwasher",
                reason="solar_oversupply",
                current_cost=0.30,
                optimal_cost=0.0,
                savings_estimate=round(1.4 * 0.30, 2),
                suggested_time_window=(
                    now.isoformat(timespec="seconds"),
                    (now + timedelta(hours=3)).isoformat(timespec="seconds")
                ),
                confidence=0.85
            )
            opportunities.append(opp)

        # Off-peak pricing windows
        if current_hour in self._off_peak_hours:
            opp = ShiftingOpportunity(
                id=self._generate_id("shift"),
                timestamp=self._get_timestamp(),
                device_type="ev_charger",
                reason="off_peak_pricing",
                current_cost=0.22,
                optimal_cost=0.35,
                savings_estimate=1.00,
                suggested_time_window=(
                    now.isoformat(timespec="seconds"),
                    (now + timedelta(hours=6)).isoformat(timespec="seconds")
                ),
                confidence=0.90
            )
            opportunities.append(opp)
        elif current_hour not in self._off_peak_hours:
            opp = ShiftingOpportunity(
                id=self._generate_id("shift"),
                timestamp=self._get_timestamp(),
                device_type="washer",
                reason="avoid_peak_pricing",
                current_cost=0.35,
                optimal_cost=0.22,
                savings_estimate=0.33,
                suggested_time_window=(
                    (now + timedelta(hours=5)).isoformat(timespec="seconds"),
                    (now + timedelta(hours=10)).isoformat(timespec="seconds")
                ),
                confidence=0.75
            )
            opportunities.append(opp)

        return opportunities

    def explain_suggestion(self, suggestion_id: str) -> dict[str, Any]:
        """Explain why an energy suggestion was made."""
        anomalies = self._detect_anomalies()
        opportunities = self._detect_shifting_opportunities()

        # Strict ID matching for anomalies
        for anomaly in anomalies:
            if anomaly.id == suggestion_id:
                return {
                    "suggestion_id": suggestion_id,
                    "type": "anomaly",
                    "title": "Hoher Energieverbrauch erkannt",
                    "description": anomaly.description,
                    "details": {
                        "expected_kwh": anomaly.expected_value,
                        "actual_kwh": anomaly.actual_value,
                        "deviation_percent": anomaly.deviation_percent,
                        "severity": anomaly.severity
                    },
                    "actions": [
                        "Ueberpruefe ob alle Geraete ausgeschaltet sind",
                        "Pruefe Standby-Verbrauch",
                        "Analysiere Verbrauchsmuster der letzten Woche"
                    ]
                }

        # Strict ID matching for opportunities
        for opp in opportunities:
            if opp.id == suggestion_id:
                return {
                    "suggestion_id": suggestion_id,
                    "type": "shifting",
                    "title": f"Load Shifting: {opp.device_type}",
                    "description": opp.reason.replace("_", " ").title(),
                    "details": {
                        "current_cost_per_kwh": opp.current_cost,
                        "optimal_cost_per_kwh": opp.optimal_cost,
                        "savings_estimate": opp.savings_estimate,
                        "suggested_window": opp.suggested_time_window,
                        "confidence": opp.confidence
                    },
                    "actions": [
                        f"Starte {opp.device_type} im vorgeschlagenen Zeitfenster",
                        f"Geschaetzte Ersparnis: {opp.savings_estimate:.2f} EUR"
                    ]
                }

        return {
            "suggestion_id": suggestion_id,
            "type": "unknown",
            "title": "Vorschlag nicht gefunden",
            "description": "Die Anfrage konnte keinem bekannten Vorschlag zugeordnet werden."
        }

    def get_suppression_status(self) -> dict[str, Any]:
        """Check if energy suggestions should be suppressed."""
        anomalies = self._detect_anomalies()
        high_severity_anomalies = [a for a in anomalies if a.severity == "high"]

        return {
            "suppressed": len(high_severity_anomalies) > 0,
            "reason": f"{len(high_severity_anomalies)} high-severity anomalies detected" if high_severity_anomalies else None,
            "suppress_until": None,
            "recommendations": [
                "Address high-severity anomalies before new suggestions" if high_severity_anomalies else None
            ]
        }

    def get_health(self) -> dict[str, Any]:
        """Get service health status."""
        return {
            "status": "healthy",
            "hass_available": self._hass_available,
            "cache_valid": self._is_cache_valid(),
            "last_update": self._last_update,
            "baselines_configured": len(self._baselines),
            "anomaly_thresholds": self._anomaly_thresholds,
            "energy_entities_found": len(self._get_all_energy_entities()),
        }
