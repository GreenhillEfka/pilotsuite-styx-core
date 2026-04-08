"""PV-Ertragsprognose — Wetter-basierte Solarvorhersage (v12.6.0).

Berechnet PV-Ertrag basierend auf:
- Sonnenstand (geographische Position, Tageszeit)
- Wetterdaten (DWD/OpenWeatherMap)
- Bewölkung, Niederschlag, Aerosole
- PV-Anlagen-Konfiguration
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PVHourlyForecast:
    """Stündliche PV-Prognose."""
    
    timestamp: str  # ISO 8601
    hour: int
    solar_elevation: float  # Grad über Horizont
    solar_azimuth: float  # Grad (0=North, 180=South)
    clearsky_irradiance_wm2: float  # Theoretische Einstrahlung
    actual_irradiance_wm2: float  # Tatsächliche Einstrahlung (mit Wetter)
    pv_power_kw: float  # Erwartete PV-Leistung
    pv_energy_wh: float  # Erwartete Energie pro Stunde
    cloud_cover_pct: int  # Bewölkung
    weather_condition: str  # clear/cloudy/rainy/overcast
    efficiency_factor: float  # 0-1 Gesamtwirkungsgrad


@dataclass
class PVDailyForecast:
    """Tägliche PV-Zusammenfassung."""
    
    date: str
    total_energy_kwh: float
    peak_power_kw: float
    peak_time: str
    sunrise: str
    sunset: str
    solar_noon: str
    daylight_hours: float
    avg_cloud_cover_pct: int
    weather_quality: str  # excellent/good/fair/poor


@dataclass
class PVForecastSummary:
    """Zusammenfassung der PV-Prognose."""
    
    forecast_horizon_hours: int
    total_energy_kwh: float
    avg_daily_energy_kwh: float
    peak_power_kw: float
    peak_time: str
    best_production_day: str
    worst_production_day: str
    total_sunlight_hours: float
    weather_impact_pct: float  # Wie stark Wetter reduziert


class PVPredictionEngine:
    """Engine für PV-Ertragsprognosen.
    
    Kombiniert astronomische Berechnungen mit Wetterdaten
    für präzise Vorhersagen des Solarertrags.
    """
    
    def __init__(
        self,
        latitude: float = 51.0,
        longitude: float = 10.0,
        pv_peak_kw: float = 10.0,
        panel_azimuth: float = 180.0,  # Süd
        panel_tilt: float = 30.0,  # Grad
        system_efficiency: float = 0.85,  # 85% Systemwirkungsgrad
    ):
        self._lat = latitude
        self._lon = longitude
        self._pv_peak = pv_peak_kw
        self._panel_azimuth = panel_azimuth
        self._panel_tilt = panel_tilt
        self._system_efficiency = system_efficiency
        
        # Wetterdaten (werden von extern gesetzt)
        self._weather_data: dict[int, dict] = {}
        
    def update_location(self, lat: float, lon: float) -> None:
        """Update Standort."""
        self._lat = lat
        self._lon = lon
    
    def set_pv_system(self, peak_kw: float, azimuth: float = 180.0, tilt: float = 30.0) -> None:
        """Konfiguriere PV-Anlage."""
        self._pv_peak = peak_kw
        self._panel_azimuth = azimuth
        self._panel_tilt = tilt
    
    def set_system_efficiency(self, efficiency: float) -> None:
        """Setze Systemwirkungsgrad (0-1)."""
        self._system_efficiency = max(0.5, min(0.95, efficiency))
    
    def set_weather_data(self, weather_data: list[dict]) -> None:
        """Setze Wetterdaten für Prognose.
        
        weather_data: Liste von dicts mit:
        - timestamp: ISO 8601
        - temperature_c: float
        - cloud_cover_pct: int (0-100)
        - precipitation_mm: float
        - weather_code: int (WMO codes)
        - irradiance_wm2: float (optional, sonst berechnet)
        """
        self._weather_data = {}
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        for i, data in enumerate(weather_data):
            self._weather_data[i] = {
                "timestamp": data.get("timestamp", (now + timedelta(hours=i)).isoformat()),
                "temperature_c": data.get("temperature_c", 15.0),
                "cloud_cover_pct": data.get("cloud_cover_pct", 50),
                "precipitation_mm": data.get("precipitation_mm", 0.0),
                "weather_code": data.get("weather_code", 0),
                "irradiance_wm2": data.get("irradiance_wm2"),
                "wind_speed_ms": data.get("wind_speed_ms", 3.0),
            }
    
    def _solar_position(self, dt: datetime) -> tuple[float, float]:
        """Berechne Sonnenposition (Elevation, Azimuth)."""
        # Algorithmus basierend auf NOAA Solar Calculator
        
        # Tag des Jahres
        doy = dt.timetuple().tm_yday
        
        # Fractional year (radians)
        gamma = 2 * math.pi / 365 * (doy - 1)
        
        # Equation of time (minutes)
        eqtime = (
            229.18 * (
                0.000075
                + 0.001868 * math.cos(gamma)
                - 0.032077 * math.sin(gamma)
                - 0.014615 * math.cos(2 * gamma)
                - 0.040849 * math.sin(2 * gamma)
            )
        )
        
        # Declination (radians)
        decl = (
            0.006918
            - 0.399912 * math.cos(gamma)
            + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma)
            + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma)
            + 0.00148 * math.sin(3 * gamma)
        )
        
        # Time offset (minutes)
        tz_offset = 2.0 if 3 <= dt.month <= 10 else 1.0  # MEZ/MESZ
        time_offset = eqtime + 4 * self._lon - 60 * tz_offset
        
        # Hour angle
        tsol = dt.hour * 60 + dt.minute + time_offset
        ha = math.radians(tsol / 4 - 180)
        
        # Latitude (radians)
        lat_rad = math.radians(self._lat)
        
        # Solar elevation
        sin_elev = (
            math.sin(lat_rad) * math.sin(decl)
            + math.cos(lat_rad) * math.cos(decl) * math.cos(ha)
        )
        elevation = math.degrees(math.asin(max(-1, min(1, sin_elev))))
        
        # Solar azimuth
        cos_az = (
            (math.sin(decl) * math.cos(lat_rad) - math.cos(decl) * math.sin(lat_rad) * math.cos(ha))
            / math.cos(math.radians(elevation))
        )
        cos_az = max(-1, min(1, cos_az))
        azimuth = math.degrees(math.acos(cos_az))
        
        if math.sin(ha) > 0:
            azimuth = 360 - azimuth
        
        return round(elevation, 2), round(azimuth, 2)
    
    def _sunrise_sunset(self, dt: datetime) -> tuple[datetime, datetime]:
        """Berechne Sonnenauf- und -untergang."""
        doy = dt.timetuple().tm_yday
        
        # Declination
        decl = math.radians(-23.45 * math.cos(math.radians(360 / 365 * (doy + 10))))
        lat_rad = math.radians(self._lat)
        
        # Hour angle at sunrise
        cos_ha = -math.tan(lat_rad) * math.tan(decl)
        cos_ha = max(-1.0, min(1.0, cos_ha))
        ha_sunrise = math.degrees(math.acos(cos_ha))
        
        # Day length
        day_length_h = 2 * ha_sunrise / 15
        
        # Solar noon
        tz_offset = 2.0 if 3 <= dt.month <= 10 else 1.0
        solar_noon_h = (720 - 4 * self._lon) / 60.0 + tz_offset
        
        sunrise_h = solar_noon_h - day_length_h / 2
        sunset_h = solar_noon_h + day_length_h / 2
        
        # Konvertiere zu datetime
        sunrise = dt.replace(
            hour=int(sunrise_h),
            minute=int((sunrise_h % 1) * 60),
            second=0,
            microsecond=0,
        )
        sunset = dt.replace(
            hour=int(sunset_h),
            minute=int((sunset_h % 1) * 60),
            second=0,
            microsecond=0,
        )
        
        return sunrise, sunset
    
    def _clearsky_irradiance(self, elevation: float) -> float:
        """Berechne Clearsky-Einstrahlung (W/m²)."""
        if elevation <= 0:
            return 0.0
        
        # Extraterrestrische Einstrahlung
        I0 = 1367  # W/m²
        
        # Atmospheric attenuation (vereinfacht)
        air_mass = 1 / math.sin(math.radians(elevation))
        if air_mass < 1:
            air_mass = 1
        
        # Clearsky transmission
        tau = 0.7 ** air_mass
        
        # Direct normal irradiance
        dni = I0 * tau
        
        # Global horizontal irradiance
        ghi = dni * math.sin(math.radians(elevation))
        
        return round(ghi, 1)
    
    def _weather_factor(self, hour_offset: int) -> tuple[float, str]:
        """Berechne Wetter-Einflussfaktor und Condition."""
        weather = self._weather_data.get(hour_offset, {})
        
        cloud_cover = weather.get("cloud_cover_pct", 50)
        precip = weather.get("precipitation_mm", 0)
        weather_code = weather.get("weather_code", 0)
        
        # Basis-Reduktion durch Bewölkung
        # 0% clouds = 1.0, 100% clouds = 0.2-0.3
        cloud_factor = 1.0 - (cloud_cover / 100.0 * 0.75)
        
        # Niederschlag reduziert zusätzlich
        if precip > 0:
            cloud_factor *= 0.7  # 30% Reduktion bei Regen
        
        # Wetter-Code Einflüsse (WMO codes)
        if weather_code in [3, 45, 48]:  # Fog
            cloud_factor *= 0.5
        elif weather_code in [61, 63, 65, 80, 81, 82]:  # Rain
            cloud_factor *= 0.6
        elif weather_code in [71, 73, 75, 85, 86]:  # Snow
            cloud_factor *= 0.5
        elif weather_code in [95, 96, 99]:  # Thunderstorm
            cloud_factor *= 0.3
        
        cloud_factor = max(0.1, min(1.0, cloud_factor))
        
        # Condition bestimmen
        if cloud_cover <= 20:
            condition = "clear"
        elif cloud_cover <= 50:
            condition = "partly_cloudy"
        elif cloud_cover <= 80:
            condition = "cloudy"
        else:
            condition = "overcast"
        
        if precip > 0:
            condition = "rainy" if weather.get("temperature_c", 15) > 2 else "snowy"
        
        return round(cloud_factor, 2), condition
    
    def _panel_efficiency(self, elevation: float, azimuth: float) -> float:
        """Berechne Panel-Effizienz basierend auf Ausrichtung."""
        # Incidence angle modifier (vereinfacht)
        
        # Optimal: Sonne senkrecht auf Panel
        # Panel zeigt nach Süden (180°) mit tilt
        
        # Azimuth-Differenz
        azimuth_diff = abs(azimuth - self._panel_azimuth)
        if azimuth_diff > 180:
            azimuth_diff = 360 - azimuth_diff
        
        azimuth_factor = math.cos(math.radians(azimuth_diff))
        azimuth_factor = max(0, azimuth_factor)
        
        # Elevation optimal bei panel_tilt
        optimal_elevation = 90 - self._panel_tilt
        elevation_diff = abs(elevation - optimal_elevation)
        elevation_factor = math.cos(math.radians(min(90, elevation_diff)))
        
        # Kombination
        efficiency = azimuth_factor * 0.7 + elevation_factor * 0.3
        
        return max(0, min(1, efficiency))
    
    def generate_hourly_forecast(
        self,
        hours: int = 48,
        start_time: Optional[datetime] = None,
    ) -> list[PVHourlyForecast]:
        """Generiere stündliche PV-Prognose."""
        if start_time is None:
            start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        forecast = []
        
        for h in range(hours):
            dt = start_time + timedelta(hours=h)
            
            # Sonnenposition
            elevation, azimuth = self._solar_position(dt)
            
            # Clearsky Einstrahlung
            clearsky_ghi = self._clearsky_irradiance(elevation)
            
            # Wetter-Einfluss
            weather_factor, condition = self._weather_factor(h)
            
            # Tatsächliche Einstrahlung
            actual_ghi = clearsky_ghi * weather_factor
            
            # Panel-Effizienz
            panel_eff = self._panel_efficiency(elevation, azimuth)
            
            # PV-Leistung
            # P = G × P_peak × system_efficiency × panel_efficiency
            pv_power = actual_ghi / 1000 * self._pv_peak * self._system_efficiency * panel_eff
            
            # Nachts null
            if elevation <= 0:
                pv_power = 0
                actual_ghi = 0
            
            pv_energy_wh = pv_power * 1000  # Wh für eine Stunde
            
            point = PVHourlyForecast(
                timestamp=dt.isoformat(),
                hour=h,
                solar_elevation=elevation,
                solar_azimuth=azimuth,
                clearsky_irradiance_wm2=round(clearsky_ghi, 1),
                actual_irradiance_wm2=round(actual_ghi, 1),
                pv_power_kw=round(pv_power, 3),
                pv_energy_wh=round(pv_energy_wh, 1),
                cloud_cover_pct=self._weather_data.get(h, {}).get("cloud_cover_pct", 50),
                weather_condition=condition,
                efficiency_factor=round(panel_eff * self._system_efficiency * weather_factor, 3),
            )
            forecast.append(point)
        
        return forecast
    
    def generate_daily_forecast(
        self,
        days: int = 7,
    ) -> list[PVDailyForecast]:
        """Generiere tägliche PV-Prognose."""
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_forecasts = []
        
        for d in range(days):
            day_start = start_time + timedelta(days=d)
            hourly = self.generate_hourly_forecast(hours=24, start_time=day_start)
            
            # Tages-Zusammenfassung
            total_energy_wh = sum(h.pv_energy_wh for h in hourly)
            peak_hour = max(hourly, key=lambda h: h.pv_power_kw)
            
            # Sonnenauf-/untergang
            sunrise, sunset = self._sunrise_sunset(day_start)
            solar_noon = day_start.replace(
                hour=(sunrise.hour + sunset.hour) // 2,
                minute=30,
            )
            
            daylight_hours = (sunset - sunrise).total_seconds() / 3600
            
            # Durchschnittliche Bewölkung
            avg_cloud = sum(h.cloud_cover_pct for h in hourly) / len(hourly)
            
            # Wetter-Qualität
            if avg_cloud <= 20:
                quality = "excellent"
            elif avg_cloud <= 40:
                quality = "good"
            elif avg_cloud <= 70:
                quality = "fair"
            else:
                quality = "poor"
            
            daily = PVDailyForecast(
                date=day_start.strftime("%Y-%m-%d"),
                total_energy_kwh=round(total_energy_wh / 1000, 2),
                peak_power_kw=round(peak_hour.pv_power_kw, 3),
                peak_time=peak_hour.timestamp,
                sunrise=sunrise.isoformat(),
                sunset=sunset.isoformat(),
                solar_noon=solar_noon.isoformat(),
                daylight_hours=round(daylight_hours, 1),
                avg_cloud_cover_pct=round(avg_cloud, 0),
                weather_quality=quality,
            )
            daily_forecasts.append(daily)
        
        return daily_forecasts
    
    def generate_summary(
        self,
        hourly_forecast: Optional[list[PVHourlyForecast]] = None,
    ) -> PVForecastSummary:
        """Generiere Zusammenfassung."""
        if hourly_forecast is None:
            hourly_forecast = self.generate_hourly_forecast()
        
        total_energy_wh = sum(h.pv_energy_wh for h in hourly_forecast)
        peak_hour = max(hourly_forecast, key=lambda h: h.pv_power_kw)
        
        # Gruppiere nach Tagen
        days = {}
        for h in hourly_forecast:
            date = h.timestamp[:10]
            if date not in days:
                days[date] = 0
            days[date] += h.pv_energy_wh
        
        best_day = max(days.items(), key=lambda x: x[1])[0] if days else ""
        worst_day = min(days.items(), key=lambda x: x[1])[0] if days else ""
        
        # Sonnenstunden (wenn elevation > 0)
        sunlight_hours = sum(1 for h in hourly_forecast if h.solar_elevation > 0)
        
        # Wetter-Einfluss
        clearsky_total = sum(h.clearsky_irradiance_wm2 for h in hourly_forecast)
        actual_total = sum(h.actual_irradiance_wm2 for h in hourly_forecast)
        weather_impact = ((clearsky_total - actual_total) / clearsky_total * 100) if clearsky_total > 0 else 0
        
        return PVForecastSummary(
            forecast_horizon_hours=len(hourly_forecast),
            total_energy_kwh=round(total_energy_wh / 1000, 2),
            avg_daily_energy_kwh=round(total_energy_wh / 1000 / max(1, len(days)), 2),
            peak_power_kw=round(peak_hour.pv_power_kw, 3),
            peak_time=peak_hour.timestamp,
            best_production_day=best_day,
            worst_production_day=worst_day,
            total_sunlight_hours=sunlight_hours,
            weather_impact_pct=round(weather_impact, 1),
        )
    
    def get_pv_forecast_as_dict(
        self,
        hours: int = 48,
    ) -> dict:
        """Generiere komplettes Forecast als Dictionary."""
        hourly = self.generate_hourly_forecast(hours)
        summary = self.generate_summary(hourly)
        
        return {
            "generated_at": datetime.now().isoformat(),
            "pv_system": {
                "peak_kw": self._pv_peak,
                "azimuth": self._panel_azimuth,
                "tilt": self._panel_tilt,
                "efficiency": self._system_efficiency,
            },
            "location": {
                "latitude": self._lat,
                "longitude": self._lon,
            },
            "summary": asdict(summary),
            "hourly_forecast": [asdict(h) for h in hourly],
            "daily_forecast": [asdict(d) for d in self.generate_daily_forecast()],
        }
