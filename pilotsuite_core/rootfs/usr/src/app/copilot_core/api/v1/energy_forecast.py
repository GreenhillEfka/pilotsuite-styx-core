"""Energy Forecast API Endpoints — v12.6.0.

REST API für Energie-Prognosen:
- Verbrauchsprognose (24h/7d)
- PV-Ertragsprognose
- Load Shifting Empfehlungen
- Kostenoptimierung

GET /api/v1/energy/forecast/consumption
GET /api/v1/energy/forecast/pv
GET /api/v1/energy/forecast/combined
GET /api/v1/energy/load-shifting/recommendations
GET /api/v1/energy/load-shifting/windows
POST /api/v1/energy/load-shifting/devices
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from flask import Blueprint, jsonify, request, current_app

from copilot_core.api.security import require_token
from copilot_core.energy.forecast import EnergyForecastEngine
from copilot_core.energy.pv_prediction import PVPredictionEngine
from copilot_core.energy.load_shifting import LoadShiftingEngine, ShiftableDevice
from copilot_core.energy.optimization_engine import (
    EnergyReading,
    EnergyUnit,
    OptimizationType,
    create_energy_optimization_engine,
)

_LOGGER = logging.getLogger(__name__)

energy_forecast_bp = Blueprint("energy_forecast", __name__, url_prefix="/api/v1/energy")
_default_optimization_engine = create_energy_optimization_engine()


def _get_weather_service():
    """Hole Weather Service aus App Config oder Modul-Instanz."""
    try:
        services = current_app.config.get("COPILOT_SERVICES", {})
        svc = services.get("weather_service")
        if svc:
            return svc
    except Exception:
        pass
    # Fallback: module-level weather service instance
    try:
        from copilot_core.api.v1.weather import get_weather_service
        return get_weather_service()
    except Exception:
        return None


def _get_energy_service():
    """Hole Energy Service aus App Config."""
    try:
        services = current_app.config.get("COPILOT_SERVICES", {})
        return services.get("energy_service")
    except Exception:
        return None


def _get_optimization_engine():
    """Hole Optimization Engine aus App Config oder nutze den Modul-Singleton."""
    try:
        engine = current_app.config.get("COPILOT_ENERGY_OPTIMIZATION_ENGINE")
        if engine is not None:
            return engine
    except Exception:
        pass
    return _default_optimization_engine


def _parse_energy_unit(raw_unit: Optional[str]) -> EnergyUnit:
    """Parse unit names case-insensitively with sane defaults."""
    normalized = (raw_unit or "W").strip()
    for unit in EnergyUnit:
        if unit.value.lower() == normalized.lower() or unit.name.lower() == normalized.lower():
            return unit
    raise ValueError(f"Unsupported energy unit: {raw_unit}")


def _get_budget_value(*names: str) -> Optional[float]:
    """Read a numeric budget value from query params if present."""
    for name in names:
        raw = request.args.get(name)
        if raw in (None, ""):
            continue
        return float(raw)
    return None


def _default_suggestion_explanation(suggestion: dict) -> str:
    """Create a compact fallback explanation string."""
    action = suggestion.get("action_required") or {}
    best_hour = action.get("best_start_hour")
    parts = [suggestion.get("description", "Optimierungsvorschlag verfügbar.")]
    savings = suggestion.get("estimated_savings")
    unit = suggestion.get("estimated_savings_unit")
    if savings is not None and unit:
        parts.append(f"Erwartete Ersparnis: {savings:.3f} {unit}.")
    if best_hour is not None:
        parts.append(f"Empfohlenes Startfenster ab {int(best_hour):02d}:00 Uhr.")
    parts.append("Ausführung bleibt policy-gated und erfordert bewusste Annahme.")
    return " ".join(parts)


def _fetch_weather_forecast(hours: int = 48) -> list[dict]:
    """Hole Wetterdaten von Weather Service oder generiere Defaults.

    Returns a list of hourly dicts with keys the energy engines expect:
    temperature_c, cloud_cover_pct, precipitation_mm, weather_code, timestamp.
    """
    weather_service = _get_weather_service()

    # Try services dict first (sync call with hourly data)
    if weather_service and hasattr(weather_service, "get_forecast"):
        try:
            import asyncio
            forecast_raw = asyncio.run(weather_service.get_forecast(days=max(1, hours // 24)))
            daily = forecast_raw.get("forecast", []) if isinstance(forecast_raw, dict) else []
            # Expand daily → hourly (interpolate for each day)
            hourly: list[dict] = []
            for day in daily:
                cloud = day.get("cloud_cover_percent", 50)
                temp_high = day.get("temperature_high_c", 15.0)
                temp_low = day.get("temperature_low_c", 5.0)
                precip_prob = day.get("precipitation_probability", 0)
                ts_base = day.get("timestamp", "")
                for h in range(24):
                    # Simple diurnal temperature curve
                    t_frac = 0.5 * (1 + __import__("math").sin((h - 6) / 24 * 2 * 3.14159 - 1.5708))
                    temp = temp_low + (temp_high - temp_low) * t_frac
                    hourly.append({
                        "timestamp": ts_base,
                        "temperature_c": round(temp, 1),
                        "cloud_cover_pct": cloud,
                        "precipitation_mm": round(precip_prob * 0.05, 1),
                        "weather_code": 0 if cloud < 30 else 1 if cloud < 60 else 3,
                    })
                    if len(hourly) >= hours:
                        break
                if len(hourly) >= hours:
                    break
            return hourly[:hours]
        except Exception as e:
            _LOGGER.warning("Weather forecast fetch error: %s", e)

    # Fallback: generate default weather based on time of day
    from datetime import datetime, timedelta
    now = datetime.now()
    result = []
    for i in range(hours):
        dt = now + timedelta(hours=i)
        h = dt.hour
        # Simple diurnal pattern
        temp = 5.0 + 10.0 * max(0, __import__("math").sin((h - 6) / 24 * 2 * 3.14159 - 1.5708))
        cloud = 40  # moderate default
        result.append({
            "timestamp": dt.isoformat(),
            "temperature_c": round(temp, 1),
            "cloud_cover_pct": cloud,
            "precipitation_mm": 0.0,
            "weather_code": 1,
        })
    return result


def _fetch_price_forecast(hours: int = 48) -> list[dict]:
    """Hole Strompreis-Prognose."""
    energy_service = _get_energy_service()
    if not energy_service:
        return []
    
    try:
        # Annahme: Energy Service hat Preis-Daten
        prices = energy_service.get_price_forecast(hours=hours)
        return prices if isinstance(prices, list) else []
    except Exception as e:
        _LOGGER.warning("Price forecast fetch error: %s", e)
        return []


@energy_forecast_bp.route("/", methods=["GET"])
@require_token
def energy_root():
    """Root route — returns energy snapshot in format HA integration expects.

    HA energy_context.py expects fields: timestamp, total_consumption_today_kwh,
    total_production_today_kwh, current_power_watts, peak_power_today_watts,
    anomalies_detected, shifting_opportunities, baselines.daily_average
    """
    try:
        now = datetime.now()

        weather_service = _get_weather_service()
        cloud_cover = 50
        if weather_service:
            try:
                current_weather = weather_service.get_current()
                cloud_cover = current_weather.get("cloud_cover_pct", 50) if current_weather else 50
            except Exception:
                pass

        pv_kw = max(0, 5.0 * (1 - cloud_cover / 100))
        if now.hour < 6 or now.hour > 20:
            pv_kw = 0

        hour = now.hour
        if 18 <= hour <= 21:
            consumption_kw = 1.2
        elif 6 <= hour <= 9:
            consumption_kw = 0.7
        else:
            consumption_kw = 0.4

        daily_consumption = round(consumption_kw * 24 * 0.6, 1)
        daily_production = round(pv_kw * 6, 1)

        return jsonify({
            "ok": True,
            "timestamp": now.isoformat(),
            "total_consumption_today_kwh": daily_consumption,
            "total_production_today_kwh": daily_production,
            "current_power_watts": round(consumption_kw * 1000, 0),
            "peak_power_today_watts": round(consumption_kw * 1000 * 1.5, 0),
            "anomalies_detected": 0,
            "shifting_opportunities": 1 if 10 <= hour <= 16 and pv_kw > 1 else 0,
            "baselines": {
                "daily_average": round(daily_consumption * 0.95, 1),
            },
        })
    except Exception as e:
        _LOGGER.error("Energy root error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/forecast/consumption", methods=["GET"])
@require_token
def get_consumption_forecast():
    """Hole Verbrauchsprognose.
    
    Query Params:
    - hours: Prognosehorizont (default 48, max 168)
    - include_weather: Wettereinfluss berücksichtigen (default true)
    
    Returns:
    {
        "ok": true,
        "generated_at": "...",
        "forecast_horizon_hours": 48,
        "summary": {...},
        "hourly_forecast": [...],
        "daily_forecast": [...]
    }
    """
    try:
        hours = min(int(request.args.get("hours", 48)), 168)
        include_weather = request.args.get("include_weather", "true").lower() == "true"
        
        # Engine initialisieren
        engine = EnergyForecastEngine()
        
        # Standort von Energy Service oder Config
        energy_service = _get_energy_service()
        if energy_service:
            try:
                location = energy_service.get_location()
                if location:
                    engine.update_location(location.get("lat", 51.0), location.get("lon", 10.0))
            except Exception:
                pass
        
        # Wetterdaten
        weather_data = []
        if include_weather:
            weather_raw = _fetch_weather_forecast(hours)
            weather_data = [
                {
                    "temperature_c": w.get("temperature_c"),
                    "cloud_cover_pct": w.get("cloud_cover_pct", 50),
                }
                for w in weather_raw
            ] if weather_raw else []
        
        # Generiere Prognose
        result = engine.get_forecast_as_dict(hours=hours, weather_data=weather_data)
        
        return jsonify({
            "ok": True,
            **result,
        })
    
    except Exception as e:
        _LOGGER.error("Consumption forecast error: %s", e)
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@energy_forecast_bp.route("/forecast/pv", methods=["GET"])
@require_token
def get_pv_forecast():
    """Hole PV-Ertragsprognose.
    
    Query Params:
    - hours: Prognosehorizont (default 48)
    - peak_kw: PV-Anlagenleistung (optional, sonst Config)
    - azimuth: Panel-Ausrichtung (optional)
    - tilt: Panel-Neigung (optional)
    
    Returns:
    {
        "ok": true,
        "pv_system": {...},
        "location": {...},
        "summary": {...},
        "hourly_forecast": [...],
        "daily_forecast": [...]
    }
    """
    try:
        hours = min(int(request.args.get("hours", 48)), 168)
        peak_kw = float(request.args.get("peak_kw", 10.0))
        azimuth = float(request.args.get("azimuth", 180.0))
        tilt = float(request.args.get("tilt", 30.0))
        
        # Engine initialisieren
        engine = PVPredictionEngine(
            pv_peak_kw=peak_kw,
            panel_azimuth=azimuth,
            panel_tilt=tilt,
        )
        
        # Standort
        energy_service = _get_energy_service()
        if energy_service:
            try:
                location = energy_service.get_location()
                if location:
                    engine.update_location(location.get("lat", 51.0), location.get("lon", 10.0))
            except Exception:
                pass
        
        # Wetterdaten
        weather_raw = _fetch_weather_forecast(hours)
        if weather_raw:
            weather_data = [
                {
                    "timestamp": w.get("timestamp"),
                    "temperature_c": w.get("temperature_c"),
                    "cloud_cover_pct": w.get("cloud_cover_pct", 50),
                    "precipitation_mm": w.get("precipitation_mm", 0),
                    "weather_code": w.get("weather_code", 0),
                }
                for w in weather_raw
            ]
            engine.set_weather_data(weather_data)
        
        # Generiere Prognose
        result = engine.get_pv_forecast_as_dict(hours=hours)
        
        return jsonify({
            "ok": True,
            **result,
        })
    
    except Exception as e:
        _LOGGER.error("PV forecast error: %s", e)
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@energy_forecast_bp.route("/forecast/combined", methods=["GET"])
@require_token
def get_combined_forecast():
    """Hole kombinierte Energie-Prognose (Verbrauch + PV + Preise).
    
    Query Params:
    - hours: Prognosehorizont (default 48)
    - include_load_shifting: Load Shifting Empfehlungen (default true)
    
    Returns:
    {
        "ok": true,
        "consumption": {...},
        "pv": {...},
        "prices": {...},
        "balance": [...],  # Stunde für Stunde
        "recommendations": [...]
    }
    """
    try:
        hours = min(int(request.args.get("hours", 48)), 168)
        include_shifting = request.args.get("include_load_shifting", "true").lower() == "true"
        
        # Hole Einzelprognosen
        consumption_engine = EnergyForecastEngine()
        pv_engine = PVPredictionEngine()
        
        # Wetterdaten
        weather_raw = _fetch_weather_forecast(hours)
        weather_data = [
            {
                "temperature_c": w.get("temperature_c"),
                "cloud_cover_pct": w.get("cloud_cover_pct", 50),
            }
            for w in weather_raw
        ] if weather_raw else []
        
        # Verbrauchsprognose
        consumption_forecast = consumption_engine.generate_hourly_forecast(
            hours=hours,
            weather_data=weather_data,
        )
        
        # PV-Prognose
        pv_weather_data = []
        if weather_raw:
            pv_weather_data = [
                {
                    "timestamp": w.get("timestamp"),
                    "temperature_c": w.get("temperature_c"),
                    "cloud_cover_pct": w.get("cloud_cover_pct", 50),
                    "precipitation_mm": w.get("precipitation_mm", 0),
                    "weather_code": w.get("weather_code", 0),
                }
                for w in weather_raw
            ]
            pv_engine.set_weather_data(pv_weather_data)
        
        pv_forecast = pv_engine.generate_hourly_forecast(hours=hours)
        
        # Preisprognose
        price_forecast = _fetch_price_forecast(hours)
        
        # Balance berechnen (PV - Verbrauch)
        balance = []
        for i in range(hours):
            consumption = consumption_forecast[i].predicted_consumption_kw if i < len(consumption_forecast) else 0
            pv = pv_forecast[i].pv_power_kw if i < len(pv_forecast) else 0
            price = price_forecast[i].get("price_ct_kwh", 30.0) if i < len(price_forecast) else 30.0
            
            balance.append({
                "hour": i,
                "timestamp": consumption_forecast[i].timestamp if i < len(consumption_forecast) else "",
                "consumption_kw": round(consumption, 3),
                "pv_kw": round(pv, 3),
                "balance_kw": round(pv - consumption, 3),  # Positiv = Überschuss
                "price_ct_kwh": round(price, 2),
                "self_sufficiency_pct": round(min(100, pv / max(0.1, consumption) * 100), 1),
            })
        
        # Load Shifting Empfehlungen
        recommendations = []
        if include_shifting:
            shifting_engine = LoadShiftingEngine(
                pv_forecast=[asdict(p) for p in pv_forecast],
                price_forecast=price_forecast,
                consumption_forecast=[asdict(c) for c in consumption_forecast],
            )
            
            # Standard-Geräte hinzufügen
            shifting_engine.add_device_from_profile("washer_1", "washer", "Waschmaschine")
            shifting_engine.add_device_from_profile("dryer_1", "dryer", "Wäschetrockner")
            shifting_engine.add_device_from_profile("dishwasher_1", "dishwasher", "Geschirrspüler")
            shifting_engine.add_device_from_profile("ev_1", "ev_charger", "EV-Ladestation")
            
            rec_result = shifting_engine.get_recommendations_as_dict()
            recommendations = rec_result.get("recommendations", [])
        
        return jsonify({
            "ok": True,
            "generated_at": datetime.now().isoformat(),
            "forecast_horizon_hours": hours,
            "consumption_summary": asdict(consumption_engine.generate_summary(consumption_forecast)),
            "pv_summary": asdict(pv_engine.generate_summary(pv_forecast)),
            "balance": balance,
            "recommendations": recommendations,
        })
    
    except Exception as e:
        _LOGGER.error("Combined forecast error: %s", e)
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@energy_forecast_bp.route("/load-shifting/recommendations", methods=["GET"])
@require_token
def get_load_shifting_recommendations():
    """Hole Load Shifting Empfehlungen.
    
    Query Params:
    - hours: Betrachtungshorizont (default 24)
    
    Returns:
    {
        "ok": true,
        "summary": {...},
        "recommendations": [...],
        "optimization_windows": [...]
    }
    """
    try:
        hours = min(int(request.args.get("hours", 24)), 48)
        
        # Daten holen
        pv_raw = _fetch_weather_forecast(hours)
        pv_forecast = []
        if pv_raw:
            # Vereinfachte PV-Schätzung aus Bewölkung
            for i, w in enumerate(pv_raw):
                cloud = w.get("cloud_cover_pct", 50)
                pv_kw = max(0, 5.0 * (1 - cloud / 100))  # 5kW Peak Annahme
                pv_forecast.append({"pv_power_kw": pv_kw})
        
        price_forecast = _fetch_price_forecast(hours)
        consumption_forecast = []  # Könnte von Energy Service kommen
        
        # Engine
        engine = LoadShiftingEngine(
            pv_forecast=pv_forecast,
            price_forecast=price_forecast,
            consumption_forecast=consumption_forecast,
        )
        
        # Standard-Geräte
        engine.add_device_from_profile("washer_1", "washer", "Waschmaschine")
        engine.add_device_from_profile("dryer_1", "dryer", "Wäschetrockner")
        engine.add_device_from_profile("dishwasher_1", "dishwasher", "Geschirrspüler")
        engine.add_device_from_profile("ev_1", "ev_charger", "EV-Ladestation", power_kw=11.0, energy_kwh=40.0)
        
        result = engine.get_recommendations_as_dict()
        
        return jsonify({
            "ok": True,
            **result,
        })
    
    except Exception as e:
        _LOGGER.error("Load shifting recommendations error: %s", e)
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@energy_forecast_bp.route("/load-shifting/windows", methods=["GET"])
@require_token
def get_optimization_windows():
    """Hole optimale Zeitfenster für Verbrauch.
    
    Query Params:
    - hours: Horizont (default 24)
    
    Returns:
    {
        "ok": true,
        "windows": [
            {
                "start": "...",
                "end": "...",
                "avg_price_ct_kwh": ...,
                "avg_pv_power_kw": ...,
                "recommendation": "..."
            },
            ...
        ]
    }
    """
    try:
        hours = min(int(request.args.get("hours", 24)), 48)
        
        # Engine mit minimalen Daten
        engine = LoadShiftingEngine()
        
        # Wetter für PV
        weather_raw = _fetch_weather_forecast(hours)
        if weather_raw:
            pv_forecast = [
                {"pv_power_kw": max(0, 5.0 * (1 - w.get("cloud_cover_pct", 50) / 100))}
                for w in weather_raw
            ]
            engine.set_pv_forecast(pv_forecast)
        
        # Preise
        price_forecast = _fetch_price_forecast(hours)
        engine.set_price_forecast(price_forecast)
        
        windows = engine.generate_optimization_windows(hours_ahead=hours)
        
        return jsonify({
            "ok": True,
            "generated_at": datetime.now().isoformat(),
            "windows": [asdict(w) for w in windows],
        })
    
    except Exception as e:
        _LOGGER.error("Optimization windows error: %s", e)
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@energy_forecast_bp.route("/load-shifting/devices", methods=["POST"])
@require_token
def register_shiftable_device():
    """Registriere verschiebbares Gerät.
    
    Body:
    {
        "device_id": "...",
        "device_type": "washer|dryer|dishwasher|ev_charger|heat_pump|battery",
        "name": "...",
        "power_kw": 2.0,
        "energy_kwh": 1.5,
        "duration_hours": 1.5,
        "flexibility_hours": 8,
        "priority": 3,
        "min_start_hour": 0,
        "max_start_hour": 23,
        "must_complete_by": "2024-01-01T18:00:00"
    }
    
    Returns:
    {
        "ok": true,
        "device": {...},
        "message": "Gerät registriert"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "ok": False,
                "error": "Keine Daten",
            }), 400
        
        required = ["device_id", "device_type", "name"]
        for field in required:
            if field not in data:
                return jsonify({
                    "ok": False,
                    "error": f"Fehlendes Feld: {field}",
                }), 400
        
        # Gerät erstellen
        device = ShiftableDevice(
            device_id=data["device_id"],
            device_type=data["device_type"],
            name=data["name"],
            power_kw=data.get("power_kw", 2.0),
            energy_kwh=data.get("energy_kwh", 1.5),
            duration_hours=data.get("duration_hours", 1.5),
            flexibility_hours=data.get("flexibility_hours", 8),
            priority=data.get("priority", 3),
            min_start_hour=data.get("min_start_hour", 0),
            max_start_hour=data.get("max_start_hour", 23),
            must_complete_by=data.get("must_complete_by"),
            current_state=data.get("current_state", "idle"),
            cost_per_kwh=data.get("cost_per_kwh", 30.0),
        )
        
        # In Session speichern (hier: temporär)
        # In Produktion: Database oder Energy Service
        _LOGGER.info("Registered shiftable device: %s (%s)", device.device_id, device.device_type)
        
        return jsonify({
            "ok": True,
            "device": asdict(device),
            "message": f"Gerät '{device.name}' registriert",
        })
    
    except Exception as e:
        _LOGGER.error("Register device error: %s", e)
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@energy_forecast_bp.route("/summary", methods=["GET"])
@require_token
def get_energy_summary():
    """Hole kompakte Energie-Übersicht für Dashboard.
    
    Returns:
    {
        "ok": true,
        "current": {
            "consumption_kw": ...,
            "pv_kw": ...,
            "balance_kw": ...,
            "price_ct_kwh": ...
        },
        "today": {
            "consumption_kwh": ...,
            "pv_kwh": ...,
            "cost_eur": ...,
            "self_sufficiency_pct": ...
        },
        "next_24h": {
            "best_consumption_hour": "...",
            "best_pv_hour": "...",
            "recommendation": "..."
        }
    }
    """
    try:
        # Aktuelle Daten (vereinfacht)
        now = datetime.now()
        
        # Wetter für aktuelle PV-Schätzung
        weather_service = _get_weather_service()
        cloud_cover = 50
        if weather_service:
            try:
                current_weather = weather_service.get_current()
                cloud_cover = current_weather.get("cloud_cover_pct", 50) if current_weather else 50
            except Exception:
                pass
        
        # PV-Schätzung
        pv_kw = max(0, 5.0 * (1 - cloud_cover / 100))
        if now.hour < 6 or now.hour > 20:
            pv_kw = 0
        
        # Verbrauch (Basis-Profil)
        hour = now.hour
        if 18 <= hour <= 21:
            consumption_kw = 1.2
        elif 6 <= hour <= 9:
            consumption_kw = 0.7
        else:
            consumption_kw = 0.4
        
        balance = pv_kw - consumption_kw
        
        # Preis
        price = 30.0
        price_forecast = _fetch_price_forecast(1)
        if price_forecast:
            price = price_forecast[0].get("price_ct_kwh", 30.0)
        
        return jsonify({
            "ok": True,
            "generated_at": now.isoformat(),
            "current": {
                "consumption_kw": round(consumption_kw, 2),
                "pv_kw": round(pv_kw, 2),
                "balance_kw": round(balance, 2),
                "price_ct_kwh": round(price, 2),
                "grid_import": round(max(0, consumption_kw - pv_kw), 2),
                "pv_export": round(max(0, pv_kw - consumption_kw), 2),
            },
            "today": {
                "consumption_kwh": round(consumption_kw * 24 * 0.6, 1),  # Schätzung
                "pv_kwh": round(pv_kw * 6, 1),  # Schätzung
                "cost_eur": round(consumption_kw * 24 * 0.6 * price / 100, 2),
                "self_sufficiency_pct": round(min(100, pv_kw / max(0.1, consumption_kw) * 100), 1),
            },
            "next_24h": {
                "best_consumption_hour": "14:00" if 14 > hour else "14:00 (morgen)",
                "best_pv_hour": "13:00" if 13 > hour else "13:00 (morgen)",
                "recommendation": "Waschmaschine heute Nachmittag starten — PV-Spitze!",
            },
        })
    
    except Exception as e:
        _LOGGER.error("Energy summary error: %s", e)
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@energy_forecast_bp.route("/optimization/readings", methods=["POST"])
@require_token
def add_optimization_readings():
    """Register one or many energy readings for optimization analysis."""
    try:
        data = request.get_json(silent=True) or {}
        payload_items = data.get("readings") if isinstance(data, dict) and "readings" in data else [data]

        if not payload_items:
            return jsonify({"ok": False, "error": "Keine Readings übergeben"}), 400

        engine = _get_optimization_engine()
        accepted = 0
        suggestions_before = len(engine.get_suggestions(unresolved_only=False))

        for item in payload_items:
            if not isinstance(item, dict):
                return jsonify({"ok": False, "error": "Ungültiges Reading-Format"}), 400

            required = ["entity_id", "zone_id", "module_id", "value"]
            missing = [field for field in required if field not in item]
            if missing:
                return jsonify({"ok": False, "error": f"Fehlende Felder: {', '.join(missing)}"}), 400

            reading = EnergyReading(
                entity_id=item["entity_id"],
                zone_id=item["zone_id"],
                module_id=item["module_id"],
                value=float(item["value"]),
                unit=_parse_energy_unit(item.get("unit")),
                timestamp=item.get("timestamp") or datetime.utcnow().isoformat() + "Z",
                cost=float(item["cost"]) if item.get("cost") is not None else None,
                tariff_rate=item.get("tariff_rate"),
            )
            engine.add_reading(reading)
            accepted += 1

        suggestions_after = len(engine.get_suggestions(unresolved_only=False))
        summary = engine.get_energy_summary(
            zone_id=data.get("zone_id") if isinstance(data, dict) else None,
            period_hours=int(data.get("period_hours", 24)) if isinstance(data, dict) else 24,
        )

        return jsonify({
            "ok": True,
            "accepted": accepted,
            "created_suggestions": max(0, suggestions_after - suggestions_before),
            "summary": summary,
        })
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as e:
        _LOGGER.error("Optimization readings error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/optimization/summary", methods=["GET"])
@require_token
def get_optimization_summary():
    """Return optimization summary with savings tracking and tariff context."""
    try:
        engine = _get_optimization_engine()
        period_hours = min(int(request.args.get("hours", 24)), 24 * 30)
        zone_id = request.args.get("zone_id")
        budget_eur = _get_budget_value("budget_eur", "monthly_budget_eur", "daily_budget_eur")
        report = engine.get_report(zone_id=zone_id, period_hours=period_hours, budget_eur=budget_eur)

        return jsonify({
            "ok": True,
            **report,
        })
    except Exception as e:
        _LOGGER.error("Optimization summary error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/optimization/suggestions", methods=["GET"])
@require_token
def get_optimization_suggestions():
    """Return optimization suggestions with optional filters."""
    try:
        engine = _get_optimization_engine()
        unresolved_only = request.args.get("unresolved_only", "true").lower() == "true"
        suggestion_type = request.args.get("type")
        zone_id = request.args.get("zone_id")
        suggestions = engine.get_suggestions(
            unresolved_only=unresolved_only,
            optimization_type=suggestion_type,
            zone_id=zone_id,
        )

        return jsonify({
            "ok": True,
            "count": len(suggestions),
            "suggestions": suggestions,
        })
    except Exception as e:
        _LOGGER.error("Optimization suggestions error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/optimization/suggestions/<suggestion_id>/accept", methods=["POST"])
@require_token
def accept_optimization_suggestion(suggestion_id: str):
    """Accept an optimization suggestion."""
    try:
        engine = _get_optimization_engine()
        if not engine.accept_suggestion(suggestion_id):
            return jsonify({"ok": False, "error": "Suggestion not found"}), 404
        return jsonify({
            "ok": True,
            "suggestion": engine.get_suggestion(suggestion_id),
            "message": "Optimierungsvorschlag akzeptiert",
        })
    except Exception as e:
        _LOGGER.error("Accept optimization suggestion error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/optimization/suggestions/<suggestion_id>/reject", methods=["POST"])
@require_token
def reject_optimization_suggestion(suggestion_id: str):
    """Reject an optimization suggestion with optional feedback."""
    try:
        engine = _get_optimization_engine()
        data = request.get_json(silent=True) or {}
        if not engine.reject_suggestion(suggestion_id, feedback=data.get("feedback")):
            return jsonify({"ok": False, "error": "Suggestion not found"}), 404
        return jsonify({
            "ok": True,
            "suggestion": engine.get_suggestion(suggestion_id),
            "message": "Optimierungsvorschlag verworfen",
        })
    except Exception as e:
        _LOGGER.error("Reject optimization suggestion error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/tariff/forecast", methods=["GET"])
@require_token
def get_tariff_forecast_route():
    """Return the tariff forecast from the optimization engine."""
    try:
        engine = _get_optimization_engine()
        hours = min(int(request.args.get("hours", 24)), 24 * 7)
        forecast = engine.get_tariff_forecast(hours_ahead=hours)
        return jsonify({
            "ok": True,
            "hours_ahead": hours,
            "forecast": forecast,
        })
    except Exception as e:
        _LOGGER.error("Tariff forecast error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Stub routes for HA sensors that poll these endpoints ──────────────


@energy_forecast_bp.route("/anomalies", methods=["GET"])
@require_token
def energy_anomalies():
    """Energy anomalies — stub until real anomaly detection is wired."""
    return jsonify({"ok": True, "anomalies": []})


@energy_forecast_bp.route("/shifting", methods=["GET"])
@require_token
def energy_shifting():
    """Load shifting opportunities backed by the optimization engine."""
    try:
        engine = _get_optimization_engine()
        opportunities = engine.get_suggestions(
            unresolved_only=True,
            optimization_type=OptimizationType.SCHEDULE_SHIFT,
            zone_id=request.args.get("zone_id"),
        )
        return jsonify({"ok": True, "count": len(opportunities), "opportunities": opportunities})
    except Exception as e:
        _LOGGER.error("Energy shifting error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/explain/<suggestion_id>", methods=["GET"])
@require_token
def energy_explain(suggestion_id):
    """Explain an energy suggestion from the optimization engine."""
    try:
        engine = _get_optimization_engine()
        explanation = engine.explain_suggestion(suggestion_id)
        if explanation is None:
            suggestion = engine.get_suggestion(suggestion_id)
            if suggestion is None:
                return jsonify({"ok": False, "error": "Suggestion not found"}), 404
            explanation = {
                "suggestion": suggestion,
                "explanation": _default_suggestion_explanation(suggestion),
                "policy_gate_required": True,
                "recommended_action": suggestion.get("action_required") or {},
            }
        return jsonify({"ok": True, "suggestion_id": suggestion_id, **explanation})
    except Exception as e:
        _LOGGER.error("Energy explain error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/costs", methods=["GET"])
@require_token
def energy_costs():
    """Energy cost view backed by optimization summary and tariff forecast."""
    try:
        engine = _get_optimization_engine()
        period_hours = min(int(request.args.get("hours", 24)), 24 * 30)
        summary = engine.get_energy_summary(zone_id=request.args.get("zone_id"), period_hours=period_hours)
        tariff_forecast = engine.get_tariff_forecast(hours_ahead=min(period_hours, 24))
        return jsonify({
            "ok": True,
            "period_hours": period_hours,
            "costs": {
                "total_cost_eur": round(summary["total_cost"], 4),
                "average_cost_per_kwh": round(summary["total_cost"] / summary["total_consumption_kwh"], 4) if summary["total_consumption_kwh"] else 0.0,
                "total_consumption_kwh": round(summary["total_consumption_kwh"], 4),
            },
            "current_tariff": tariff_forecast[0] if tariff_forecast else None,
        })
    except Exception as e:
        _LOGGER.error("Energy costs error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/costs/budget", methods=["GET"])
@require_token
def energy_costs_budget():
    """Budget tracking for current energy spend."""
    try:
        engine = _get_optimization_engine()
        period_hours = min(int(request.args.get("hours", 24)), 24 * 30)
        budget_eur = _get_budget_value("budget_eur", "monthly_budget_eur", "daily_budget_eur")
        if budget_eur is None:
            return jsonify({"ok": False, "error": "budget_eur/monthly_budget_eur/daily_budget_eur required"}), 400
        report = engine.get_report(
            zone_id=request.args.get("zone_id"),
            period_hours=period_hours,
            budget_eur=budget_eur,
        )
        return jsonify({"ok": True, "budget": report.get("budget"), "summary": report.get("summary")})
    except Exception as e:
        _LOGGER.error("Energy budget error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/costs/summary", methods=["GET"])
@require_token
def energy_costs_summary():
    """Compact cost/savings summary."""
    try:
        engine = _get_optimization_engine()
        period_hours = min(int(request.args.get("hours", 24)), 24 * 30)
        report = engine.get_report(
            zone_id=request.args.get("zone_id"),
            period_hours=period_hours,
            budget_eur=_get_budget_value("budget_eur", "monthly_budget_eur", "daily_budget_eur"),
        )
        return jsonify({
            "ok": True,
            "summary": report["summary"],
            "savings": report["savings"],
            "budget": report.get("budget"),
        })
    except Exception as e:
        _LOGGER.error("Energy costs summary error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/sankey", methods=["GET"])
@require_token
def energy_sankey():
    """Energy Sankey data — stub."""
    return jsonify({"ok": True, "status": "not_configured", "flows": []})


@energy_forecast_bp.route("/sankey.svg", methods=["GET"])
@require_token
def energy_sankey_svg():
    """Energy Sankey SVG — stub."""
    from flask import Response
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><text x="50" y="100" fill="#888">Energie-Sankey nicht konfiguriert</text></svg>'
    return Response(svg, mimetype="image/svg+xml")


@energy_forecast_bp.route("/reports/generate", methods=["GET"])
@require_token
def energy_reports_generate():
    """Generate an actionable energy report with savings tracking."""
    try:
        engine = _get_optimization_engine()
        period_hours = min(int(request.args.get("hours", 24)), 24 * 30)
        report = engine.get_report(
            zone_id=request.args.get("zone_id"),
            period_hours=period_hours,
            budget_eur=_get_budget_value("budget_eur", "monthly_budget_eur", "daily_budget_eur"),
        )
        return jsonify({"ok": True, "report": report})
    except Exception as e:
        _LOGGER.error("Energy report error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@energy_forecast_bp.route("/demand-response/status", methods=["GET"])
@require_token
def energy_demand_response_status():
    """Demand response status — stub."""
    return jsonify({
        "ok": True,
        "status": "not_configured",
        "active": False,
        "events": [],
    })


# Import für asdict
from dataclasses import asdict
