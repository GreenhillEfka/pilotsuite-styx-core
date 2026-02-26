"""Presence Engine -- Multi-sensor Bayesian presence detection per Habitus zone.

Accepts updates from multiple sensor types (PIR, mmWave, BLE, device_tracker,
media_player activity) and produces a per-zone presence state with a
confidence score derived via Bayesian inference.

Each sensor contributes an independent probability that the zone is occupied.
Sensors have configurable weights and per-sensor decay timers.  When all
sensors go silent, a configurable grace period keeps the zone marked as
"grace_period" before transitioning to "vacant".

Thread-safety: all mutable state is protected by ``_lock``.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

_LOGGER = logging.getLogger(__name__)

# ---- Sensor type -> default prior probability ----
# These represent P(sensor_active | occupied) for Bayesian update.
_DEFAULT_PRIOR: dict[str, float] = {
    "motion": 0.80,
    "presence": 0.90,
    "mmwave": 0.95,
    "device_tracker": 0.70,
    "media_activity": 0.60,
}

# Background false-positive rate: P(sensor_active | vacant)
_FALSE_POSITIVE_RATE: dict[str, float] = {
    "motion": 0.05,
    "presence": 0.02,
    "mmwave": 0.01,
    "device_tracker": 0.10,
    "media_activity": 0.03,
}

# Base prior: probability that a zone is occupied before any evidence
_BASE_PRIOR_OCCUPIED = 0.30


# ---- Data Models -----------------------------------------------------------


@dataclass
class SensorConfig:
    """Configuration for a single sensor contributing to presence detection."""

    entity_id: str
    sensor_type: str = "motion"  # motion, presence, mmwave, device_tracker, media_activity
    weight: float = 1.0  # Bayesian weight multiplier
    decay_s: int = 300  # per-sensor decay in seconds

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SensorConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class SensorState:
    """Runtime state of a single sensor."""

    entity_id: str
    sensor_type: str = "motion"
    active: bool = False
    last_active_ts: float = 0.0
    weight: float = 1.0
    decay_s: int = 300


@dataclass
class ZonePresenceState:
    """Aggregated presence state for a single zone."""

    zone_id: str
    occupied: bool = False
    confidence: float = 0.0
    state: str = "vacant"  # occupied, vacant, grace_period
    active_sensors: list[str] = field(default_factory=list)
    last_activity_ts: float = 0.0
    last_vacancy_ts: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---- Engine ----------------------------------------------------------------


class PresenceEngine:
    """Multi-sensor Bayesian presence detection engine.

    Each zone can have multiple sensors.  The engine tracks per-sensor
    activation state and uses Bayesian inference to compute a combined
    occupancy confidence for the zone.

    Lifecycle:
        1. ``register_sensor(zone_id, config)`` -- add a sensor to a zone.
        2. ``update_sensor(zone_id, entity_id, active, sensor_type)`` -- push
           sensor state change.
        3. ``evaluate_presence(zone_id)`` -- compute current presence state.

    Thread-safe via ``_lock``.
    """

    def __init__(self, default_timeout_s: int = 300) -> None:
        self._lock = threading.Lock()
        self._default_timeout_s = default_timeout_s

        # zone_id -> { entity_id -> SensorState }
        self._zone_sensors: dict[str, dict[str, SensorState]] = {}

        # zone_id -> ZonePresenceState (cached last evaluation)
        self._zone_states: dict[str, ZonePresenceState] = {}

        # zone_id -> timeout_s (grace period per zone)
        self._zone_timeouts: dict[str, int] = {}

        _LOGGER.info(
            "PresenceEngine initialized (default_timeout=%ds)", default_timeout_s
        )

    # ---- Sensor registration -----------------------------------------------

    def register_sensor(self, zone_id: str, config: SensorConfig) -> None:
        """Register a sensor for a zone.

        If the sensor already exists it will be updated with the new config.
        """
        with self._lock:
            if zone_id not in self._zone_sensors:
                self._zone_sensors[zone_id] = {}
            self._zone_sensors[zone_id][config.entity_id] = SensorState(
                entity_id=config.entity_id,
                sensor_type=config.sensor_type,
                weight=config.weight,
                decay_s=config.decay_s,
            )
            # Ensure zone state exists
            if zone_id not in self._zone_states:
                self._zone_states[zone_id] = ZonePresenceState(zone_id=zone_id)

    def register_sensors(self, zone_id: str, configs: list[SensorConfig]) -> None:
        """Register multiple sensors for a zone at once."""
        for cfg in configs:
            self.register_sensor(zone_id, cfg)

    def clear_zone(self, zone_id: str) -> None:
        """Remove all sensors and state for a zone."""
        with self._lock:
            self._zone_sensors.pop(zone_id, None)
            self._zone_states.pop(zone_id, None)
            self._zone_timeouts.pop(zone_id, None)

    def set_zone_timeout(self, zone_id: str, timeout_s: int) -> None:
        """Set the grace-period timeout for a zone."""
        with self._lock:
            self._zone_timeouts[zone_id] = max(0, timeout_s)

    # ---- Sensor updates ----------------------------------------------------

    def update_sensor(
        self,
        zone_id: str,
        entity_id: str,
        active: bool,
        sensor_type: str = "motion",
    ) -> ZonePresenceState:
        """Push a sensor state change and re-evaluate the zone.

        If the sensor was not previously registered it will be auto-created
        with default settings derived from ``sensor_type``.

        Parameters
        ----------
        zone_id : str
            The zone this sensor belongs to.
        entity_id : str
            The HA entity (e.g. ``binary_sensor.kitchen_motion``).
        active : bool
            Whether the sensor is currently reporting presence.
        sensor_type : str
            One of: motion, presence, mmwave, device_tracker, media_activity.

        Returns
        -------
        ZonePresenceState
            The updated presence state for the zone.
        """
        now = time.time()

        with self._lock:
            # Auto-register sensor if not known
            if zone_id not in self._zone_sensors:
                self._zone_sensors[zone_id] = {}
            sensors = self._zone_sensors[zone_id]

            if entity_id not in sensors:
                sensors[entity_id] = SensorState(
                    entity_id=entity_id,
                    sensor_type=sensor_type,
                    weight=1.0,
                    decay_s=self._default_timeout_s,
                )

            sensor = sensors[entity_id]
            sensor.active = active
            sensor.sensor_type = sensor_type
            if active:
                sensor.last_active_ts = now

            # Ensure zone state exists
            if zone_id not in self._zone_states:
                self._zone_states[zone_id] = ZonePresenceState(zone_id=zone_id)

        # Re-evaluate presence (outside lock -- _evaluate is self-locking)
        return self._evaluate_locked(zone_id, now)

    # ---- Presence evaluation -----------------------------------------------

    def evaluate_presence(self, zone_id: str) -> ZonePresenceState:
        """Compute current presence state for a zone.

        Returns a ``ZonePresenceState`` with confidence score and state
        (``occupied``, ``grace_period``, or ``vacant``).
        """
        return self._evaluate_locked(zone_id, time.time())

    def _evaluate_locked(self, zone_id: str, now: float) -> ZonePresenceState:
        """Internal evaluation with explicit timestamp."""
        with self._lock:
            sensors = self._zone_sensors.get(zone_id, {})
            state = self._zone_states.get(zone_id)
            if state is None:
                state = ZonePresenceState(zone_id=zone_id)
                self._zone_states[zone_id] = state

            timeout_s = self._zone_timeouts.get(zone_id, self._default_timeout_s)

            # Collect active and recently-active sensors
            active_ids: list[str] = []
            last_activity = 0.0

            for sensor in sensors.values():
                if sensor.active:
                    active_ids.append(sensor.entity_id)
                    last_activity = max(last_activity, sensor.last_active_ts)
                elif sensor.last_active_ts > 0:
                    elapsed = now - sensor.last_active_ts
                    if elapsed <= sensor.decay_s:
                        # Sensor within its individual decay window -- still
                        # contributes (at reduced confidence)
                        active_ids.append(sensor.entity_id)
                    last_activity = max(last_activity, sensor.last_active_ts)

            # Bayesian confidence
            confidence = self._bayesian_confidence(sensors, now)

            # Determine zone state
            if confidence >= 0.50 and active_ids:
                zone_state = "occupied"
                occupied = True
            elif last_activity > 0 and (now - last_activity) <= timeout_s:
                zone_state = "grace_period"
                occupied = True  # still treated as occupied during grace
            else:
                zone_state = "vacant"
                occupied = False

            # Update cached state
            state.occupied = occupied
            state.confidence = round(confidence, 4)
            state.state = zone_state
            state.active_sensors = active_ids

            if last_activity > 0:
                state.last_activity_ts = last_activity

            if zone_state == "vacant" and state.last_vacancy_ts == 0.0:
                state.last_vacancy_ts = now
            elif zone_state != "vacant":
                state.last_vacancy_ts = 0.0

            return ZonePresenceState(
                zone_id=state.zone_id,
                occupied=state.occupied,
                confidence=state.confidence,
                state=state.state,
                active_sensors=list(state.active_sensors),
                last_activity_ts=state.last_activity_ts,
                last_vacancy_ts=state.last_vacancy_ts,
            )

    def _bayesian_confidence(
        self,
        sensors: dict[str, SensorState],
        now: float,
    ) -> float:
        """Compute Bayesian occupancy confidence from all sensors.

        Uses the odds form of Bayes' theorem for iterative updates:

            odds_posterior = odds_prior * prod(likelihood_ratio_i)

        where likelihood_ratio = P(sensor_active | occupied) /
                                 P(sensor_active | vacant)

        Inactive sensors contribute the complement ratio.
        Sensors within their decay window contribute a time-decayed ratio.
        """
        if not sensors:
            return 0.0

        # Start with base prior odds
        prior = _BASE_PRIOR_OCCUPIED
        odds = prior / (1.0 - prior)

        for sensor in sensors.values():
            stype = sensor.sensor_type
            p_active_given_occ = _DEFAULT_PRIOR.get(stype, 0.80)
            p_active_given_vac = _FALSE_POSITIVE_RATE.get(stype, 0.05)

            if sensor.active:
                # Sensor is currently active
                lr = (p_active_given_occ / max(p_active_given_vac, 1e-6))
                lr = lr ** sensor.weight  # apply weight
                odds *= lr
            elif sensor.last_active_ts > 0:
                elapsed = now - sensor.last_active_ts
                if elapsed <= sensor.decay_s and sensor.decay_s > 0:
                    # Sensor within decay window -- time-weighted contribution
                    decay_factor = 1.0 - (elapsed / sensor.decay_s)
                    lr = (p_active_given_occ / max(p_active_given_vac, 1e-6))
                    lr_effective = 1.0 + (lr - 1.0) * decay_factor
                    lr_effective = lr_effective ** sensor.weight
                    odds *= lr_effective
                else:
                    # Sensor has fully decayed -- provide evidence of vacancy
                    lr_absent = (1.0 - p_active_given_occ) / max(
                        1.0 - p_active_given_vac, 1e-6
                    )
                    odds *= lr_absent ** sensor.weight
            else:
                # Sensor has never been activated -- treat as neutral (no
                # evidence).  A sensor that has never fired should not push
                # the odds toward vacancy; it simply has not been observed.
                pass

        # Convert odds back to probability
        confidence = odds / (1.0 + odds)
        # Clamp to [0, 1]
        return max(0.0, min(1.0, confidence))

    # ---- Query helpers -----------------------------------------------------

    def is_zone_occupied(self, zone_id: str) -> bool:
        """Quick check if a zone is currently occupied (or in grace period)."""
        state = self.evaluate_presence(zone_id)
        return state.occupied

    def get_zone_state(self, zone_id: str) -> dict[str, Any]:
        """Return the current presence state as a dict."""
        return self.evaluate_presence(zone_id).to_dict()

    def get_all_states(self) -> list[dict[str, Any]]:
        """Return presence states for all registered zones."""
        results: list[dict[str, Any]] = []
        with self._lock:
            zone_ids = list(self._zone_sensors.keys())
        for zid in zone_ids:
            results.append(self.evaluate_presence(zid).to_dict())
        return results

    def get_registered_sensors(self, zone_id: str) -> list[dict[str, Any]]:
        """Return the sensor configurations for a zone."""
        with self._lock:
            sensors = self._zone_sensors.get(zone_id, {})
            return [
                {
                    "entity_id": s.entity_id,
                    "sensor_type": s.sensor_type,
                    "active": s.active,
                    "last_active_ts": s.last_active_ts,
                    "weight": s.weight,
                    "decay_s": s.decay_s,
                }
                for s in sensors.values()
            ]


__all__ = [
    "PresenceEngine",
    "SensorConfig",
    "SensorState",
    "ZonePresenceState",
]
