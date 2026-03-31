"""Zone-Aware Comfort Index — Slice 68.

Optimiert den Comfort Index für Habituszone-Konfigurierbarkeit.

Features:
- Per-Zone Comfort Calculation
- Zone-specific Comfort Factors (temperature, humidity, light, noise)
- Zone Comfort Profiles (baby, elderly, office, sleep, etc.)
- Comfort History per Zone
- Comfort Trend Analysis
- Zone Comfort Alerts
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import uuid
import statistics

logger = logging.getLogger(__name__)


class ComfortLevel(Enum):
    """Comfort level classifications."""
    VERY_UNCOMFORTABLE = "very_uncomfortable"  # 0-20
    UNCOMFORTABLE = "uncomfortable"  # 20-40
    NEUTRAL = "neutral"  # 40-60
    COMFORTABLE = "comfortable"  # 60-80
    VERY_COMFORTABLE = "very_comfortable"  # 80-100


class ComfortFactor(Enum):
    """Comfort factors."""
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    LIGHT = "light"
    NOISE = "noise"
    AIR_QUALITY = "air_quality"
    PRESENCE = "presence"
    CUSTOM = "custom"


@dataclass
class ZoneComfortProfile:
    """Comfort profile for a zone type."""
    profile_id: str
    name: str
    profile_type: str  # "baby", "elderly", "office", "sleep", "living", "custom"
    
    # Temperature preferences (°C)
    temp_min: float = 18.0
    temp_max: float = 26.0
    temp_optimal: float = 22.0
    
    # Humidity preferences (%)
    humidity_min: float = 30.0
    humidity_max: float = 70.0
    humidity_optimal: float = 50.0
    
    # Light preferences (0-1, 0=dark, 1=bright)
    light_min: float = 0.2
    light_max: float = 0.8
    light_optimal: float = 0.5
    
    # Noise preferences (0-1, 0=silent, 1=loud)
    noise_max: float = 0.5
    noise_optimal: float = 0.2
    
    # Factor weights (must sum to 1.0)
    temp_weight: float = 0.35
    humidity_weight: float = 0.25
    light_weight: float = 0.20
    noise_weight: float = 0.15
    air_quality_weight: float = 0.05
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "profile_type": self.profile_type,
            "temperature": {
                "min": self.temp_min,
                "max": self.temp_max,
                "optimal": self.temp_optimal,
            },
            "humidity": {
                "min": self.humidity_min,
                "max": self.humidity_max,
                "optimal": self.humidity_optimal,
            },
            "light": {
                "min": self.light_min,
                "max": self.light_max,
                "optimal": self.light_optimal,
            },
            "noise": {
                "max": self.noise_max,
                "optimal": self.noise_optimal,
            },
            "weights": {
                "temperature": self.temp_weight,
                "humidity": self.humidity_weight,
                "light": self.light_weight,
                "noise": self.noise_weight,
                "air_quality": self.air_quality_weight,
            },
        }


@dataclass
class ZoneComfortState:
    """Current comfort state for a zone."""
    zone_id: str
    comfort_score: float  # 0-100
    comfort_level: ComfortLevel
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    light: Optional[float] = None
    noise: Optional[float] = None
    air_quality: Optional[float] = None
    factor_scores: Dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "comfort_score": self.comfort_score,
            "comfort_level": self.comfort_level.value,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "light": self.light,
            "noise": self.noise,
            "air_quality": self.air_quality,
            "factor_scores": self.factor_scores,
            "timestamp": self.timestamp,
        }


@dataclass
class ComfortHistoryEntry:
    """Historical comfort data point."""
    timestamp: str
    comfort_score: float
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    zone_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "comfort_score": self.comfort_score,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "zone_id": self.zone_id,
        }


@dataclass
class ComfortAlert:
    """Comfort alert for a zone."""
    alert_id: str
    zone_id: str
    alert_type: str  # "too_hot", "too_cold", "too_humid", "too_dry", "too_dark", "too_bright", "too_noisy"
    severity: str  # "low", "medium", "high", "critical"
    current_value: float
    threshold_value: float
    message: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "zone_id": self.zone_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "message": self.message,
            "acknowledged": self.acknowledged,
            "created_at": self.created_at,
        }


class ZoneComfortEngine:
    """Zone-aware comfort index engine.
    
    Architecture:
        HA Sensors → Zone Comfort Factors → Weighted Score → Comfort Level → Alerts
    
    Usage:
        engine = ZoneComfortEngine()
        engine.set_zone_profile(zone_id, profile)
        engine.update_zone_sensors(zone_id, sensor_data)
        comfort = engine.calculate_comfort(zone_id)
    """
    
    def __init__(self):
        self._zone_profiles: Dict[str, ZoneComfortProfile] = {}
        self._zone_sensor_data: Dict[str, Dict[str, Any]] = {}
        self._zone_comfort_history: Dict[str, List[ComfortHistoryEntry]] = {}
        self._zone_alerts: Dict[str, List[ComfortAlert]] = {}
        self._default_profile: Optional[ZoneComfortProfile] = None
        
        # Predefined profiles
        self._init_default_profiles()
        
        logger.info("ZoneComfortEngine initialized")
    
    def _init_default_profiles(self) -> None:
        """Initialize default comfort profiles."""
        # Baby room profile
        baby_profile = ZoneComfortProfile(
            profile_id="profile_baby",
            name="Baby Room",
            profile_type="baby",
            temp_min=20.0,
            temp_max=24.0,
            temp_optimal=22.0,
            humidity_min=40.0,
            humidity_max=60.0,
            humidity_optimal=50.0,
            light_min=0.1,
            light_max=0.5,
            light_optimal=0.3,
            noise_max=0.3,
            noise_optimal=0.1,
            temp_weight=0.40,
            humidity_weight=0.30,
            light_weight=0.15,
            noise_weight=0.10,
            air_quality_weight=0.05,
        )
        
        # Elderly room profile
        elderly_profile = ZoneComfortProfile(
            profile_id="profile_elderly",
            name="Elderly Room",
            profile_type="elderly",
            temp_min=21.0,
            temp_max=26.0,
            temp_optimal=23.5,
            humidity_min=40.0,
            humidity_max=65.0,
            humidity_optimal=52.0,
            light_min=0.3,
            light_max=0.9,
            light_optimal=0.6,
            noise_max=0.4,
            noise_optimal=0.2,
            temp_weight=0.35,
            humidity_weight=0.25,
            light_weight=0.20,
            noise_weight=0.15,
            air_quality_weight=0.05,
        )
        
        # Office profile
        office_profile = ZoneComfortProfile(
            profile_id="profile_office",
            name="Office",
            profile_type="office",
            temp_min=20.0,
            temp_max=25.0,
            temp_optimal=22.5,
            humidity_min=35.0,
            humidity_max=65.0,
            humidity_optimal=50.0,
            light_min=0.4,
            light_max=0.9,
            light_optimal=0.7,
            noise_max=0.5,
            noise_optimal=0.3,
            temp_weight=0.30,
            humidity_weight=0.20,
            light_weight=0.30,
            noise_weight=0.15,
            air_quality_weight=0.05,
        )
        
        # Sleep profile
        sleep_profile = ZoneComfortProfile(
            profile_id="profile_sleep",
            name="Sleep",
            profile_type="sleep",
            temp_min=17.0,
            temp_max=21.0,
            temp_optimal=19.0,
            humidity_min=40.0,
            humidity_max=60.0,
            humidity_optimal=50.0,
            light_min=0.0,
            light_max=0.1,
            light_optimal=0.0,
            noise_max=0.2,
            noise_optimal=0.0,
            temp_weight=0.40,
            humidity_weight=0.20,
            light_weight=0.25,
            noise_weight=0.10,
            air_quality_weight=0.05,
        )
        
        # Living room profile
        living_profile = ZoneComfortProfile(
            profile_id="profile_living",
            name="Living Room",
            profile_type="living",
            temp_min=19.0,
            temp_max=25.0,
            temp_optimal=22.0,
            humidity_min=35.0,
            humidity_max=65.0,
            humidity_optimal=50.0,
            light_min=0.3,
            light_max=0.8,
            light_optimal=0.5,
            noise_max=0.6,
            noise_optimal=0.3,
            temp_weight=0.35,
            humidity_weight=0.25,
            light_weight=0.20,
            noise_weight=0.15,
            air_quality_weight=0.05,
        )
        
        # Store profiles
        self._profiles = {
            "baby": baby_profile,
            "elderly": elderly_profile,
            "office": office_profile,
            "sleep": sleep_profile,
            "living": living_profile,
        }
        
        self._default_profile = living_profile
    
    def set_zone_profile(self, zone_id: str, profile: ZoneComfortProfile) -> bool:
        """Set comfort profile for a zone."""
        self._zone_profiles[zone_id] = profile
        logger.info("Profile set for zone %s: %s", zone_id, profile.name)
        return True
    
    def set_zone_profile_by_type(self, zone_id: str, profile_type: str) -> bool:
        """Set comfort profile for a zone by type."""
        if profile_type not in self._profiles:
            logger.warning("Unknown profile type: %s", profile_type)
            return False
        
        self._zone_profiles[zone_id] = self._profiles[profile_type]
        logger.info("Profile set for zone %s: %s (%s)", zone_id, profile_type, self._profiles[profile_type].name)
        return True
    
    def get_zone_profile(self, zone_id: str) -> Optional[ZoneComfortProfile]:
        """Get comfort profile for a zone."""
        return self._zone_profiles.get(zone_id, self._default_profile)
    
    def update_zone_sensors(self, zone_id: str, sensor_data: Dict[str, Any]) -> None:
        """Update sensor data for a zone."""
        self._zone_sensor_data[zone_id] = {
            **self._zone_sensor_data.get(zone_id, {}),
            **sensor_data,
        }
    
    def calculate_comfort(self, zone_id: str) -> ZoneComfortState:
        """Calculate comfort score for a zone."""
        profile = self.get_zone_profile(zone_id)
        
        if not profile:
            return ZoneComfortState(
                zone_id=zone_id,
                comfort_score=50.0,
                comfort_level=ComfortLevel.NEUTRAL,
            )
        
        sensor_data = self._zone_sensor_data.get(zone_id, {})
        
        # Calculate factor scores
        factor_scores = {}
        
        # Temperature score
        temp = sensor_data.get("temperature")
        if temp is not None:
            factor_scores["temperature"] = self._calculate_temp_score(temp, profile)
        
        # Humidity score
        humidity = sensor_data.get("humidity")
        if humidity is not None:
            factor_scores["humidity"] = self._calculate_humidity_score(humidity, profile)
        
        # Light score
        light = sensor_data.get("light")
        if light is not None:
            factor_scores["light"] = self._calculate_light_score(light, profile)
        
        # Noise score
        noise = sensor_data.get("noise")
        if noise is not None:
            factor_scores["noise"] = self._calculate_noise_score(noise, profile)
        
        # Air quality score
        air_quality = sensor_data.get("air_quality")
        if air_quality is not None:
            factor_scores["air_quality"] = self._calculate_air_quality_score(air_quality)
        
        # Calculate weighted comfort score
        comfort_score = self._calculate_weighted_score(factor_scores, profile)
        
        # Determine comfort level
        comfort_level = self._get_comfort_level(comfort_score)
        
        # Create state
        state = ZoneComfortState(
            zone_id=zone_id,
            comfort_score=comfort_score,
            comfort_level=comfort_level,
            temperature=temp,
            humidity=humidity,
            light=light,
            noise=noise,
            air_quality=air_quality,
            factor_scores=factor_scores,
        )
        
        # Record history
        self._record_history(zone_id, state)
        
        # Check for alerts
        self._check_alerts(zone_id, state, profile)
        
        return state
    
    def _calculate_temp_score(self, temp: float, profile: ZoneComfortProfile) -> float:
        """Calculate temperature comfort score (0-100)."""
        if temp < profile.temp_min:
            # Too cold
            diff = profile.temp_min - temp
            return max(0, 100 - (diff * 10))
        elif temp > profile.temp_max:
            # Too hot
            diff = temp - profile.temp_max
            return max(0, 100 - (diff * 10))
        else:
            # In range - calculate based on distance from optimal
            diff_from_optimal = abs(temp - profile.temp_optimal)
            range_half = (profile.temp_max - profile.temp_min) / 2
            score = 100 - (diff_from_optimal / range_half * 20)
            return max(0, min(100, score))
    
    def _calculate_humidity_score(self, humidity: float, profile: ZoneComfortProfile) -> float:
        """Calculate humidity comfort score (0-100)."""
        if humidity < profile.humidity_min:
            # Too dry
            diff = profile.humidity_min - humidity
            return max(0, 100 - (diff * 2))
        elif humidity > profile.humidity_max:
            # Too humid
            diff = humidity - profile.humidity_max
            return max(0, 100 - (diff * 2))
        else:
            # In range
            diff_from_optimal = abs(humidity - profile.humidity_optimal)
            range_half = (profile.humidity_max - profile.humidity_min) / 2
            score = 100 - (diff_from_optimal / range_half * 20)
            return max(0, min(100, score))
    
    def _calculate_light_score(self, light: float, profile: ZoneComfortProfile) -> float:
        """Calculate light comfort score (0-100)."""
        # Light is 0-1 normalized
        if light < profile.light_min:
            # Too dark
            diff = profile.light_min - light
            return max(0, 100 - (diff * 100))
        elif light > profile.light_max:
            # Too bright
            diff = light - profile.light_max
            return max(0, 100 - (diff * 100))
        else:
            # In range
            diff_from_optimal = abs(light - profile.light_optimal)
            score = 100 - (diff_from_optimal * 50)
            return max(0, min(100, score))
    
    def _calculate_noise_score(self, noise: float, profile: ZoneComfortProfile) -> float:
        """Calculate noise comfort score (0-100)."""
        # Noise is 0-1 normalized (0=silent, 1=loud)
        if noise <= profile.noise_optimal:
            return 100.0
        elif noise >= profile.noise_max:
            return 0.0
        else:
            # Linear interpolation
            ratio = (noise - profile.noise_optimal) / (profile.noise_max - profile.noise_optimal)
            return 100 - (ratio * 100)
    
    def _calculate_air_quality_score(self, air_quality: float) -> float:
        """Calculate air quality comfort score (0-100)."""
        # Air quality is 0-1 normalized (0=bad, 1=good)
        return air_quality * 100
    
    def _calculate_weighted_score(self, factor_scores: Dict[str, float],
                                  profile: ZoneComfortProfile) -> float:
        """Calculate weighted comfort score."""
        if not factor_scores:
            return 50.0  # Neutral default
        
        weights = {
            "temperature": profile.temp_weight,
            "humidity": profile.humidity_weight,
            "light": profile.light_weight,
            "noise": profile.noise_weight,
            "air_quality": profile.air_quality_weight,
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for factor, score in factor_scores.items():
            weight = weights.get(factor, 0.0)
            total_score += score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 50.0
        
        return total_score / total_weight
    
    def _get_comfort_level(self, score: float) -> ComfortLevel:
        """Determine comfort level from score."""
        if score < 20:
            return ComfortLevel.VERY_UNCOMFORTABLE
        elif score < 40:
            return ComfortLevel.UNCOMFORTABLE
        elif score < 60:
            return ComfortLevel.NEUTRAL
        elif score < 80:
            return ComfortLevel.COMFORTABLE
        else:
            return ComfortLevel.VERY_COMFORTABLE
    
    def _record_history(self, zone_id: str, state: ZoneComfortState) -> None:
        """Record comfort state to history."""
        if zone_id not in self._zone_comfort_history:
            self._zone_comfort_history[zone_id] = []
        
        entry = ComfortHistoryEntry(
            timestamp=state.timestamp,
            comfort_score=state.comfort_score,
            temperature=state.temperature,
            humidity=state.humidity,
            zone_id=zone_id,
        )
        
        self._zone_comfort_history[zone_id].append(entry)
        
        # Limit history size (last 1000 entries per zone)
        if len(self._zone_comfort_history[zone_id]) > 1000:
            self._zone_comfort_history[zone_id] = self._zone_comfort_history[zone_id][-1000:]
    
    def _check_alerts(self, zone_id: str, state: ZoneComfortState,
                     profile: ZoneComfortProfile) -> None:
        """Check for comfort alerts."""
        alerts = []
        now = datetime.now(timezone.utc).isoformat()
        
        # Temperature alerts
        if state.temperature is not None:
            if state.temperature > profile.temp_max:
                severity = "critical" if state.temperature > profile.temp_max + 3 else "high"
                alerts.append(ComfortAlert(
                    alert_id=f"alert_{uuid.uuid4().hex[:16]}",
                    zone_id=zone_id,
                    alert_type="too_hot",
                    severity=severity,
                    current_value=state.temperature,
                    threshold_value=profile.temp_max,
                    message=f"Temperature too high: {state.temperature:.1f}°C (max: {profile.temp_max:.1f}°C)",
                ))
            elif state.temperature < profile.temp_min:
                severity = "critical" if state.temperature < profile.temp_min - 3 else "high"
                alerts.append(ComfortAlert(
                    alert_id=f"alert_{uuid.uuid4().hex[:16]}",
                    zone_id=zone_id,
                    alert_type="too_cold",
                    severity=severity,
                    current_value=state.temperature,
                    threshold_value=profile.temp_min,
                    message=f"Temperature too low: {state.temperature:.1f}°C (min: {profile.temp_min:.1f}°C)",
                ))
        
        # Humidity alerts
        if state.humidity is not None:
            if state.humidity > profile.humidity_max:
                alerts.append(ComfortAlert(
                    alert_id=f"alert_{uuid.uuid4().hex[:16]}",
                    zone_id=zone_id,
                    alert_type="too_humid",
                    severity="medium",
                    current_value=state.humidity,
                    threshold_value=profile.humidity_max,
                    message=f"Humidity too high: {state.humidity:.1f}% (max: {profile.humidity_max:.1f}%)",
                ))
            elif state.humidity < profile.humidity_min:
                alerts.append(ComfortAlert(
                    alert_id=f"alert_{uuid.uuid4().hex[:16]}",
                    zone_id=zone_id,
                    alert_type="too_dry",
                    severity="medium",
                    current_value=state.humidity,
                    threshold_value=profile.humidity_min,
                    message=f"Humidity too low: {state.humidity:.1f}% (min: {profile.humidity_min:.1f}%)",
                ))
        
        # Light alerts
        if state.light is not None:
            if state.light > profile.light_max:
                alerts.append(ComfortAlert(
                    alert_id=f"alert_{uuid.uuid4().hex[:16]}",
                    zone_id=zone_id,
                    alert_type="too_bright",
                    severity="low",
                    current_value=state.light,
                    threshold_value=profile.light_max,
                    message=f"Light too bright: {state.light*100:.0f}% (max: {profile.light_max*100:.0f}%)",
                ))
            elif state.light < profile.light_min:
                alerts.append(ComfortAlert(
                    alert_id=f"alert_{uuid.uuid4().hex[:16]}",
                    zone_id=zone_id,
                    alert_type="too_dark",
                    severity="low",
                    current_value=state.light,
                    threshold_value=profile.light_min,
                    message=f"Light too dark: {state.light*100:.0f}% (min: {profile.light_min*100:.0f}%)",
                ))
        
        # Noise alerts
        if state.noise is not None and state.noise > profile.noise_max:
            alerts.append(ComfortAlert(
                alert_id=f"alert_{uuid.uuid4().hex[:16]}",
                zone_id=zone_id,
                alert_type="too_noisy",
                severity="medium",
                current_value=state.noise,
                threshold_value=profile.noise_max,
                message=f"Noise too high: {state.noise*100:.0f}% (max: {profile.noise_max*100:.0f}%)",
            ))
        
        # Store alerts
        if zone_id not in self._zone_alerts:
            self._zone_alerts[zone_id] = []
        
        self._zone_alerts[zone_id].extend(alerts)
        
        # Limit alerts (last 100 per zone)
        if len(self._zone_alerts[zone_id]) > 100:
            self._zone_alerts[zone_id] = self._zone_alerts[zone_id][-100:]
    
    def get_comfort_history(self, zone_id: str,
                           hours: int = 24,
                           limit: int = 100) -> List[ComfortHistoryEntry]:
        """Get comfort history for a zone."""
        if zone_id not in self._zone_comfort_history:
            return []
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        history = self._zone_comfort_history[zone_id]
        
        # Filter by time
        filtered = [
            entry for entry in history
            if datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00')) > cutoff
        ]
        
        # Return most recent
        return filtered[-limit:]
    
    def get_comfort_trend(self, zone_id: str,
                         hours: int = 24) -> Dict[str, Any]:
        """Calculate comfort trend for a zone."""
        history = self.get_comfort_history(zone_id, hours)
        
        if len(history) < 2:
            return {
                "trend": "stable",
                "change": 0.0,
                "average": 50.0,
                "min": 50.0,
                "max": 50.0,
            }
        
        scores = [entry.comfort_score for entry in history]
        
        # Calculate trend (compare first half to second half)
        mid = len(scores) // 2
        first_half_avg = statistics.mean(scores[:mid]) if mid > 0 else scores[0]
        second_half_avg = statistics.mean(scores[mid:]) if mid > 0 else scores[-1]
        
        change = second_half_avg - first_half_avg
        
        if change > 5:
            trend = "improving"
        elif change < -5:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "change": round(change, 2),
            "average": round(statistics.mean(scores), 2),
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "data_points": len(scores),
        }
    
    def get_alerts(self, zone_id: str,
                  unacknowledged_only: bool = True) -> List[ComfortAlert]:
        """Get alerts for a zone."""
        if zone_id not in self._zone_alerts:
            return []
        
        alerts = self._zone_alerts[zone_id]
        
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        
        return alerts
    
    def acknowledge_alert(self, zone_id: str, alert_id: str) -> bool:
        """Acknowledge an alert."""
        if zone_id not in self._zone_alerts:
            return False
        
        for alert in self._zone_alerts[zone_id]:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        
        return False
    
    def clear_alerts(self, zone_id: str) -> int:
        """Clear all alerts for a zone."""
        if zone_id not in self._zone_alerts:
            return 0
        
        count = len(self._zone_alerts[zone_id])
        self._zone_alerts[zone_id] = []
        return count
    
    def get_zone_state(self, zone_id: str) -> Optional[ZoneComfortState]:
        """Get current comfort state for a zone."""
        if zone_id not in self._zone_sensor_data:
            return None
        
        return self.calculate_comfort(zone_id)
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """List available comfort profiles."""
        return [p.to_dict() for p in self._profiles.values()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comfort engine statistics."""
        total_zones = len(self._zone_profiles)
        total_alerts = sum(len(a) for a in self._zone_alerts.values())
        unack_alerts = sum(
            len([a for a in alerts if not a.acknowledged])
            for alerts in self._zone_alerts.values()
        )
        
        return {
            "total_zones": total_zones,
            "total_profiles": len(self._profiles),
            "total_alerts": total_alerts,
            "unacknowledged_alerts": unack_alerts,
            "total_history_entries": sum(len(h) for h in self._zone_comfort_history.values()),
        }


def create_zone_comfort_engine() -> ZoneComfortEngine:
    """Factory function to create zone comfort engine."""
    return ZoneComfortEngine()
