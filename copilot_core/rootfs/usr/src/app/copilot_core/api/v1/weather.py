"""Weather API — PilotSuite Core.

This API provides a **stable**, HA-integration-friendly schema for weather context
and a light health probe for the Core dashboard module pipeline.

Important:
- Core runs as an add-on, not inside HA's Python runtime.
- Therefore we fetch data via Supervisor proxy: http://supervisor/core/api/*
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import requests
from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

weather_bp = Blueprint("weather", __name__, url_prefix="/api/v1/weather")
bp = weather_bp

_SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api").rstrip("/")

# Cache snapshot/forecast so the dashboard can poll without overloading HA.
_CACHE_TTL_S = 300
_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"ts": 0.0, "snapshot": None, "forecast": None, "last_error": None}


def _get_token() -> str:
    return (
        os.environ.get("SUPERVISOR_TOKEN", "").strip()
        or os.environ.get("HOME_ASSISTANT_TOKEN", "").strip()
        or os.environ.get("HA_TOKEN", "").strip()
    )


def _ha_headers() -> dict[str, str] | None:
    token = _get_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _ha_get(path: str, *, params: dict[str, Any] | None = None, timeout: int = 12) -> Any:
    headers = _ha_headers()
    if not headers:
        raise RuntimeError("No HA token (SUPERVISOR_TOKEN) available")
    url = f"{_SUPERVISOR_API}{path}"
    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    if not resp.ok:
        raise RuntimeError(f"HA GET {path} failed (HTTP {resp.status_code})")
    return resp.json()


def _first_weather_state() -> dict[str, Any] | None:
    states = _ha_get("/states", timeout=15)
    if not isinstance(states, list):
        return None
    for st in states:
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id", "") or "")
        if eid.startswith("weather."):
            return st
    return None


def _sun_times() -> tuple[str, str]:
    """Return (sunrise_iso, sunset_iso) best-effort."""
    try:
        sun = _ha_get("/states/sun.sun", timeout=8)
        if not isinstance(sun, dict):
            return "", ""
        attrs = sun.get("attributes") or {}
        if not isinstance(attrs, dict):
            return "", ""
        return str(attrs.get("next_rising") or ""), str(attrs.get("next_setting") or "")
    except Exception:  # noqa: BLE001
        return "", ""


def _ha_location() -> tuple[float, float] | None:
    """Return (lat, lon) from HA /config if available."""
    try:
        cfg = _ha_get("/config", timeout=10)
        if not isinstance(cfg, dict):
            return None
        lat = cfg.get("latitude")
        lon = cfg.get("longitude")
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)
    except Exception:  # noqa: BLE001
        return None


def _open_meteo_condition(code: int) -> str:
    # https://open-meteo.com/en/docs (weathercode mapping)
    if code == 0:
        return "sunny"
    if code in (1, 2):
        return "partly_cloudy"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "foggy"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rainy"
    if code in (71, 73, 75, 77, 85, 86):
        return "snowy"
    if code in (95, 96, 99):
        return "stormy"
    return "unknown"


def _open_meteo_fetch(lat: float, lon: float, *, days: int = 5) -> dict[str, Any] | None:
    """Fetch a compact snapshot + forecast via Open‑Meteo (no API key).

    Returns a dict with keys:
      snapshot: WeatherSnapshot-like dict
      forecast: list[dict] of WeatherForecast-like items
      ui: dict for Haushalt dashboard
    """
    try:
        # Use a very conservative parameter set to stay compatible.
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true",
            "hourly": "relativehumidity_2m,cloudcover,uv_index",
            "daily": "sunrise,sunset,weathercode,temperature_2m_max,temperature_2m_min",
            "forecast_days": max(1, min(int(days), 7)),
            "timezone": "auto",
        }
        resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=12)
        if not resp.ok:
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None

        current = data.get("current_weather") or {}
        hourly = data.get("hourly") or {}
        daily = data.get("daily") or {}

        cur_time = str(current.get("time") or "")
        code = int(current.get("weathercode") or -1)
        condition = _open_meteo_condition(code)

        # Resolve hourly index matching current time (best effort).
        humidity = 0.0
        cloud = 0.0
        uv = 0.0
        try:
            times = hourly.get("time") or []
            if isinstance(times, list) and cur_time and cur_time in times:
                idx = times.index(cur_time)
                rh = (hourly.get("relativehumidity_2m") or [])
                cc = (hourly.get("cloudcover") or [])
                uvv = (hourly.get("uv_index") or [])
                if isinstance(rh, list) and idx < len(rh):
                    humidity = _safe_float(rh[idx], 0.0)
                if isinstance(cc, list) and idx < len(cc):
                    cloud = _safe_float(cc[idx], 0.0)
                if isinstance(uvv, list) and idx < len(uvv):
                    uv = _safe_float(uvv[idx], 0.0)
        except Exception:  # noqa: BLE001
            pass

        sunrise = ""
        sunset = ""
        try:
            sr = daily.get("sunrise") or []
            ss = daily.get("sunset") or []
            if isinstance(sr, list) and sr:
                sunrise = str(sr[0] or "")
            if isinstance(ss, list) and ss:
                sunset = str(ss[0] or "")
        except Exception:  # noqa: BLE001
            pass

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "condition": condition,
            "temperature_c": _safe_float(current.get("temperature"), 0.0),
            "humidity_percent": humidity,
            "cloud_cover_percent": cloud,
            "uv_index": uv,
            "sunrise": sunrise,
            "sunset": sunset,
            "forecast_pv_production_kwh": 0.0,
            "recommendation": "moderate_usage",
            "provider": "open-meteo",
            # extra (dashboard use)
            "wind_speed": _safe_float(current.get("windspeed"), 0.0),
        }

        forecast_items: list[dict[str, Any]] = []
        try:
            tmax = daily.get("temperature_2m_max") or []
            tmin = daily.get("temperature_2m_min") or []
            wcode = daily.get("weathercode") or []
            dtime = daily.get("time") or []
            for i in range(min(len(dtime), len(tmax), len(tmin), len(wcode), max(1, days))):
                cond = _open_meteo_condition(int(wcode[i] or -1))
                ccloud = 0.0
                pv_factor = 0.5
                if ccloud > 0:
                    pv_factor = max(0.0, min(1.0, 1.0 - (ccloud / 100.0)))
                forecast_items.append(
                    {
                        "timestamp": str(dtime[i] or ""),
                        "condition": cond,
                        "temperature_high_c": _safe_float(tmax[i], 0.0),
                        "temperature_low_c": _safe_float(tmin[i], 0.0),
                        "cloud_cover_percent": ccloud,
                        "precipitation_probability": 0.0,
                        "pv_production_factor": pv_factor,
                    }
                )
        except Exception:  # noqa: BLE001
            forecast_items = []

        ui = {
            "entity_id": "open_meteo",
            "friendly_name": "Open‑Meteo",
            "state": condition,
            "temperature": snapshot.get("temperature_c"),
            "humidity": snapshot.get("humidity_percent"),
            "wind_speed": snapshot.get("wind_speed"),
            "forecast": [
                {
                    "date": item.get("timestamp"),
                    "condition": item.get("condition"),
                    "temperature": item.get("temperature_high_c"),
                }
                for item in forecast_items[:5]
            ],
        }

        return {"snapshot": snapshot, "forecast": forecast_items, "ui": ui}
    except Exception:  # noqa: BLE001
        return None

def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _build_snapshot() -> dict[str, Any]:
    """Build WeatherSnapshot payload expected by the HA integration."""
    now = datetime.now(timezone.utc).isoformat()
    sunrise, sunset = _sun_times()

    st = _first_weather_state()
    if not st:
        loc = _ha_location()
        if loc:
            om = _open_meteo_fetch(loc[0], loc[1], days=5)
            if om and isinstance(om.get("snapshot"), dict):
                return om["snapshot"]
        return {
            "timestamp": now,
            "condition": "unknown",
            "temperature_c": 0.0,
            "humidity_percent": 0.0,
            "cloud_cover_percent": 0.0,
            "uv_index": 0.0,
            "sunrise": sunrise,
            "sunset": sunset,
            "forecast_pv_production_kwh": 0.0,
            "recommendation": "moderate_usage",
            "provider": "none",
        }

    attrs = st.get("attributes") or {}
    if not isinstance(attrs, dict):
        attrs = {}

    cloud = (
        attrs.get("cloud_coverage")
        or attrs.get("cloud_cover")
        or attrs.get("cloudcover")
        or attrs.get("cloudiness")
    )
    uv = attrs.get("uv_index") or attrs.get("uv")

    return {
        "timestamp": now,
        "condition": str(st.get("state") or "unknown"),
        "temperature_c": _safe_float(attrs.get("temperature"), 0.0),
        "humidity_percent": _safe_float(attrs.get("humidity"), 0.0),
        "cloud_cover_percent": _safe_float(cloud, 0.0),
        "uv_index": _safe_float(uv, 0.0),
        "sunrise": sunrise,
        "sunset": sunset,
        "forecast_pv_production_kwh": 0.0,
        "recommendation": "moderate_usage",
        "provider": str(st.get("entity_id") or "weather_entity"),
    }


def _build_forecast(days: int = 3) -> dict[str, Any]:
    st = _first_weather_state()
    if not st:
        loc = _ha_location()
        if loc:
            om = _open_meteo_fetch(loc[0], loc[1], days=max(1, days))
            if om and isinstance(om.get("forecast"), list):
                return {"forecast": om["forecast"][: max(1, min(days, 7))]}
        return {"forecast": []}

    attrs = st.get("attributes") or {}
    if not isinstance(attrs, dict):
        attrs = {}
    raw_fc = attrs.get("forecast") or []
    if not isinstance(raw_fc, list):
        raw_fc = []

    out: list[dict[str, Any]] = []
    for item in raw_fc[: max(0, min(days * 2, 10))]:
        if not isinstance(item, dict):
            continue
        # HA forecast items vary; normalize a conservative schema.
        ts = str(item.get("datetime") or item.get("time") or item.get("date") or "")
        cond = str(item.get("condition") or item.get("state") or "unknown")
        temp_hi = item.get("temperature")
        temp_lo = item.get("templow") or item.get("temperature_low")
        cloud = item.get("cloud_coverage") or item.get("cloud_cover") or item.get("cloudiness")
        precip = item.get("precipitation_probability") or item.get("precip_probability") or item.get("precipitation")
        cloud_f = _safe_float(cloud, 0.0)
        pv_factor = 0.5
        if cloud_f > 0:
            pv_factor = max(0.0, min(1.0, 1.0 - (cloud_f / 100.0)))
        out.append(
            {
                "timestamp": ts,
                "condition": cond,
                "temperature_high_c": _safe_float(temp_hi, 0.0),
                "temperature_low_c": _safe_float(temp_lo, 0.0),
                "cloud_cover_percent": cloud_f,
                "precipitation_probability": _safe_float(precip, 0.0),
                "pv_production_factor": pv_factor,
            }
        )

    return {"forecast": out}


def _cached(key: str) -> dict[str, Any] | None:
    with _cache_lock:
        ts = float(_cache.get("ts", 0.0) or 0.0)
        if (time.time() - ts) < _CACHE_TTL_S:
            val = _cache.get(key)
            if isinstance(val, dict):
                return val
    return None


def _store_cache(snapshot: dict[str, Any], forecast: dict[str, Any]) -> None:
    with _cache_lock:
        _cache["ts"] = time.time()
        _cache["snapshot"] = snapshot
        _cache["forecast"] = forecast
        _cache["last_error"] = None


def get_weather_ui_snapshot() -> dict[str, Any]:
    """Return a compact weather dict for the Haushalt dashboard tab."""
    st = _first_weather_state()
    if st:
        attrs = st.get("attributes") or {}
        if not isinstance(attrs, dict):
            attrs = {}
        forecast = attrs.get("forecast") or []
        if not isinstance(forecast, list):
            forecast = []
        return {
            "entity_id": st.get("entity_id"),
            "friendly_name": attrs.get("friendly_name"),
            "state": st.get("state"),
            "temperature": attrs.get("temperature"),
            "humidity": attrs.get("humidity"),
            "wind_speed": attrs.get("wind_speed"),
            "forecast": forecast[:5],
        }

    loc = _ha_location()
    if loc:
        om = _open_meteo_fetch(loc[0], loc[1], days=5)
        if om and isinstance(om.get("ui"), dict):
            return om["ui"]
    return {}


@weather_bp.route("/health", methods=["GET"])
@require_token
def weather_health():
    try:
        snap = _cached("snapshot")
        if snap is None:
            snap = _build_snapshot()
            fc = _build_forecast(days=3)
            _store_cache(snap, fc)
        provider = str(snap.get("provider") or "unknown")
        status = "ok" if provider != "none" else "degraded"
        return jsonify({"ok": True, "status": status, "provider": provider})
    except Exception as exc:  # noqa: BLE001
        with _cache_lock:
            _cache["last_error"] = str(exc)
        return jsonify({"ok": False, "status": "error", "error": str(exc)}), 503


@weather_bp.route("", methods=["GET"])
@require_token
def weather_snapshot():
    """Return WeatherSnapshot schema used by HA integration's weather_context."""
    try:
        snap = _cached("snapshot")
        if snap is None:
            snap = _build_snapshot()
            fc = _build_forecast(days=3)
            _store_cache(snap, fc)
        return jsonify({"ok": True, "data": snap})
    except Exception as exc:  # noqa: BLE001
        with _cache_lock:
            _cache["last_error"] = str(exc)
        # Keep schema stable even on failure (HA integration falls back to last known).
        fallback = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "condition": "unknown",
            "temperature_c": 0.0,
            "humidity_percent": 0.0,
            "cloud_cover_percent": 0.0,
            "uv_index": 0.0,
            "sunrise": "",
            "sunset": "",
            "forecast_pv_production_kwh": 0.0,
            "recommendation": "moderate_usage",
            "provider": "error",
        }
        return jsonify({"ok": False, "error": str(exc), "data": fallback}), 503


@weather_bp.route("/forecast", methods=["GET"])
@require_token
def weather_forecast():
    days = int(request.args.get("days", "3") or 3)
    days = max(1, min(days, 7))
    try:
        cached_fc = _cached("forecast")
        if cached_fc is not None:
            return jsonify({"ok": True, "data": cached_fc})
        fc = _build_forecast(days=days)
        snap = _build_snapshot()
        _store_cache(snap, fc)
        return jsonify({"ok": True, "data": fc})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc), "data": {"forecast": []}}), 503


@weather_bp.route("/pv-recommendations", methods=["GET"])
@require_token
def weather_pv_recommendations():
    # Placeholder for PV/energy integration.
    return jsonify({"ok": True, "data": {"recommendations": []}})
