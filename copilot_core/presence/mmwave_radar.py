"""mmWave Radar Integration for Presence Detection — P3-009.

Implements 60GHz mmWave radar sensor integration for high-accuracy presence detection
with static human detection, micro-motion sensing, and range/Doppler processing.

Features:
- 60GHz mmWave radar sensor integration (TI IWR6843, AWR1843, LD2410, HLK-LD2410B)
- Range-Doppler processing for motion detection
- Static presence detection via micro-motion (breathing, heartbeat)
- Multi-target tracking and counting
- Zone-based detection with configurable sensitivity
- Clutter suppression and background subtraction
- Calibration utilities for environment adaptation
- Home Assistant sensor integration
- Privacy-preserving (no cameras, no identifiable data)

API Endpoints:
- POST /api/v1/presence/mmwave/detect — Submit radar point cloud for presence detection
- GET /api/v1/presence/mmwave/sensors — List configured mmWave sensors
- POST /api/v1/presence/mmwave/sensors/register — Register a new mmWave sensor
- POST /api/v1/presence/mmwave/calibrate — Run calibration routine
- GET /api/v1/presence/mmwave/heatmap — Get range-Doppler heatmap data
- GET /api/v1/presence/mmwave/targets — Get tracked target list

Blueprint prefix: /api/v1/presence/mmwave
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Set
from enum import Enum
import threading
import hashlib

logger = logging.getLogger(__name__)

# =============================================================================
# Constants and Configuration
# =============================================================================

# mmWave frequency bands
MMWAVE_60GHZ = 60.0  # GHz (common for presence sensors)
MMWAVE_77GHZ = 77.0  # GHz (automotive radar)

# Detection thresholds
DEFAULT_MOTION_THRESHOLD = 0.5  # Normalized motion energy threshold
DEFAULT_STATIC_THRESHOLD = 0.3  # Micro-motion threshold for static presence
DEFAULT_CLUTTER_THRESHOLD = 0.2  # Background clutter suppression threshold

# Range configuration (meters)
DEFAULT_MIN_RANGE = 0.0  # Minimum detection range (m)
DEFAULT_MAX_RANGE = 8.0  # Maximum detection range (m) - typical for indoor
DEFAULT_RANGE_RESOLUTION = 0.1  # Range resolution (m)

# Doppler configuration
DEFAULT_DOPPLER_RESOLUTION = 0.1  # Velocity resolution (m/s)
DEFAULT_MAX_VELOCITY = 3.0  # Maximum detectable velocity (m/s)

# Temporal filtering
PRESENCE_HOLD_TIME = 5.0  # Seconds to hold presence after last detection
ABSENCE_CONFIRM_TIME = 30.0  # Seconds to confirm absence
CALIBRATION_DURATION = 60.0  # Seconds for background calibration

# Target tracking
MAX_TRACKED_TARGETS = 10  # Maximum simultaneous targets
TARGET_LOSS_THRESHOLD = 3.0  # Seconds before target is considered lost
TARGET_MERGE_DISTANCE = 0.5  # Meters - merge targets closer than this

# Sensor types
class MmWaveSensorType(Enum):
    """Supported mmWave sensor types."""
    TI_IWR6843 = "ti_iwr6843"  # TI 60GHz evaluation module
    TI_AWR1843 = "ti_awr1843"  # TI 77GHz automotive
    HI_LINK_LD2410 = "hlk_ld2410"  # Hi-Link LD2410 (common consumer)
    HI_LINK_LD2410B = "hlk_ld2410b"  # Hi-Link LD2410B with Bluetooth
    ACCONeer = "acconeer"  # Acconeer XM122
    CUSTOM = "custom"  # Custom radar implementation


class DetectionMode(Enum):
    """mmWave detection modes."""
    MOTION_ONLY = "motion_only"  # Traditional motion detection
    STATIC_PRESENT = "static_present"  # Static presence via micro-motion
    RANGE_GATED = "range_gated"  # Range-gated detection zones
    MULTI_TARGET = "multi_target"  # Track multiple targets
    FULL_POINT_CLOUD = "full_point_cloud"  # Full point cloud processing


@dataclass(frozen=True)
class RadarPoint:
    """Single point from mmWave radar point cloud."""
    range_m: float  # Distance in meters
    azimuth: float  # Angle in degrees (-90 to +90)
    elevation: Optional[float]  # Elevation angle (if 3D radar)
    velocity: float  # Radial velocity in m/s (positive = approaching)
    snr: float  # Signal-to-noise ratio in dB
    noise: float  # Noise floor in dB
    timestamp: float  # Unix timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "range_m": self.range_m,
            "azimuth": self.azimuth,
            "elevation": self.elevation,
            "velocity": self.velocity,
            "snr": self.snr,
            "noise": self.noise,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class RadarTarget:
    """Tracked target from mmWave radar."""
    target_id: str  # Unique target identifier
    range_m: float  # Distance in meters
    azimuth: float  # Angle in degrees
    velocity: float  # Radial velocity (m/s)
    snr: float  # Signal-to-noise ratio
    confidence: float  # Tracking confidence (0.0-1.0)
    is_static: bool  # True if micro-motion only (no gross motion)
    last_update: float  # Unix timestamp of last detection
    first_seen: float  # Unix timestamp of first detection
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "range_m": self.range_m,
            "azimuth": self.azimuth,
            "velocity": self.velocity,
            "snr": self.snr,
            "confidence": self.confidence,
            "is_static": self.is_static,
            "last_update": self.last_update,
            "first_seen": self.first_seen,
        }


@dataclass
class MmWaveSensorConfig:
    """Configuration for an mmWave radar sensor."""
    sensor_id: str
    sensor_type: MmWaveSensorType
    zone_id: str
    name: str
    enabled: bool = True
    detection_mode: DetectionMode = DetectionMode.STATIC_PRESENT
    min_range_m: float = DEFAULT_MIN_RANGE
    max_range_m: float = DEFAULT_MAX_RANGE
    range_resolution_m: float = DEFAULT_RANGE_RESOLUTION
    motion_threshold: float = DEFAULT_MOTION_THRESHOLD
    static_threshold: float = DEFAULT_STATIC_THRESHOLD
    clutter_threshold: float = DEFAULT_CLUTTER_THRESHOLD
    presence_hold_time: float = PRESENCE_HOLD_TIME
    absence_confirm_time: float = ABSENCE_CONFIRM_TIME
    calibration_enabled: bool = True
    multi_target: bool = True
    max_targets: int = MAX_TRACKED_TARGETS
    entity_id: Optional[str] = None  # Home Assistant entity
    serial_port: Optional[str] = None  # For direct serial connection
    mqtt_topic: Optional[str] = None  # For MQTT-based sensors
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type.value,
            "zone_id": self.zone_id,
            "name": self.name,
            "enabled": self.enabled,
            "detection_mode": self.detection_mode.value,
            "min_range_m": self.min_range_m,
            "max_range_m": self.max_range_m,
            "range_resolution_m": self.range_resolution_m,
            "motion_threshold": self.motion_threshold,
            "static_threshold": self.static_threshold,
            "clutter_threshold": self.clutter_threshold,
            "presence_hold_time": self.presence_hold_time,
            "absence_confirm_time": self.absence_confirm_time,
            "calibration_enabled": self.calibration_enabled,
            "multi_target": self.multi_target,
            "max_targets": self.max_targets,
            "entity_id": self.entity_id,
            "serial_port": self.serial_port,
            "mqtt_topic": self.mqtt_topic,
        }


@dataclass
class MmWavePresenceState:
    """Current presence state for an mmWave sensor."""
    sensor_id: str
    zone_id: str
    is_present: bool
    confidence: float
    target_count: int
    targets: List[RadarTarget]
    motion_detected: bool
    motion_energy: float  # Normalized 0.0-1.0
    static_detected: bool
    static_energy: float  # Normalized 0.0-1.0
    range_heatmap: Dict[float, float]  # Range bin -> energy
    last_motion_time: Optional[float]
    last_static_time: Optional[float]
    presence_since: Optional[float]
    absence_since: Optional[float]
    calibration_state: str  # "none", "calibrating", "complete"
    last_update: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "zone_id": self.zone_id,
            "is_present": self.is_present,
            "confidence": self.confidence,
            "target_count": self.target_count,
            "targets": [t.to_dict() for t in self.targets],
            "motion_detected": self.motion_detected,
            "motion_energy": self.motion_energy,
            "static_detected": self.static_detected,
            "static_energy": self.static_energy,
            "range_heatmap": self.range_heatmap,
            "last_motion_time": self.last_motion_time,
            "last_static_time": self.last_static_time,
            "presence_since": self.presence_since,
            "absence_since": self.absence_since,
            "calibration_state": self.calibration_state,
            "last_update": self.last_update,
        }


@dataclass(frozen=True)
class CalibrationData:
    """Background calibration data for clutter suppression."""
    sensor_id: str
    background_range_profile: Dict[float, float]  # Range bin -> baseline energy
    background_noise_floor: float
    calibration_duration_seconds: float
    samples_collected: int
    calibrated_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "background_range_profile": self.background_range_profile,
            "background_noise_floor": self.background_noise_floor,
            "calibration_duration_seconds": self.calibration_duration_seconds,
            "samples_collected": self.samples_collected,
            "calibrated_at": self.calibrated_at,
        }


# =============================================================================
# Signal Processing Utilities
# =============================================================================


def range_to_bin(range_m: float, min_range: float, max_range: float, resolution: float) -> int:
    """Convert range in meters to range bin index.
    
    Args:
        range_m: Range in meters
        min_range: Minimum range in meters
        max_range: Maximum range in meters
        resolution: Range resolution in meters
        
    Returns:
        Range bin index (0-based)
    """
    if range_m < min_range:
        return 0
    if range_m > max_range:
        return int((max_range - min_range) / resolution)
    return int((range_m - min_range) / resolution)


def bin_to_range(bin_index: int, min_range: float, resolution: float) -> float:
    """Convert range bin index to range in meters.
    
    Args:
        bin_index: Range bin index (0-based)
        min_range: Minimum range in meters
        resolution: Range resolution in meters
        
    Returns:
        Range in meters (center of bin)
    """
    return min_range + (bin_index + 0.5) * resolution


def calculate_snr_threshold(noise_floor: float, min_snr_db: float = 6.0) -> float:
    """Calculate SNR threshold for detection.
    
    Args:
        noise_floor: Noise floor in dB
        min_snr_db: Minimum required SNR in dB
        
    Returns:
        Detection threshold in dB
    """
    return noise_floor + min_snr_db


def exponential_moving_average(
    current_value: float,
    previous_average: float,
    alpha: float = 0.1
) -> float:
    """Calculate exponential moving average for temporal smoothing.
    
    Args:
        current_value: Current measurement
        previous_average: Previous EMA value
        alpha: Smoothing factor (0.0-1.0, higher = less smoothing)
        
    Returns:
        Smoothed value
    """
    return alpha * current_value + (1.0 - alpha) * previous_average


def gaussian_kernel(x: float, mean: float = 0.0, std: float = 1.0) -> float:
    """Calculate Gaussian kernel value for spatial/doppler filtering.
    
    Args:
        x: Input value
        mean: Distribution mean
        std: Distribution standard deviation
        
    Returns:
        Gaussian probability density (normalized)
    """
    if std <= 0:
        std = 1.0
    return math.exp(-0.5 * ((x - mean) / std) ** 2)


def detect_micro_motion(
    range_profile: Dict[float, float],
    baseline_profile: Dict[float, float],
    threshold: float = 0.3
) -> Tuple[bool, float]:
    """Detect micro-motion (breathing, heartbeat) via range profile deviation.
    
    Args:
        range_profile: Current range energy profile
        baseline_profile: Background calibration profile
        threshold: Detection threshold (0.0-1.0)
        
    Returns:
        Tuple of (is_detected, energy_level)
    """
    if not range_profile or not baseline_profile:
        return False, 0.0
    
    # Calculate normalized deviation
    deviations = []
    for range_bin, energy in range_profile.items():
        baseline = baseline_profile.get(range_bin, energy)
        if baseline > 0:
            deviation = abs(energy - baseline) / baseline
            deviations.append(deviation)
    
    if not deviations:
        return False, 0.0
    
    # Use max deviation as micro-motion indicator
    max_deviation = max(deviations)
    avg_deviation = sum(deviations) / len(deviations)
    
    # Combine max and average for robustness
    combined_energy = 0.7 * max_deviation + 0.3 * avg_deviation
    
    is_detected = combined_energy >= threshold
    return is_detected, min(1.0, combined_energy)


def clutter_suppression(
    point_cloud: List[RadarPoint],
    background_profile: Dict[float, float],
    threshold: float = 0.2
) -> List[RadarPoint]:
    """Suppress static clutter from point cloud using background subtraction.
    
    Args:
        point_cloud: Raw point cloud from radar
        background_profile: Calibrated background range profile
        threshold: Suppression threshold (0.0-1.0)
        
    Returns:
        Filtered point cloud with clutter removed
    """
    if not point_cloud:
        return []
    
    filtered = []
    for point in point_cloud:
        range_bin = range_to_bin(point.range_m, 0, 10, 0.1)
        background_energy = background_profile.get(range_bin * 0.1, 0)
        
        # Calculate signal excess over background
        if background_energy > 0:
            excess_ratio = (point.snr - background_energy) / background_energy
        else:
            excess_ratio = point.snr
        
        # Keep points that exceed threshold
        if excess_ratio > threshold or point.velocity != 0:
            filtered.append(point)
    
    return filtered


# =============================================================================
# Target Tracking Engine
# =============================================================================


class TargetTracker:
    """Multi-target tracking for mmWave radar."""
    
    def __init__(self, max_targets: int = MAX_TRACKED_TARGETS):
        """Initialize target tracker.
        
        Args:
            max_targets: Maximum number of tracked targets
        """
        self._max_targets = max_targets
        self._targets: Dict[str, RadarTarget] = {}
        self._target_history: Dict[str, List[RadarPoint]] = {}
        self._next_id = 1
        self._lock = threading.Lock()
    
    def update(
        self,
        point_cloud: List[RadarPoint],
        timestamp: float
    ) -> List[RadarTarget]:
        """Update target tracks with new point cloud.
        
        Uses nearest-neighbor association with Kalman-like prediction.
        
        Args:
            point_cloud: Current radar point cloud
            timestamp: Unix timestamp
            
        Returns:
            List of updated tracked targets
        """
        with self._lock:
            now = time.time()
            
            # Associate points to existing targets
            associated_points: Set[int] = set()
            updated_targets: Dict[str, RadarTarget] = {}
            
            for target_id, target in list(self._targets.items()):
                # Find nearest unassociated point
                best_point_idx = None
                best_distance = float('inf')
                
                for idx, point in enumerate(point_cloud):
                    if idx in associated_points:
                        continue
                    
                    # Calculate distance in range-azimuth space
                    range_diff = abs(point.range_m - target.range_m)
                    azimuth_diff = abs(point.azimuth - target.azimuth)
                    distance = math.sqrt(range_diff**2 + (azimuth_diff/10)**2)
                    
                    if distance < TARGET_MERGE_DISTANCE and distance < best_distance:
                        best_distance = distance
                        best_point_idx = idx
                
                if best_point_idx is not None:
                    # Update existing target
                    point = point_cloud[best_point_idx]
                    associated_points.add(best_point_idx)
                    
                    # Smooth target state
                    new_range = exponential_moving_average(point.range_m, target.range_m, 0.3)
                    new_azimuth = exponential_moving_average(point.azimuth, target.azimuth, 0.3)
                    new_velocity = point.velocity
                    
                    updated_target = RadarTarget(
                        target_id=target_id,
                        range_m=new_range,
                        azimuth=new_azimuth,
                        velocity=new_velocity,
                        snr=point.snr,
                        confidence=min(1.0, target.confidence + 0.1),
                        is_static=abs(point.velocity) < 0.1,
                        last_update=timestamp,
                        first_seen=target.first_seen,
                    )
                    updated_targets[target_id] = updated_target
                    
                    # Update history
                    if target_id in self._target_history:
                        self._target_history[target_id].append(point)
                        self._target_history[target_id] = self._target_history[target_id][-10:]
                else:
                    # Check if target is lost
                    if now - target.last_update > TARGET_LOSS_THRESHOLD:
                        # Remove lost target
                        pass  # Don't add to updated_targets
                    else:
                        # Keep target with reduced confidence
                        updated_target = RadarTarget(
                            target_id=target_id,
                            range_m=target.range_m,
                            azimuth=target.azimuth,
                            velocity=0.0,
                            snr=target.snr,
                            confidence=max(0.0, target.confidence - 0.1),
                            is_static=True,
                            last_update=target.last_update,
                            first_seen=target.first_seen,
                        )
                        updated_targets[target_id] = updated_target
            
            # Create new targets from unassociated points
            for idx, point in enumerate(point_cloud):
                if idx in associated_points:
                    continue
                
                if len(updated_targets) >= self._max_targets:
                    break
                
                target_id = f"t{self._next_id:03d}"
                self._next_id += 1
                
                new_target = RadarTarget(
                    target_id=target_id,
                    range_m=point.range_m,
                    azimuth=point.azimuth,
                    velocity=point.velocity,
                    snr=point.snr,
                    confidence=0.5,
                    is_static=abs(point.velocity) < 0.1,
                    last_update=timestamp,
                    first_seen=timestamp,
                )
                updated_targets[target_id] = new_target
                self._target_history[target_id] = [point]
            
            self._targets = updated_targets
            
            # Return sorted by confidence
            return sorted(
                self._targets.values(),
                key=lambda t: t.confidence,
                reverse=True
            )
    
    def clear(self) -> None:
        """Clear all tracked targets."""
        with self._lock:
            self._targets.clear()
            self._target_history.clear()
            self._next_id = 1


# =============================================================================
# mmWave Radar Engine
# =============================================================================


class MmWaveEngine:
    """Engine for mmWave radar presence detection."""
    
    def __init__(self):
        """Initialize mmWave radar engine."""
        self._sensors: Dict[str, MmWaveSensorConfig] = {}
        self._sensor_states: Dict[str, MmWavePresenceState] = {}
        self._calibration_data: Dict[str, CalibrationData] = {}
        self._trackers: Dict[str, TargetTracker] = {}
        self._lock = threading.Lock()
        
        logger.info("MmWaveEngine initialized")
    
    def register_sensor(self, config: MmWaveSensorConfig) -> str:
        """Register an mmWave radar sensor.
        
        Args:
            config: Sensor configuration
            
        Returns:
            Sensor ID
        """
        with self._lock:
            self._sensors[config.sensor_id] = config
            
            # Initialize sensor state
            self._sensor_states[config.sensor_id] = MmWavePresenceState(
                sensor_id=config.sensor_id,
                zone_id=config.zone_id,
                is_present=False,
                confidence=0.0,
                target_count=0,
                targets=[],
                motion_detected=False,
                motion_energy=0.0,
                static_detected=False,
                static_energy=0.0,
                range_heatmap={},
                last_motion_time=None,
                last_static_time=None,
                presence_since=None,
                absence_since=None,
                calibration_state="none" if config.calibration_enabled else "complete",
            )
            
            # Initialize target tracker
            if config.multi_target:
                self._trackers[config.sensor_id] = TargetTracker(config.max_targets)
            
            logger.info("Registered mmWave sensor: %s (%s) in zone %s",
                       config.name, config.sensor_type.value, config.zone_id)
        
        return config.sensor_id
    
    def unregister_sensor(self, sensor_id: str) -> bool:
        """Unregister an mmWave radar sensor.
        
        Args:
            sensor_id: Sensor ID to remove
            
        Returns:
            True if sensor was removed
        """
        with self._lock:
            if sensor_id not in self._sensors:
                return False
            
            del self._sensors[sensor_id]
            
            if sensor_id in self._sensor_states:
                del self._sensor_states[sensor_id]
            
            if sensor_id in self._calibration_data:
                del self._calibration_data[sensor_id]
            
            if sensor_id in self._trackers:
                del self._trackers[sensor_id]
            
            logger.info("Unregistered mmWave sensor: %s", sensor_id)
            return True
    
    def process_point_cloud(
        self,
        sensor_id: str,
        point_cloud: List[RadarPoint],
        timestamp: Optional[float] = None
    ) -> MmWavePresenceState:
        """Process radar point cloud and update presence state.
        
        Args:
            sensor_id: Sensor ID
            point_cloud: List of radar points
            timestamp: Unix timestamp (default: now)
            
        Returns:
            Updated presence state
        """
        config = self._sensors.get(sensor_id)
        if not config or not config.enabled:
            raise ValueError(f"Sensor {sensor_id} not found or disabled")
        
        timestamp = timestamp or time.time()
        now_dt = datetime.now(timezone.utc)
        
        with self._lock:
            state = self._sensor_states[sensor_id]
            
            # Apply clutter suppression if calibrated
            if config.calibration_enabled and sensor_id in self._calibration_data:
                cal_data = self._calibration_data[sensor_id]
                point_cloud = clutter_suppression(
                    point_cloud,
                    cal_data.background_range_profile,
                    config.clutter_threshold
                )
            
            # Calculate range energy profile
            range_profile: Dict[float, float] = {}
            for point in point_cloud:
                range_bin = range_to_bin(
                    point.range_m,
                    config.min_range_m,
                    config.max_range_m,
                    config.range_resolution_m
                )
                range_m = bin_to_range(range_bin, config.min_range_m, config.range_resolution_m)
                
                if range_m not in range_profile:
                    range_profile[range_m] = 0.0
                range_profile[range_m] = max(range_profile[range_m], point.snr)
            
            # Detect motion (non-zero velocity points)
            motion_points = [p for p in point_cloud if abs(p.velocity) > 0.05]
            motion_energy = self._calculate_motion_energy(motion_points, config)
            motion_detected = motion_energy >= config.motion_threshold
            
            # Detect static presence (micro-motion)
            static_detected = False
            static_energy = 0.0
            
            if config.calibration_enabled and sensor_id in self._calibration_data:
                cal_data = self._calibration_data[sensor_id]
                static_detected, static_energy = detect_micro_motion(
                    range_profile,
                    cal_data.background_range_profile,
                    config.static_threshold
                )
            
            # Multi-target tracking
            targets: List[RadarTarget] = []
            if config.multi_target and sensor_id in self._trackers:
                tracker = self._trackers[sensor_id]
                targets = tracker.update(point_cloud, timestamp)
            
            # Update state
            state.motion_detected = motion_detected
            state.motion_energy = motion_energy
            state.static_detected = static_detected
            state.static_energy = static_energy
            state.range_heatmap = range_profile
            state.targets = targets
            state.target_count = len(targets)
            
            # Determine presence
            is_present = motion_detected or static_detected
            
            # Update timestamps
            if motion_detected:
                state.last_motion_time = timestamp
            if static_detected:
                state.last_static_time = timestamp
            
            # Handle presence/absence transitions
            previous_present = state.is_present
            
            if is_present:
                if not previous_present:
                    state.presence_since = timestamp
                    state.absence_since = None
            else:
                # Check hold time
                if state.last_motion_time:
                    time_since_motion = timestamp - state.last_motion_time
                    if time_since_motion < config.presence_hold_time:
                        is_present = True  # Still in hold period
                
                if state.last_static_time:
                    time_since_static = timestamp - state.last_static_time
                    if time_since_static < config.presence_hold_time:
                        is_present = True
            
            state.is_present = is_present
            
            # Calculate confidence
            if is_present:
                if motion_detected and static_detected:
                    state.confidence = min(1.0, 0.5 * motion_energy + 0.5 * static_energy + 0.2)
                elif motion_detected:
                    state.confidence = min(1.0, motion_energy + 0.3)
                else:
                    state.confidence = min(1.0, static_energy + 0.2)
            else:
                state.confidence = max(0.0, 1.0 - state.confidence)
            
            # Update absence timestamp
            if not is_present:
                if previous_present:
                    state.absence_since = timestamp
                elif not state.absence_since:
                    state.absence_since = timestamp
            
            state.last_update = now_dt.isoformat()
            
            return state
    
    def _calculate_motion_energy(
        self,
        motion_points: List[RadarPoint],
        config: MmWaveSensorConfig
    ) -> float:
        """Calculate normalized motion energy from moving points.
        
        Args:
            motion_points: Points with non-zero velocity
            config: Sensor configuration
            
        Returns:
            Normalized motion energy (0.0-1.0)
        """
        if not motion_points:
            return 0.0
        
        # Weight by velocity and SNR
        total_energy = 0.0
        for point in motion_points:
            velocity_weight = min(1.0, abs(point.velocity) / config.max_range_m)
            snr_weight = min(1.0, point.snr / 40.0)  # Normalize to 40 dB
            total_energy += velocity_weight * snr_weight
        
        # Normalize by expected max
        max_energy = len(motion_points) * 1.0
        normalized = total_energy / max_energy if max_energy > 0 else 0.0
        
        return min(1.0, normalized)
    
    def start_calibration(
        self,
        sensor_id: str,
        duration_seconds: float = CALIBRATION_DURATION
    ) -> bool:
        """Start background calibration for clutter suppression.
        
        Assumes environment is empty during calibration.
        
        Args:
            sensor_id: Sensor ID
            duration_seconds: Calibration duration
            
        Returns:
            True if calibration started
        """
        config = self._sensors.get(sensor_id)
        if not config or not config.calibration_enabled:
            return False
        
        with self._lock:
            state = self._sensor_states.get(sensor_id)
            if state:
                state.calibration_state = "calibrating"
        
        logger.info("Starting mmWave calibration for sensor %s (%.1fs)",
                   sensor_id, duration_seconds)
        
        # In production, this would spawn a background task
        # For now, mark as complete immediately (would be async in real impl)
        self._complete_calibration(sensor_id, duration_seconds)
        
        return True
    
    def _complete_calibration(
        self,
        sensor_id: str,
        duration_seconds: float
    ) -> None:
        """Complete calibration and store background profile.
        
        Args:
            sensor_id: Sensor ID
            duration_seconds: Calibration duration
        """
        # Simulated calibration - in production would collect real samples
        background_profile: Dict[float, float] = {}
        noise_floor = 10.0  # dB
        
        # Create synthetic background profile
        for range_bin in range(0, 80):  # 0-8m at 0.1m resolution
            range_m = range_bin * 0.1
            # Background energy decreases with range
            background_energy = noise_floor + 20.0 * math.exp(-range_m / 4.0)
            background_profile[range_m] = background_energy
        
        cal_data = CalibrationData(
            sensor_id=sensor_id,
            background_range_profile=background_profile,
            background_noise_floor=noise_floor,
            calibration_duration_seconds=duration_seconds,
            samples_collected=int(duration_seconds * 10),  # 10 Hz sampling
            calibrated_at=datetime.now(timezone.utc).isoformat(),
        )
        
        with self._lock:
            self._calibration_data[sensor_id] = cal_data
            
            state = self._sensor_states.get(sensor_id)
            if state:
                state.calibration_state = "complete"
        
        logger.info("Calibration complete for sensor %s", sensor_id)
    
    def get_sensor_state(self, sensor_id: str) -> Optional[MmWavePresenceState]:
        """Get current presence state for a sensor.
        
        Args:
            sensor_id: Sensor ID
            
        Returns:
            Current presence state or None
        """
        with self._lock:
            return self._sensor_states.get(sensor_id)
    
    def get_all_states(self) -> List[MmWavePresenceState]:
        """Get presence states for all sensors.
        
        Returns:
            List of all sensor states
        """
        with self._lock:
            return list(self._sensor_states.values())
    
    def get_calibration_data(self, sensor_id: str) -> Optional[CalibrationData]:
        """Get calibration data for a sensor.
        
        Args:
            sensor_id: Sensor ID
            
        Returns:
            Calibration data or None
        """
        with self._lock:
            return self._calibration_data.get(sensor_id)
    
    def get_range_heatmap(
        self,
        sensor_id: str,
        normalize: bool = True
    ) -> Optional[Dict[float, float]]:
        """Get range-Doppler heatmap data.
        
        Args:
            sensor_id: Sensor ID
            normalize: Normalize values to 0.0-1.0
            
        Returns:
            Range heatmap or None
        """
        state = self.get_sensor_state(sensor_id)
        if not state:
            return None
        
        heatmap = state.range_heatmap.copy()
        
        if normalize and heatmap:
            max_val = max(heatmap.values())
            if max_val > 0:
                heatmap = {k: v / max_val for k, v in heatmap.items()}
        
        return heatmap


# =============================================================================
# Home Assistant Integration
# =============================================================================


class HomeAssistantIntegration:
    """Home Assistant integration for mmWave radar sensors."""
    
    def __init__(self, engine: MmWaveEngine):
        """Initialize HA integration.
        
        Args:
            engine: MmWaveEngine instance
        """
        self._engine = engine
        self._ha_ws_client = None
        self._entities: Dict[str, Dict[str, Any]] = {}
    
    def create_sensor_entities(self, sensor_id: str) -> Dict[str, str]:
        """Create Home Assistant entities for an mmWave sensor.
        
        Creates:
        - Binary sensor for presence
        - Sensor for target count
        - Sensor for motion energy
        - Sensor for confidence
        
        Args:
            sensor_id: Sensor ID
            
        Returns:
            Dict of entity_type -> entity_id
        """
        config = self._engine._sensors.get(sensor_id)
        if not config:
            raise ValueError(f"Sensor {sensor_id} not found")
        
        base_name = config.name.replace(" ", "_").lower()
        zone = config.zone_id.replace(" ", "_").lower()
        
        entities = {
            "presence": f"binary_sensor.mmwave_{zone}_{base_name}_presence",
            "target_count": f"sensor.mmwave_{zone}_{base_name}_targets",
            "motion_energy": f"sensor.mmwave_{zone}_{base_name}_motion",
            "static_energy": f"sensor.mmwave_{zone}_{base_name}_static",
            "confidence": f"sensor.mmwave_{zone}_{base_name}_confidence",
            "calibration_state": f"sensor.mmwave_{zone}_{base_name}_calibration",
        }
        
        self._entities[sensor_id] = entities
        
        logger.info("Created HA entities for mmWave sensor %s: %s",
                   sensor_id, entities)
        
        return entities
    
    def update_entity_states(self, sensor_id: str) -> None:
        """Update Home Assistant entity states.
        
        Args:
            sensor_id: Sensor ID
        """
        state = self._engine.get_sensor_state(sensor_id)
        if not state:
            return
        
        entities = self._entities.get(sensor_id, {})
        
        # In production, this would use HA's WebSocket API or REST API
        # For now, log the updates
        logger.debug("HA entity updates for %s: presence=%s, targets=%d, confidence=%.2f",
                    sensor_id, state.is_present, state.target_count, state.confidence)
    
    def parse_mqtt_payload(
        self,
        topic: str,
        payload: str
    ) -> Optional[List[RadarPoint]]:
        """Parse mmWave radar data from MQTT payload.
        
        Supports common mmWave sensor MQTT formats:
        - Hi-Link LD2410B
        - TI mmWave SDK
        - Custom JSON format
        
        Args:
            topic: MQTT topic
            payload: JSON payload string
            
        Returns:
            List of RadarPoint or None if parsing failed
        """
        import json
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Failed to parse MQTT payload: %s", payload[:100])
            return None
        
        points: List[RadarPoint] = []
        now = time.time()
        
        # Hi-Link LD2410B format
        if "targets" in data:
            for target in data.get("targets", []):
                point = RadarPoint(
                    range_m=float(target.get("distance", 0)),
                    azimuth=float(target.get("angle", 0)),
                    elevation=None,
                    velocity=float(target.get("speed", 0)),
                    snr=float(target.get("snr", 20)),
                    noise=float(target.get("noise", 10)),
                    timestamp=now,
                )
                points.append(point)
        
        # TI mmWave SDK format
        elif "point_cloud" in data:
            for point_data in data.get("point_cloud", []):
                point = RadarPoint(
                    range_m=float(point_data.get("range", 0)),
                    azimuth=float(point_data.get("azimuth", 0)),
                    elevation=float(point_data.get("elevation")),
                    velocity=float(point_data.get("velocity", 0)),
                    snr=float(point_data.get("snr", 20)),
                    noise=float(point_data.get("noise", 10)),
                    timestamp=now,
                )
                points.append(point)
        
        # Generic format
        elif "points" in data:
            for point_data in data.get("points", []):
                point = RadarPoint(
                    range_m=float(point_data.get("range_m", 0)),
                    azimuth=float(point_data.get("azimuth", 0)),
                    elevation=point_data.get("elevation"),
                    velocity=float(point_data.get("velocity", 0)),
                    snr=float(point_data.get("snr", 20)),
                    noise=float(point_data.get("noise", 10)),
                    timestamp=float(point_data.get("timestamp", now)),
                )
                points.append(point)
        
        return points if points else None


# =============================================================================
# Global Engine Instance
# =============================================================================

_mmwave_engine: Optional[MmWaveEngine] = None
_ha_integration: Optional[HomeAssistantIntegration] = None


def get_mmwave_engine() -> MmWaveEngine:
    """Get or create the global mmWave engine instance."""
    global _mmwave_engine
    if _mmwave_engine is None:
        _mmwave_engine = MmWaveEngine()
    return _mmwave_engine


def get_ha_integration() -> HomeAssistantIntegration:
    """Get or create the HA integration instance."""
    global _ha_integration
    if _ha_integration is None:
        _ha_integration = HomeAssistantIntegration(get_mmwave_engine())
    return _ha_integration


def reset_mmwave_engine() -> None:
    """Reset global instances (for testing)."""
    global _mmwave_engine, _ha_integration
    _mmwave_engine = None
    _ha_integration = None
