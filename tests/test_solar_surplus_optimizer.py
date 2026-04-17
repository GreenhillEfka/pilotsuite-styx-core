"""Deterministic policy-kernel tests for the solar surplus optimizer."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

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
        from datetime import datetime, timezone

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

    def test_optimizer_module_stays_runtime_pure(self):
        import copilot_core.energy.solar_surplus_optimizer as module

        source = inspect.getsource(module)
        assert "homeassistant" not in source.lower()
        assert "from homeassistant" not in source.lower()
