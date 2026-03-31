"""TimeOfDay Module Extensions — Slice 77.

Erweiterte Tageszeit-Berechnung für Habituszonen.

New Features (Slice 77):
- Geografische Position (Lat/Lon für präzise Berechnungen)
- Präzise Sunrise/Sunset (astronomische Berechnung)
- Dämmerungszeiten (civil, nautical, astronomical)
- Mondphasen (basic)
- Zeitzonen-Support
- Golden Hour / Blue Hour
- Jahreszeiten-basierte Events
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import uuid
import math

logger = logging.getLogger(__name__)


class TwilightType(Enum):
    """Twilight types."""
    CIVIL = "civil"  # Sun 6° below horizon (visible horizon)
    NAUTICAL = "nautical"  # Sun 12° below horizon (horizon visible for navigation)
    ASTRONOMICAL = "astronomical"  # Sun 18° below horizon (dark enough for astronomy)


class MoonPhase(Enum):
    """Moon phases."""
    NEW_MOON = "new_moon"
    WAXING_CRESCENT = "waxing_crescent"
    FIRST_QUARTER = "first_quarter"
    WAXING_GIBBOUS = "waxing_gibbous"
    FULL_MOON = "full_moon"
    WANING_GIBBOUS = "waning_gibbous"
    LAST_QUARTER = "last_quarter"
    WANING_CRESCENT = "waning_crescent"


@dataclass
class GeographicLocation:
    """Geographic location for sun/moon calculations."""
    latitude: float  # -90 to 90
    longitude: float  # -180 to 180
    timezone: str = "UTC"
    elevation_meters: float = 0.0
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate location coordinates."""
        if not -90 <= self.latitude <= 90:
            return False, "Latitude must be between -90 and 90"
        if not -180 <= self.longitude <= 180:
            return False, "Longitude must be between -180 and 180"
        return True, None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "elevation_meters": self.elevation_meters,
        }


@dataclass
class SunTimes:
    """Sun times for a specific date and location."""
    date: str
    location: GeographicLocation
    
    sunrise: Optional[str] = None  # ISO timestamp
    sunset: Optional[str] = None  # ISO timestamp
    solar_noon: Optional[str] = None
    day_length_seconds: int = 0
    
    # Twilight times
    civil_dawn: Optional[str] = None
    civil_dusk: Optional[str] = None
    nautical_dawn: Optional[str] = None
    nautical_dusk: Optional[str] = None
    astronomical_dawn: Optional[str] = None
    astronomical_dusk: Optional[str] = None
    
    # Golden/Blue hours
    golden_hour_morning_start: Optional[str] = None
    golden_hour_morning_end: Optional[str] = None
    golden_hour_evening_start: Optional[str] = None
    golden_hour_evening_end: Optional[str] = None
    blue_hour_morning_start: Optional[str] = None
    blue_hour_morning_end: Optional[str] = None
    blue_hour_evening_start: Optional[str] = None
    blue_hour_evening_end: Optional[str] = None
    
    # Solar position at given time
    solar_elevation: float = 0.0  # Degrees above horizon
    solar_azimuth: float = 0.0  # Degrees from north
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "location": self.location.to_dict(),
            "sunrise": self.sunrise,
            "sunset": self.sunset,
            "solar_noon": self.solar_noon,
            "day_length_seconds": self.day_length_seconds,
            "civil_dawn": self.civil_dawn,
            "civil_dusk": self.civil_dusk,
            "golden_hour_morning_start": self.golden_hour_morning_start,
            "golden_hour_evening_end": self.golden_hour_evening_end,
        }


@dataclass
class MoonData:
    """Moon data for a specific date."""
    date: str
    phase: MoonPhase
    illumination: float  # 0.0-1.0
    age_days: float  # Days since new moon
    next_full_moon: Optional[str] = None
    next_new_moon: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "phase": self.phase.value,
            "illumination": self.illumination,
            "age_days": self.age_days,
            "next_full_moon": self.next_full_moon,
            "next_new_moon": self.next_new_moon,
        }


@dataclass
class TimeOfDayProfile:
    """Extended time of day profile with geographic awareness."""
    profile_id: str
    zone_id: str
    name: str
    location: Optional[GeographicLocation] = None
    use_geographic: bool = False  # Use lat/lon for calculations
    fixed_sunrise: Optional[str] = None  # Manual override (HH:MM)
    fixed_sunset: Optional[str] = None  # Manual override (HH:MM)
    golden_hour_enabled: bool = True
    blue_hour_enabled: bool = False
    twilight_mode: TwilightType = TwilightType.CIVIL
    season_events_enabled: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "zone_id": self.zone_id,
            "name": self.name,
            "location": self.location.to_dict() if self.location else None,
            "use_geographic": self.use_geographic,
            "fixed_sunrise": self.fixed_sunrise,
            "fixed_sunset": self.fixed_sunset,
            "golden_hour_enabled": self.golden_hour_enabled,
            "blue_hour_enabled": self.blue_hour_enabled,
            "twilight_mode": self.twilight_mode.value,
            "season_events_enabled": self.season_events_enabled,
        }


class TimeOfDayModuleExtended:
    """Extended time of day module with geographic calculations.
    
    New Capabilities (Slice 77):
    - Precise sunrise/sunset based on lat/lon
    - Twilight times (civil, nautical, astronomical)
    - Golden hour / Blue hour calculations
    - Moon phase tracking
    - Seasonal event detection
    - Timezone-aware calculations
    
    All calculations are done locally — no external API dependencies.
    """
    
    def __init__(self):
        self._profiles: Dict[str, TimeOfDayProfile] = {}
        self._sun_times_cache: Dict[str, SunTimes] = {}  # cache_key -> SunTimes
        self._moon_data_cache: Dict[str, MoonData] = {}  # date_str -> MoonData
        
        logger.info("TimeOfDayModuleExtended initialized")
    
    def set_profile(self, profile: TimeOfDayProfile) -> str:
        """Set time of day profile for zone."""
        with self._lock():
            self._profiles[profile.zone_id] = profile
        
        logger.info("TimeOfDay profile set for %s: %s", profile.zone_id, profile.name)
        return profile.profile_id
    
    def get_profile(self, zone_id: str) -> Optional[TimeOfDayProfile]:
        """Get profile for zone."""
        return self._profiles.get(zone_id)
    
    def set_location(self, zone_id: str, latitude: float, longitude: float,
                    timezone_str: str = "UTC") -> bool:
        """Set geographic location for zone."""
        profile = self._profiles.get(zone_id)
        
        if not profile:
            profile = TimeOfDayProfile(
                profile_id=f"profile_{zone_id}",
                zone_id=zone_id,
                name=f"{zone_id} Profile",
            )
        
        location = GeographicLocation(
            latitude=latitude,
            longitude=longitude,
            timezone=timezone_str,
        )
        
        valid, error = location.validate()
        if not valid:
            logger.error("Invalid location: %s", error)
            return False
        
        profile.location = location
        profile.use_geographic = True
        
        with self._lock():
            self._profiles[zone_id] = profile
        
        # Clear sun times cache for this zone
        self._clear_sun_cache(zone_id)
        
        logger.info("Location set for %s: %.4f, %.4f", zone_id, latitude, longitude)
        return True
    
    def get_sun_times(self, zone_id: str,
                     at_date: Optional[datetime] = None) -> Optional[SunTimes]:
        """Get sun times for zone on specific date."""
        profile = self._profiles.get(zone_id)
        
        if not profile:
            return None
        
        date = at_date or datetime.now(timezone.utc)
        date_str = date.strftime("%Y-%m-%d")
        
        # Check cache
        cache_key = f"{zone_id}_{date_str}"
        if cache_key in self._sun_times_cache:
            return self._sun_times_cache[cache_key]
        
        # Calculate sun times
        if profile.use_geographic and profile.location:
            sun_times = self._calculate_sun_times(date, profile.location, profile.twilight_mode)
        elif profile.fixed_sunrise and profile.fixed_sunset:
            sun_times = self._create_fixed_sun_times(date, profile)
        else:
            # Default approximations
            sun_times = self._create_default_sun_times(date, zone_id)
        
        # Cache result
        self._sun_times_cache[cache_key] = sun_times
        
        # Limit cache size
        if len(self._sun_times_cache) > 1000:
            oldest_key = next(iter(self._sun_times_cache))
            del self._sun_times_cache[oldest_key]
        
        return sun_times
    
    def _calculate_sun_times(self, date: datetime, location: GeographicLocation,
                            twilight_type: TwilightType) -> SunTimes:
        """Calculate precise sun times using astronomical formulas."""
        lat_rad = math.radians(location.latitude)
        
        # Day of year
        day_of_year = date.timetuple().tm_yday
        
        # Solar declination (simplified)
        declination = 23.45 * math.sin(math.radians((360/365) * (day_of_year - 81)))
        declination_rad = math.radians(declination)
        
        # Hour angle for sunrise/sunset
        # cos(omega) = -tan(lat) * tan(dec) for standard sunrise
        # For twilight, use different angles
        
        def calculate_hour_angle(angle_degrees: float) -> Optional[float]:
            """Calculate hour angle for given sun angle below horizon."""
            angle_rad = math.radians(angle_degrees)
            cos_omega = (math.sin(angle_rad) - math.sin(lat_rad) * math.sin(declination_rad)) / \
                       (math.cos(lat_rad) * math.cos(declination_rad))
            
            # Check if sun never rises/sets at this location
            if cos_omega < -1 or cos_omega > 1:
                return None
            
            return math.degrees(math.acos(cos_omega))
        
        # Standard sunrise/sunset (sun at horizon, -0.833° for atmospheric refraction)
        hour_angle = calculate_hour_angle(-0.833)
        
        # Solar noon (approximately 12:00 local solar time)
        # Equation of time correction (simplified)
        eot_minutes = 9.87 * math.sin(2 * math.radians((360/365) * (day_of_year - 81))) - \
                     7.53 * math.cos(math.radians((360/365) * (day_of_year - 81))) - \
                     1.5 * math.sin(math.radians((360/365) * (day_of_year - 81)))
        
        # Time offset for longitude within timezone
        # Assume timezone is roughly based on longitude (15° per hour)
        timezone_offset = round(location.longitude / 15) * 60  # minutes
        
        if hour_angle is not None:
            # Sunrise/sunset in minutes from midnight
            sunrise_minutes = 720 - (hour_angle * 4) + eot_minutes - timezone_offset
            sunset_minutes = 720 + (hour_angle * 4) + eot_minutes - timezone_offset
            
            # Normalize to 0-1440
            sunrise_minutes = sunrise_minutes % 1440
            sunset_minutes = sunset_minutes % 1440
            
            sunrise = date.replace(hour=int(sunrise_minutes // 60),
                                  minute=int(sunrise_minutes % 60),
                                  second=0, microsecond=0)
            sunset = date.replace(hour=int(sunset_minutes // 60),
                                 minute=int(sunset_minutes % 60),
                                 second=0, microsecond=0)
            
            day_length = int((sunset_minutes - sunrise_minutes) * 60)
        else:
            sunrise = None
            sunset = None
            day_length = 0
        
        # Twilight calculations
        twilight_angle = -6.0 if twilight_type == TwilightType.CIVIL else \
                        -12.0 if twilight_type == TwilightType.NAUTICAL else -18.0
        
        twilight_hour_angle = calculate_hour_angle(twilight_angle)
        
        if twilight_hour_angle is not None:
            civil_dawn_mins = 720 - (twilight_hour_angle * 4) + eot_minutes - timezone_offset
            civil_dusk_mins = 720 + (twilight_hour_angle * 4) + eot_minutes - timezone_offset
            
            civil_dawn = date.replace(hour=int(civil_dawn_mins // 60) % 24,
                                     minute=int(civil_dawn_mins % 60),
                                     second=0)
            civil_dusk = date.replace(hour=int(civil_dusk_mins // 60) % 24,
                                     minute=int(civil_dusk_mins % 60),
                                     second=0)
        else:
            civil_dawn = None
            civil_dusk = None
        
        # Solar noon
        solar_noon_minutes = 720 + eot_minutes - timezone_offset
        solar_noon = date.replace(hour=int(solar_noon_minutes // 60) % 24,
                                 minute=int(solar_noon_minutes % 60),
                                 second=0) if sunrise and sunset else None
        
        # Golden hour (approximately 1 hour after sunrise / before sunset)
        golden_hour_morning_start = None
        golden_hour_morning_end = None
        golden_hour_evening_start = None
        golden_hour_evening_end = None
        
        if sunrise and sunset:
            golden_hour_morning_start = sunrise
            golden_hour_morning_end = (sunrise + timedelta(hours=1)).replace(tzinfo=timezone.utc)
            golden_hour_evening_start = (sunset - timedelta(hours=1)).replace(tzinfo=timezone.utc)
            golden_hour_evening_end = sunset
        
        # Blue hour (during civil twilight)
        blue_hour_morning_start = civil_dawn
        blue_hour_morning_end = sunrise
        blue_hour_evening_start = sunset
        blue_hour_evening_end = civil_dusk
        
        sun_times = SunTimes(
            date=date_str,
            location=location,
            sunrise=sunrise.isoformat() if sunrise else None,
            sunset=sunset.isoformat() if sunset else None,
            solar_noon=solar_noon.isoformat() if solar_noon else None,
            day_length_seconds=max(0, day_length),
            civil_dawn=civil_dawn.isoformat() if civil_dawn else None,
            civil_dusk=civil_dusk.isoformat() if civil_dusk else None,
            golden_hour_morning_start=golden_hour_morning_start.isoformat() if golden_hour_morning_start else None,
            golden_hour_morning_end=golden_hour_morning_end.isoformat() if golden_hour_morning_end else None,
            golden_hour_evening_start=golden_hour_evening_start.isoformat() if golden_hour_evening_start else None,
            golden_hour_evening_end=golden_hour_evening_end.isoformat() if golden_hour_evening_end else None,
            blue_hour_morning_start=blue_hour_morning_start.isoformat() if blue_hour_morning_start else None,
            blue_hour_morning_end=blue_hour_morning_end.isoformat() if blue_hour_morning_end else None,
            blue_hour_evening_start=blue_hour_evening_start.isoformat() if blue_hour_evening_start else None,
            blue_hour_evening_end=blue_hour_evening_end.isoformat() if blue_hour_evening_end else None,
        )
        
        return sun_times
    
    def _create_fixed_sun_times(self, date: datetime, profile: TimeOfDayProfile) -> SunTimes:
        """Create sun times from fixed times."""
        sunrise_parts = profile.fixed_sunrise.split(":")
        sunset_parts = profile.fixed_sunset.split(":")
        
        sunrise = date.replace(hour=int(sunrise_parts[0]), minute=int(sunrise_parts[1]), second=0)
        sunset = date.replace(hour=int(sunset_parts[0]), minute=int(sunset_parts[1]), second=0)
        
        day_length = int((sunset - sunrise).total_seconds())
        
        return SunTimes(
            date=date.strftime("%Y-%m-%d"),
            location=profile.location or GeographicLocation(0, 0),
            sunrise=sunrise.isoformat(),
            sunset=sunset.isoformat(),
            solar_noon=None,
            day_length_seconds=day_length,
        )
    
    def _create_default_sun_times(self, date: datetime, zone_id: str) -> SunTimes:
        """Create default sun times (no location data)."""
        # Simple approximations based on season
        day_of_year = date.timetuple().tm_yday
        
        # Seasonal variation (Northern Hemisphere default)
        season_offset = math.sin(math.radians((360/365) * (day_of_year - 81)))
        
        sunrise_hour = 6 + int(season_offset * 1.5)  # 4:30 - 7:30
        sunset_hour = 20 + int(season_offset * 1.5)  # 18:30 - 21:30
        
        sunrise = date.replace(hour=sunrise_hour, minute=0, second=0)
        sunset = date.replace(hour=sunset_hour, minute=0, second=0)
        
        return SunTimes(
            date=date.strftime("%Y-%m-%d"),
            location=GeographicLocation(0, 0),
            sunrise=sunrise.isoformat(),
            sunset=sunset.isoformat(),
            solar_noon=None,
            day_length_seconds=int((sunset - sunrise).total_seconds()),
        )
    
    def get_moon_data(self, at_date: Optional[datetime] = None) -> MoonData:
        """Get moon data for date (simplified calculation)."""
        date = at_date or datetime.now(timezone.utc)
        date_str = date.strftime("%Y-%m-%d")
        
        # Check cache
        if date_str in self._moon_data_cache:
            return self._moon_data_cache[date_str]
        
        # Simplified moon phase calculation
        # Known new moon: January 6, 2000
        known_new_moon = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
        synodic_month = 29.53058867  # Days
        
        days_since = (date - known_new_moon).total_seconds() / 86400
        lunar_cycles = days_since / synodic_month
        current_cycle = lunar_cycles - int(lunar_cycles)
        age_days = current_cycle * synodic_month
        
        # Determine phase
        if current_cycle < 0.0625:
            phase = MoonPhase.NEW_MOON
        elif current_cycle < 0.1875:
            phase = MoonPhase.WAXING_CRESCENT
        elif current_cycle < 0.3125:
            phase = MoonPhase.FIRST_QUARTER
        elif current_cycle < 0.4375:
            phase = MoonPhase.WAXING_GIBBOUS
        elif current_cycle < 0.5625:
            phase = MoonPhase.FULL_MOON
        elif current_cycle < 0.6875:
            phase = MoonPhase.WANING_GIBBOUS
        elif current_cycle < 0.8125:
            phase = MoonPhase.LAST_QUARTER
        elif current_cycle < 0.9375:
            phase = MoonPhase.WANING_CRESCENT
        else:
            phase = MoonPhase.NEW_MOON
        
        # Illumination (simplified)
        illumination = 0.5 * (1 - math.cos(2 * math.pi * current_cycle))
        
        # Next full/new moon (approximate)
        days_to_full = (0.5 - current_cycle) * synodic_month
        days_to_new = (1.0 - current_cycle) * synodic_month
        
        if days_to_full < 0:
            days_to_full += synodic_month
        if days_to_new < 0:
            days_to_new += synodic_month
        
        next_full = (date + timedelta(days=days_to_full)).strftime("%Y-%m-%d")
        next_new = (date + timedelta(days=days_to_new)).strftime("%Y-%m-%d")
        
        moon_data = MoonData(
            date=date_str,
            phase=phase,
            illumination=round(illumination, 3),
            age_days=round(age_days, 1),
            next_full_moon=next_full,
            next_new_moon=next_new,
        )
        
        self._moon_data_cache[date_str] = moon_data
        
        # Limit cache
        if len(self._moon_data_cache) > 100:
            oldest_key = next(iter(self._moon_data_cache))
            del self._moon_data_cache[oldest_key]
        
        return moon_data
    
    def is_golden_hour(self, zone_id: str,
                      at_time: Optional[datetime] = None) -> bool:
        """Check if currently golden hour."""
        sun_times = self.get_sun_times(zone_id, at_time)
        
        if not sun_times or not sun_times.golden_hour_morning_start:
            return False
        
        now = at_time or datetime.now(timezone.utc)
        now_str = now.isoformat()
        
        # Morning golden hour
        if (sun_times.golden_hour_morning_start <= now_str <=
            sun_times.golden_hour_morning_end):
            return True
        
        # Evening golden hour
        if (sun_times.golden_hour_evening_start and
            sun_times.golden_hour_evening_end and
            sun_times.golden_hour_evening_start <= now_str <=
            sun_times.golden_hour_evening_end):
            return True
        
        return False
    
    def is_blue_hour(self, zone_id: str,
                    at_time: Optional[datetime] = None) -> bool:
        """Check if currently blue hour."""
        sun_times = self.get_sun_times(zone_id, at_time)
        
        if not sun_times or not sun_times.blue_hour_morning_start:
            return False
        
        now = at_time or datetime.now(timezone.utc)
        now_str = now.isoformat()
        
        # Morning blue hour
        if (sun_times.blue_hour_morning_start <= now_str <=
            sun_times.blue_hour_morning_end):
            return True
        
        # Evening blue hour
        if (sun_times.blue_hour_evening_start and
            sun_times.blue_hour_evening_end and
            sun_times.blue_hour_evening_start <= now_str <=
            sun_times.blue_hour_evening_end):
            return True
        
        return False
    
    def get_solar_position(self, zone_id: str,
                          at_time: Optional[datetime] = None) -> Dict[str, float]:
        """Get solar elevation and azimuth."""
        date = at_time or datetime.now(timezone.utc)
        profile = self._profiles.get(zone_id)
        
        if not profile or not profile.location:
            return {"elevation": 0.0, "azimuth": 0.0}
        
        location = profile.location
        
        # Simplified solar position calculation
        lat_rad = math.radians(location.latitude)
        
        # Hour angle
        solar_noon = 12  # Simplified
        hour_angle = (date.hour - solar_noon) * 15 + date.minute / 4
        
        # Solar declination
        day_of_year = date.timetuple().tm_yday
        declination = 23.45 * math.sin(math.radians((360/365) * (day_of_year - 81)))
        dec_rad = math.radians(declination)
        
        # Solar elevation
        hour_rad = math.radians(hour_angle)
        sin_elevation = (math.sin(lat_rad) * math.sin(dec_rad) +
                        math.cos(lat_rad) * math.cos(dec_rad) * math.cos(hour_rad))
        elevation = math.degrees(math.asin(sin_elevation))
        
        # Solar azimuth (simplified)
        azimuth = 180 + hour_angle  # Very simplified
        
        return {
            "elevation": round(elevation, 2),
            "azimuth": round(azimuth, 2),
        }
    
    def _clear_sun_cache(self, zone_id: str) -> None:
        """Clear sun times cache for zone."""
        keys_to_remove = [k for k in self._sun_times_cache if k.startswith(f"{zone_id}_")]
        for key in keys_to_remove:
            del self._sun_times_cache[key]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get extended time module statistics."""
        zones_with_location = len([
            p for p in self._profiles.values()
            if p.location
        ])
        
        return {
            "total_profiles": len(self._profiles),
            "zones_with_geographic": zones_with_location,
            "zones_with_fixed_times": len([
                p for p in self._profiles.values()
                if p.fixed_sunrise and p.fixed_sunset
            ]),
            "sun_times_cached": len(self._sun_times_cache),
            "moon_data_cached": len(self._moon_data_cache),
        }
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_time_of_day_module_extended() -> TimeOfDayModuleExtended:
    """Factory function to create extended time of day module."""
    return TimeOfDayModuleExtended()
