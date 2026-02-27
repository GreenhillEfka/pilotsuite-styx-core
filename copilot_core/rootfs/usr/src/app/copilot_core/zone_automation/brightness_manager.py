"""Brightness Manager -- Per-room brightness management with indoor/outdoor ratio.

Tracks indoor and outdoor lux readings per zone, computes relative brightness
ratios, determines whether artificial lighting is needed, and suggests dimming
percentages.

Features:
    - Multiple indoor brightness sensors per zone.
    - Cloud-resilient exponential moving average filter to smooth sensor jitter
      and resist cloud connectivity blips.
    - Outdoor reference sensor (shared or per-zone).
    - Configurable target lux per zone.
    - Artificial-light-need calculation with suggested dimming percentage.

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

# Default smoothing factor for exponential moving average.
# Closer to 1.0 = more responsive, closer to 0.0 = smoother.
_DEFAULT_EMA_ALPHA = 0.3

# If a sensor reading hasn't been updated in this many seconds, consider it
# stale and reduce its influence.
_STALE_THRESHOLD_S = 600  # 10 minutes


# ---- Data Models -----------------------------------------------------------


@dataclass
class BrightnessSensorReading:
    """Single lux sensor reading with EMA smoothing."""

    entity_id: str
    raw_lux: float = 0.0
    smoothed_lux: float = 0.0
    last_update_ts: float = 0.0
    sample_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ZoneBrightnessState:
    """Aggregated brightness state for a single zone."""

    zone_id: str
    # Indoor
    indoor_avg_lux: float = 0.0
    indoor_sensor_count: int = 0
    # Outdoor
    outdoor_lux: float = 0.0
    outdoor_sensor_id: str = ""
    # Computed
    brightness_ratio: float = 0.0  # indoor / outdoor (0..inf)
    artificial_light_needed: bool = True
    suggested_brightness_pct: int = 100
    deficit_lux: float = 0.0
    target_lux: float = 300.0
    last_evaluation_ts: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---- Manager ---------------------------------------------------------------


class BrightnessManager:
    """Per-zone brightness tracking and artificial light need calculation.

    Features:
        - EMA-smoothed indoor/outdoor lux tracking
        - Relative brightness (indoor/outdoor ratio) mode
        - Sun occlusion transient filter: ignores brief outdoor brightness
          drops (e.g. cloud passing over the sun) shorter than
          ``sun_filter_seconds`` to avoid flickering lights on/off.
        - Configurable brightness threshold slider (0-100%)

    Usage:
        mgr = BrightnessManager()
        mgr.configure_zone("kitchen", target_lux=400.0,
                           indoor_sensors=["sensor.kitchen_lux"],
                           outdoor_sensor="sensor.outdoor_lux")
        mgr.update_indoor("kitchen", "sensor.kitchen_lux", 180.0)
        mgr.update_outdoor("sensor.outdoor_lux", 12000.0)
        result = mgr.evaluate("kitchen")
        # result.suggested_brightness_pct => e.g. 55
    """

    def __init__(
        self,
        ema_alpha: float = _DEFAULT_EMA_ALPHA,
        sun_filter_seconds: float = 120.0,
        use_relative_brightness: bool = True,
    ) -> None:
        self._lock = threading.Lock()
        self._ema_alpha = max(0.01, min(1.0, ema_alpha))
        self._sun_filter_seconds = max(0.0, sun_filter_seconds)
        self._use_relative_brightness = use_relative_brightness

        # zone_id -> { entity_id -> BrightnessSensorReading }
        self._indoor_sensors: dict[str, dict[str, BrightnessSensorReading]] = {}

        # entity_id -> BrightnessSensorReading (outdoor sensors are shared)
        self._outdoor_sensors: dict[str, BrightnessSensorReading] = {}

        # zone_id -> outdoor sensor entity_id
        self._zone_outdoor_mapping: dict[str, str] = {}

        # zone_id -> target_lux
        self._zone_targets: dict[str, float] = {}

        # zone_id -> ZoneBrightnessState (cached)
        self._zone_states: dict[str, ZoneBrightnessState] = {}

        # Sun occlusion filter: track outdoor brightness dips per sensor.
        # entity_id -> {"dip_start_ts": float, "pre_dip_lux": float}
        self._outdoor_dip_state: dict[str, dict[str, float]] = {}

        _LOGGER.info(
            "BrightnessManager initialized (ema_alpha=%.2f, sun_filter=%ds, relative=%s)",
            self._ema_alpha,
            int(self._sun_filter_seconds),
            self._use_relative_brightness,
        )

    # ---- Zone configuration ------------------------------------------------

    def configure_zone(
        self,
        zone_id: str,
        target_lux: float = 300.0,
        indoor_sensors: list[str] | None = None,
        outdoor_sensor: str = "",
    ) -> None:
        """Configure or reconfigure a zone's brightness tracking.

        Parameters
        ----------
        zone_id : str
            The Habitus zone identifier.
        target_lux : float
            Desired illumination level in lux (e.g. 300 for general, 500 for
            task lighting).
        indoor_sensors : list[str], optional
            Entity IDs of indoor brightness sensors for this zone.
        outdoor_sensor : str, optional
            Entity ID of the outdoor brightness sensor.  Multiple zones can
            share the same outdoor sensor.
        """
        with self._lock:
            self._zone_targets[zone_id] = max(1.0, target_lux)

            if outdoor_sensor:
                self._zone_outdoor_mapping[zone_id] = outdoor_sensor
                if outdoor_sensor not in self._outdoor_sensors:
                    self._outdoor_sensors[outdoor_sensor] = BrightnessSensorReading(
                        entity_id=outdoor_sensor
                    )

            if indoor_sensors:
                if zone_id not in self._indoor_sensors:
                    self._indoor_sensors[zone_id] = {}
                for sid in indoor_sensors:
                    if sid not in self._indoor_sensors[zone_id]:
                        self._indoor_sensors[zone_id][sid] = BrightnessSensorReading(
                            entity_id=sid
                        )

            # Ensure zone state exists
            if zone_id not in self._zone_states:
                self._zone_states[zone_id] = ZoneBrightnessState(
                    zone_id=zone_id,
                    target_lux=self._zone_targets[zone_id],
                )

    def remove_zone(self, zone_id: str) -> None:
        """Remove all brightness tracking for a zone."""
        with self._lock:
            self._indoor_sensors.pop(zone_id, None)
            self._zone_outdoor_mapping.pop(zone_id, None)
            self._zone_targets.pop(zone_id, None)
            self._zone_states.pop(zone_id, None)

    # ---- Sensor updates ----------------------------------------------------

    def update_indoor(self, zone_id: str, entity_id: str, lux: float) -> None:
        """Push a new indoor lux reading for a sensor in a zone.

        Applies EMA smoothing to resist jitter and cloud blips.

        Parameters
        ----------
        zone_id : str
            The zone this sensor belongs to.
        entity_id : str
            The sensor entity ID.
        lux : float
            The raw lux reading (>= 0).
        """
        lux = max(0.0, lux)
        now = time.time()

        with self._lock:
            if zone_id not in self._indoor_sensors:
                self._indoor_sensors[zone_id] = {}
            sensors = self._indoor_sensors[zone_id]

            if entity_id not in sensors:
                sensors[entity_id] = BrightnessSensorReading(entity_id=entity_id)

            reading = sensors[entity_id]
            reading.raw_lux = lux
            reading.sample_count += 1

            # EMA smoothing
            if reading.sample_count == 1:
                reading.smoothed_lux = lux
            else:
                # Guard against stale readings causing wild jumps
                elapsed = now - reading.last_update_ts if reading.last_update_ts > 0 else 0
                alpha = self._ema_alpha
                if elapsed > _STALE_THRESHOLD_S:
                    # Sensor was stale -- reset to new value more aggressively
                    alpha = min(1.0, alpha * 3.0)
                reading.smoothed_lux = alpha * lux + (1.0 - alpha) * reading.smoothed_lux

            reading.last_update_ts = now

    def update_outdoor(self, entity_id: str, lux: float) -> None:
        """Push a new outdoor lux reading with sun occlusion transient filter.

        The filter suppresses brief outdoor brightness drops (cloud passing
        over the sun). If the outdoor lux drops by more than 30% from the
        smoothed value and the drop is shorter than ``sun_filter_seconds``,
        the smoothed value is held at the pre-dip level instead of following
        the dip downward. Once the dip lasts longer than the filter window,
        the sensor is allowed to track the new lower value normally.

        Parameters
        ----------
        entity_id : str
            The outdoor sensor entity ID.
        lux : float
            The raw lux reading (>= 0).
        """
        lux = max(0.0, lux)
        now = time.time()

        with self._lock:
            if entity_id not in self._outdoor_sensors:
                self._outdoor_sensors[entity_id] = BrightnessSensorReading(
                    entity_id=entity_id
                )

            reading = self._outdoor_sensors[entity_id]
            prev_smoothed = reading.smoothed_lux
            reading.raw_lux = lux
            reading.sample_count += 1

            if reading.sample_count == 1:
                reading.smoothed_lux = lux
                reading.last_update_ts = now
                return

            elapsed = now - reading.last_update_ts if reading.last_update_ts > 0 else 0
            alpha = self._ema_alpha
            if elapsed > _STALE_THRESHOLD_S:
                alpha = min(1.0, alpha * 3.0)

            # ── Sun occlusion transient filter ──────────────────────
            dip_state = self._outdoor_dip_state.get(entity_id)
            dip_threshold_ratio = 0.70  # 30% drop = dip detected

            if prev_smoothed > 50 and lux < prev_smoothed * dip_threshold_ratio:
                # Outdoor brightness dropped significantly
                if dip_state is None:
                    # Start tracking the dip
                    self._outdoor_dip_state[entity_id] = {
                        "dip_start_ts": now,
                        "pre_dip_lux": prev_smoothed,
                    }
                    dip_state = self._outdoor_dip_state[entity_id]

                dip_duration = now - dip_state["dip_start_ts"]
                if self._sun_filter_seconds > 0 and dip_duration < self._sun_filter_seconds:
                    # Dip is still within the filter window -- hold smoothed
                    # at pre-dip level (ignore the transient drop)
                    reading.smoothed_lux = dip_state["pre_dip_lux"]
                    reading.last_update_ts = now
                    return
                else:
                    # Dip lasted longer than filter -- treat as real drop
                    self._outdoor_dip_state.pop(entity_id, None)
            else:
                # No dip or lux recovered -- clear dip state
                self._outdoor_dip_state.pop(entity_id, None)

            # Normal EMA update
            reading.smoothed_lux = alpha * lux + (1.0 - alpha) * reading.smoothed_lux
            reading.last_update_ts = now

    def update_sensor(
        self,
        zone_id: str,
        entity_id: str,
        lux: float,
        is_outdoor: bool = False,
    ) -> None:
        """Generic sensor update -- routes to indoor or outdoor update.

        Convenience method used by the controller when it doesn't know
        the sensor role ahead of time.
        """
        if is_outdoor:
            self.update_outdoor(entity_id, lux)
        else:
            self.update_indoor(zone_id, entity_id, lux)

    # ---- Evaluation --------------------------------------------------------

    def evaluate(self, zone_id: str) -> ZoneBrightnessState:
        """Evaluate brightness for a zone and determine if artificial light
        is needed plus a suggested dimming percentage.

        Returns
        -------
        ZoneBrightnessState
            Contains indoor_avg_lux, outdoor_lux, brightness_ratio,
            artificial_light_needed, suggested_brightness_pct, deficit_lux.
        """
        now = time.time()

        with self._lock:
            target_lux = self._zone_targets.get(zone_id, 300.0)
            indoor_sensors = self._indoor_sensors.get(zone_id, {})
            outdoor_sid = self._zone_outdoor_mapping.get(zone_id, "")
            outdoor_reading = self._outdoor_sensors.get(outdoor_sid)

            # Compute indoor average (only non-stale sensors)
            indoor_values: list[float] = []
            for reading in indoor_sensors.values():
                if reading.sample_count == 0:
                    continue
                age = now - reading.last_update_ts
                if age > _STALE_THRESHOLD_S * 3:
                    # Very stale -- skip entirely
                    continue
                indoor_values.append(reading.smoothed_lux)

            indoor_avg = (
                sum(indoor_values) / len(indoor_values) if indoor_values else 0.0
            )

            # Outdoor lux
            outdoor_lux = 0.0
            if outdoor_reading and outdoor_reading.sample_count > 0:
                outdoor_lux = outdoor_reading.smoothed_lux

            # Brightness ratio: how much natural light reaches indoors
            if outdoor_lux > 0:
                brightness_ratio = indoor_avg / outdoor_lux
            else:
                brightness_ratio = 0.0

            # Deficit: how much more light is needed
            deficit_lux = max(0.0, target_lux - indoor_avg)

            # Determine if artificial light is needed.
            # Two modes:
            #   1. Absolute: compare indoor_avg against target_lux directly.
            #   2. Relative: use the indoor/outdoor brightness ratio. If the
            #      ratio is stable (even when absolute values drop due to
            #      clouds), we don't trigger artificial light. This prevents
            #      false triggers during brief weather changes.
            if self._use_relative_brightness and outdoor_lux > 50:
                # Relative mode: a stable ratio means natural light is
                # proportionally reaching indoors even if absolute values
                # changed. Only trigger lights when the ratio indicates
                # insufficient natural light penetration.
                expected_indoor = outdoor_lux * max(brightness_ratio, 0.01)
                if expected_indoor >= target_lux:
                    artificial_needed = False
                    suggested_pct = 0
                elif indoor_avg >= target_lux:
                    artificial_needed = False
                    suggested_pct = 0
                else:
                    artificial_needed = True
                    ratio = deficit_lux / target_lux
                    suggested_pct = int(math.sqrt(ratio) * 100)
                    suggested_pct = max(5, min(100, suggested_pct))
            elif indoor_avg >= target_lux:
                artificial_needed = False
                suggested_pct = 0
            elif indoor_avg <= 0:
                artificial_needed = True
                suggested_pct = 100
            else:
                artificial_needed = True
                # Proportion of target that's missing
                ratio = deficit_lux / target_lux
                # Map to brightness percentage (non-linear -- sqrt for
                # perceptual linearity)
                suggested_pct = int(math.sqrt(ratio) * 100)
                suggested_pct = max(5, min(100, suggested_pct))

            # Update cached state
            state = self._zone_states.get(zone_id)
            if state is None:
                state = ZoneBrightnessState(zone_id=zone_id)
                self._zone_states[zone_id] = state

            state.indoor_avg_lux = round(indoor_avg, 2)
            state.indoor_sensor_count = len(indoor_values)
            state.outdoor_lux = round(outdoor_lux, 2)
            state.outdoor_sensor_id = outdoor_sid
            state.brightness_ratio = round(brightness_ratio, 4)
            state.artificial_light_needed = artificial_needed
            state.suggested_brightness_pct = suggested_pct
            state.deficit_lux = round(deficit_lux, 2)
            state.target_lux = target_lux
            state.last_evaluation_ts = now

            return ZoneBrightnessState(
                zone_id=state.zone_id,
                indoor_avg_lux=state.indoor_avg_lux,
                indoor_sensor_count=state.indoor_sensor_count,
                outdoor_lux=state.outdoor_lux,
                outdoor_sensor_id=state.outdoor_sensor_id,
                brightness_ratio=state.brightness_ratio,
                artificial_light_needed=state.artificial_light_needed,
                suggested_brightness_pct=state.suggested_brightness_pct,
                deficit_lux=state.deficit_lux,
                target_lux=state.target_lux,
                last_evaluation_ts=state.last_evaluation_ts,
            )

    def evaluate_all(self) -> list[dict[str, Any]]:
        """Evaluate all configured zones and return results."""
        with self._lock:
            zone_ids = list(self._zone_targets.keys())
        return [self.evaluate(zid).to_dict() for zid in zone_ids]

    # ---- Status helpers ----------------------------------------------------

    def get_zone_state(self, zone_id: str) -> dict[str, Any] | None:
        """Return cached brightness state for a zone."""
        with self._lock:
            state = self._zone_states.get(zone_id)
            return state.to_dict() if state else None

    def get_all_states(self) -> list[dict[str, Any]]:
        """Return cached brightness state for all zones."""
        with self._lock:
            return [s.to_dict() for s in self._zone_states.values()]

    def get_indoor_readings(self, zone_id: str) -> list[dict[str, Any]]:
        """Return raw + smoothed readings for all indoor sensors in a zone."""
        with self._lock:
            sensors = self._indoor_sensors.get(zone_id, {})
            return [r.to_dict() for r in sensors.values()]

    def get_outdoor_reading(self, entity_id: str) -> dict[str, Any] | None:
        """Return raw + smoothed reading for an outdoor sensor."""
        with self._lock:
            reading = self._outdoor_sensors.get(entity_id)
            return reading.to_dict() if reading else None


__all__ = [
    "BrightnessManager",
    "BrightnessSensorReading",
    "ZoneBrightnessState",
]
