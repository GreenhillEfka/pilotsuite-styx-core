"""Deterministic policy-kernel tests for the solar surplus optimizer."""
from __future__ import annotations

import inspect
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.energy.forecast import ForecastDataPoint  # noqa: E402
from copilot_core.energy.load_shifting import ShiftableDevice  # noqa: E402
from copilot_core.energy.pv_prediction import PVHourlyForecast  # noqa: E402
from copilot_core.energy.solar_surplus_optimizer import (  # noqa: E402
    SolarSurplusCandidate,
    SolarSurplusOptimizer,
    SolarSurplusSlot,
)


class TestSolarSurplusOptimizer:
    def test_recommendations_are_deterministic_for_fixed_input(self):
        optimizer = SolarSurplusOptimizer()
        slots = [
            SolarSurplusSlot(
                timestamp="2026-04-17T10:00:00Z",
                window_hours=1.0,
                available_surplus_kwh=0.6,
                expected_import_price_ct_kwh=22.0,
                confidence=0.60,
            ),
            SolarSurplusSlot(
                timestamp="2026-04-17T12:00:00Z",
                window_hours=2.5,
                available_surplus_kwh=1.8,
                expected_import_price_ct_kwh=37.0,
                confidence=0.95,
            ),
            SolarSurplusSlot(
                timestamp="2026-04-17T14:00:00Z",
                window_hours=2.0,
                available_surplus_kwh=1.1,
                expected_import_price_ct_kwh=28.0,
                confidence=0.70,
            ),
        ]
        candidates = [
            SolarSurplusCandidate(
                device_id="dishwasher-1",
                device_name="Dishwasher",
                energy_kwh=1.5,
                duration_hours=2.0,
                earliest_start="2026-04-17T10:00:00Z",
                latest_start="2026-04-17T15:00:00Z",
                priority=2,
            ),
            SolarSurplusCandidate(
                device_id="dryer-1",
                device_name="Dryer",
                energy_kwh=2.2,
                duration_hours=2.0,
                earliest_start="2026-04-17T06:00:00Z",
                latest_start="2026-04-17T08:00:00Z",
                priority=3,
            ),
        ]

        from datetime import datetime, timezone

        actions, summary = optimizer.recommend(
            slots,
            candidates,
            now=datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc),
        )

        dishwasher, dryer = actions
        assert dishwasher.action == "schedule_at"
        assert dishwasher.recommended_start == "2026-04-17T12:00:00Z"
        assert dishwasher.expected_grid_relief_kwh == 1.5
        assert dishwasher.expected_self_consumption_gain_pct == 100.0
        assert dishwasher.expected_savings_eur == 0.43
        assert dryer.action == "do_not_shift"
        assert summary.recommendations_count == 1
        assert summary.expected_grid_relief_kwh == 1.5
        assert summary.expected_savings_eur == 0.43
        assert summary.expected_self_consumption_gain_pct == 40.54

    def test_schedule_now_when_best_slot_is_immediate(self):
        optimizer = SolarSurplusOptimizer(schedule_now_window_minutes=45)
        slots = [
            SolarSurplusSlot(
                timestamp="2026-04-17T10:15:00Z",
                window_hours=1.5,
                available_surplus_kwh=0.9,
                expected_import_price_ct_kwh=31.0,
                confidence=0.9,
            )
        ]
        candidates = [
            SolarSurplusCandidate(
                device_id="washer-1",
                device_name="Washer",
                energy_kwh=0.8,
                duration_hours=1.0,
                earliest_start="2026-04-17T10:00:00Z",
                latest_start="2026-04-17T11:00:00Z",
                priority=1,
            )
        ]

        actions, _summary = optimizer.recommend(
            slots,
            candidates,
            now=datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc),
        )

        assert actions[0].action == "schedule_now"
        assert actions[0].recommended_start == "2026-04-17T10:15:00Z"

    def test_slot_adapter_trims_mismatched_forecasts_to_shared_horizon(self):
        start = datetime(2026, 4, 17, 0, 0, tzinfo=timezone.utc)
        pv_forecast = [
            PVHourlyForecast(
                timestamp=(start + timedelta(hours=hour)).isoformat(),
                hour=hour % 24,
                solar_elevation=35.0,
                solar_azimuth=180.0,
                clearsky_irradiance_wm2=550.0,
                actual_irradiance_wm2=500.0,
                pv_power_kw=2.0,
                pv_energy_wh=2000.0,
                cloud_cover_pct=15,
                weather_condition="clear",
                efficiency_factor=0.9,
            )
            for hour in range(48)
        ]
        load_forecast = [
            ForecastDataPoint(
                timestamp=(start + timedelta(hours=hour)).isoformat(),
                hour=hour % 24,
                predicted_consumption_kw=0.6,
                predicted_consumption_kwh=0.6,
                confidence=0.82,
                base_load_kw=0.3,
                variable_load_kw=0.3,
                weather_adjustment=0.0,
                day_type="weekday",
            )
            for hour in range(24)
        ]
        price_forecast = [
            {
                "timestamp": (start + timedelta(hours=hour)).isoformat(),
                "price_ct_kwh": 24.0 + hour,
            }
            for hour in range(36)
        ]

        slots = SolarSurplusSlot.from_forecasts(
            pv_forecast,
            load_forecast=load_forecast,
            price_forecast=price_forecast,
        )

        assert len(slots) == 24
        assert slots[0].timestamp == "2026-04-17T00:00:00Z"
        assert slots[-1].timestamp == "2026-04-17T23:00:00Z"
        assert slots[0].available_surplus_kwh == 1.4
        assert slots[-1].expected_import_price_ct_kwh == 47.0
        assert slots[0].confidence == 0.82

    def test_slot_adapter_handles_missing_fields_with_safe_defaults(self):
        slots = SolarSurplusSlot.from_forecasts(
            [{"timestamp": "2026-04-17T12:00:00Z", "pv_power_kw": 1.8}],
            load_forecast=[{"timestamp": "2026-04-17T12:00:00Z", "predicted_consumption_kw": 0.5}],
            price_forecast=[{"timestamp": "2026-04-17T12:00:00Z"}],
        )

        assert len(slots) == 1
        assert slots[0].window_hours == 1.0
        assert slots[0].available_surplus_kwh == 1.3
        assert slots[0].expected_import_price_ct_kwh == 30.0
        assert slots[0].expected_export_price_ct_kwh == 8.0
        assert slots[0].confidence == 1.0

    def test_candidate_adapter_normalizes_shiftable_profiles_and_filters_non_idle(self):
        reference_time = datetime(2026, 4, 17, 10, 15, tzinfo=timezone.utc)
        idle_device = ShiftableDevice(
            device_id="ev-1",
            device_type="ev_charger",
            name="",
            power_kw=3.5,
            energy_kwh=0.0,
            duration_hours=0.0,
            flexibility_hours=6,
            priority=0,
            min_start_hour=11,
            max_start_hour=18,
            must_complete_by="2026-04-17T15:00:00Z",
            current_state="idle",
            cost_per_kwh=30.0,
        )
        running_device = {
            "device_id": "washer-2",
            "device_type": "washer",
            "name": "Washer 2",
            "current_state": "running",
        }

        candidates = SolarSurplusCandidate.from_shiftable_devices(
            [idle_device, running_device],
            reference_time=reference_time,
        )

        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.device_id == "ev-1"
        assert candidate.device_name == "ev-1"
        assert candidate.energy_kwh == 3.5
        assert candidate.duration_hours == 1.0
        assert candidate.earliest_start == "2026-04-17T11:00:00Z"
        assert candidate.latest_start == "2026-04-17T14:00:00Z"
        assert candidate.priority == 1
        assert candidate.interruptible is False

    def test_reporting_surface_returns_normalized_recommendation_batch_shape(self):
        optimizer = SolarSurplusOptimizer(schedule_now_window_minutes=10)
        reference_time = datetime(2026, 4, 17, 9, 5, tzinfo=timezone.utc)
        start = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)

        pv_forecast = [
            PVHourlyForecast(
                timestamp=(start + timedelta(hours=hour)).isoformat(),
                hour=(10 + hour) % 24,
                solar_elevation=45.0,
                solar_azimuth=180.0,
                clearsky_irradiance_wm2=650.0,
                actual_irradiance_wm2=610.0,
                pv_power_kw=2.4 + hour * 0.2,
                pv_energy_wh=2400.0 + hour * 200.0,
                cloud_cover_pct=10,
                weather_condition="clear",
                efficiency_factor=0.92,
            )
            for hour in range(3)
        ]
        load_forecast = [
            ForecastDataPoint(
                timestamp=(start + timedelta(hours=hour)).isoformat(),
                hour=(10 + hour) % 24,
                predicted_consumption_kw=0.5,
                predicted_consumption_kwh=0.5,
                confidence=0.88,
                base_load_kw=0.3,
                variable_load_kw=0.2,
                weather_adjustment=0.0,
                day_type="weekday",
            )
            for hour in range(3)
        ]
        price_forecast = [
            {
                "timestamp": (start + timedelta(hours=hour)).isoformat(),
                "price_ct_kwh": 26.0 + hour * 3,
                "export_price_ct_kwh": 8.0,
            }
            for hour in range(3)
        ]
        shiftable_devices = [
            ShiftableDevice(
                device_id="dishwasher-1",
                device_type="dishwasher",
                name="Dishwasher",
                power_kw=1.2,
                energy_kwh=1.2,
                duration_hours=1.0,
                flexibility_hours=6,
                priority=2,
                min_start_hour=10,
                max_start_hour=14,
                must_complete_by="2026-04-17T15:00:00Z",
                current_state="idle",
                cost_per_kwh=29.0,
            )
        ]

        batch = optimizer.get_recommendations_as_dict(
            pv_forecast=pv_forecast,
            load_forecast=load_forecast,
            price_forecast=price_forecast,
            shiftable_devices=shiftable_devices,
            reference_time=reference_time,
            now=reference_time,
        )

        assert set(batch) == {"generated_at", "summary", "recommendations", "slots", "candidates"}
        assert batch["generated_at"] == "2026-04-17T09:05:00Z"

        assert batch["summary"]["generated_at"] == batch["generated_at"]
        assert batch["summary"]["horizon_hours"] == 3
        assert batch["summary"]["total_slots"] == 3
        assert batch["summary"]["total_candidates"] == 1
        assert batch["summary"]["recommendations_count"] == 1

        assert len(batch["slots"]) == 3
        assert batch["slots"][0]["timestamp"] == "2026-04-17T10:00:00Z"
        assert batch["slots"][0]["available_surplus_kwh"] == 1.9

        assert len(batch["candidates"]) == 1
        assert batch["candidates"][0]["device_id"] == "dishwasher-1"
        assert batch["candidates"][0]["earliest_start"] == "2026-04-17T10:00:00Z"

        assert len(batch["recommendations"]) == 1
        recommendation = batch["recommendations"][0]
        assert set(recommendation) == {
            "device_id",
            "device_name",
            "action",
            "recommended_start",
            "reason",
            "confidence",
            "expected_self_consumption_gain_pct",
            "expected_savings_eur",
            "expected_grid_relief_kwh",
            "slot_timestamp",
            "score",
        }
        assert recommendation["device_id"] == "dishwasher-1"
        assert recommendation["action"] == "schedule_at"
        assert recommendation["recommended_start"] == "2026-04-17T12:00:00Z"
        assert recommendation["slot_timestamp"] == recommendation["recommended_start"]
        assert recommendation["expected_grid_relief_kwh"] == 1.2

    def test_optimizer_module_stays_runtime_pure(self):
        import copilot_core.energy.solar_surplus_optimizer as module

        source = inspect.getsource(module)
        assert "homeassistant" not in source.lower()
        assert "from homeassistant" not in source.lower()
