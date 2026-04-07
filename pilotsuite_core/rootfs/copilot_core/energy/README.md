# Energy Forecasting Module — v12.6.0

## Overview

This module provides comprehensive energy forecasting and optimization capabilities for the PilotSuite Styx Core system.

## Components

### 1. EnergyForecastEngine (`forecast.py`)

**Purpose:** 24h/7d Energieverbrauchs-Prognose

**Features:**
- Hourly and daily consumption forecasting
- Weather impact integration (temperature sensitivity)
- Day type detection (weekday/weekend)
- Historical data learning
- Confidence scoring

**Usage:**
```python
from copilot_core.energy.forecast import EnergyForecastEngine

engine = EnergyForecastEngine(
    base_load_kw=0.3,
    latitude=52.52,
    longitude=13.405,
)

# Generate 48h forecast
forecast = engine.generate_hourly_forecast(hours=48)

# With weather data
weather_data = [{"temperature_c": 15.0} for _ in range(48)]
forecast = engine.generate_hourly_forecast(hours=48, weather_data=weather_data)

# Get summary
summary = engine.generate_summary(forecast)
```

### 2. PVPredictionEngine (`pv_prediction.py`)

**Purpose:** PV-Ertragsprognose (Wetter-basiert)

**Features:**
- Solar position calculations (elevation, azimuth)
- Clearsky irradiance modeling
- Weather impact (cloud cover, precipitation)
- Panel orientation optimization (azimuth, tilt)
- Sunrise/sunset calculations
- Daily and hourly forecasts

**Usage:**
```python
from copilot_core.energy.pv_prediction import PVPredictionEngine

engine = PVPredictionEngine(
    latitude=52.52,
    longitude=13.405,
    pv_peak_kw=10.0,
    panel_azimuth=180.0,  # South
    panel_tilt=30.0,
)

# Set weather data
weather_data = [
    {
        "timestamp": "2024-01-01T00:00:00",
        "temperature_c": 15.0,
        "cloud_cover_pct": 50,
        "precipitation_mm": 0,
        "weather_code": 0,
    }
    for _ in range(48)
]
engine.set_weather_data(weather_data)

# Generate forecast
forecast = engine.generate_hourly_forecast(hours=48)
```

### 3. LoadShiftingEngine (`load_shifting.py`)

**Purpose:** Load Shifting Empfehlungen

**Features:**
- Device flexibility modeling
- Price-based optimization
- PV self-consumption optimization
- CO2 intensity consideration
- Recommendation generation with savings calculation
- Optimization window detection

**Usage:**
```python
from copilot_core.energy.load_shifting import LoadShiftingEngine

engine = LoadShiftingEngine()

# Add devices
engine.add_device_from_profile("washer_1", "washer", "Waschmaschine")
engine.add_device_from_profile("ev_1", "ev_charger", "EV-Ladestation")

# Set forecasts
engine.set_pv_forecast(pv_forecast)
engine.set_price_forecast(price_forecast)

# Get recommendations
recommendations = engine.generate_recommendations()

# Get optimization windows
windows = engine.generate_optimization_windows(hours_ahead=24)

# Simple text recommendation
text = engine.get_simple_recommendation_text()
# "💡 Waschmaschine um 14:00 starten — PV-Spitze nutzen (85%)!"
```

### 4. API Endpoints (`api/v1/energy_forecast.py`)

**Endpoints:**

#### GET `/api/v1/energy/forecast/consumption`
Verbrauchsprognose

**Params:**
- `hours`: Prognosehorizont (default 48, max 168)
- `include_weather`: Wettereinfluss (default true)

#### GET `/api/v1/energy/forecast/pv`
PV-Ertragsprognose

**Params:**
- `hours`: Prognosehorizont (default 48)
- `peak_kw`: PV-Leistung (optional)
- `azimuth`: Panel-Ausrichtung (optional)
- `tilt`: Panel-Neigung (optional)

#### GET `/api/v1/energy/forecast/combined`
Kombinierte Prognose (Verbrauch + PV + Preise)

**Params:**
- `hours`: Prognosehorizont (default 48)
- `include_load_shifting`: Empfehlungen (default true)

**Returns:**
- Consumption forecast
- PV forecast
- Hourly balance (PV - Consumption)
- Load shifting recommendations

#### GET `/api/v1/energy/load-shifting/recommendations`
Load Shifting Empfehlungen

**Params:**
- `hours`: Betrachtungshorizont (default 24)

#### GET `/api/v1/energy/load-shifting/windows`
Optimale Zeitfenster

**Params:**
- `hours`: Horizont (default 24)

**Returns:**
Top 4 optimization windows with:
- Start/end time
- Average price
- Average PV power
- Recommendation text

#### POST `/api/v1/energy/load-shifting/devices`
Registriere verschiebbares Gerät

**Body:**
```json
{
  "device_id": "washer_1",
  "device_type": "washer",
  "name": "Waschmaschine",
  "power_kw": 2.0,
  "energy_kwh": 1.5,
  "duration_hours": 1.5,
  "flexibility_hours": 8,
  "priority": 3
}
```

#### GET `/api/v1/energy/summary`
Kompakte Dashboard-Übersicht

**Returns:**
- Current consumption/PV/balance
- Today's totals
- Next 24h recommendations

## Integration

### Weather Service Integration

The module integrates with the weather service for:
- Temperature data (consumption heating/cooling)
- Cloud cover (PV reduction)
- Precipitation (PV reduction)
- Weather codes (fog, rain, snow impacts)

### Price Forecast Integration

Supports dynamic electricity prices:
- Hourly price forecasts
- Time-of-use pricing
- Spot market prices

### Energy Service Integration

Uses energy service for:
- Location data
- Historical consumption
- Real-time measurements

## Testing

Run tests with:
```bash
cd /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app
pytest tests/test_energy_forecast_new.py -v
```

**Test Coverage:**
- EnergyForecastEngine: 16 tests
- PVPredictionEngine: 13 tests
- LoadShiftingEngine: 13 tests
- Integration tests: 3 tests

**Total:** 45 tests

## Example Output

### Consumption Forecast
```json
{
  "generated_at": "2024-01-01T12:00:00",
  "forecast_horizon_hours": 48,
  "summary": {
    "total_predicted_consumption_kwh": 45.6,
    "avg_hourly_consumption_kw": 0.95,
    "peak_consumption_kw": 1.8,
    "base_load_percentage": 31.5
  },
  "hourly_forecast": [...]
}
```

### PV Forecast
```json
{
  "pv_system": {
    "peak_kw": 10.0,
    "azimuth": 180.0,
    "tilt": 30.0
  },
  "summary": {
    "total_energy_kwh": 42.5,
    "peak_power_kw": 8.2,
    "peak_time": "2024-01-01T13:00:00",
    "weather_impact_pct": 15.3
  }
}
```

### Load Shifting Recommendation
```json
{
  "recommendation_id": "rec_washer_1_1704110400",
  "device_name": "Waschmaschine",
  "action": "schedule",
  "recommended_start": "2024-01-01T14:00:00",
  "savings_eur": 0.45,
  "savings_pct": 35.2,
  "pv_utilization_pct": 85.0,
  "reason": "Maximale PV-Nutzung (85%) während der Laufzeit"
}
```

## Performance

- Forecast generation: < 100ms for 48h
- Memory footprint: < 10MB
- No external API dependencies (calculations are local)
- Thread-safe operations

## Future Enhancements

- [ ] Machine learning for consumption patterns
- [ ] Real-time price API integration
- [ ] Battery storage optimization
- [ ] Multi-home support
- [ ] Historical accuracy tracking
- [ ] Automated device scheduling

## Version

**v12.6.0** — Initial release with:
- Energy consumption forecasting
- PV production forecasting
- Load shifting recommendations
- REST API endpoints
- Comprehensive test suite
