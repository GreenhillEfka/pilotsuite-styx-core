from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

mock_security = MagicMock()
mock_security.require_token = lambda f: f
sys.modules["copilot_core.api.security"] = mock_security

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1 import energy_forecast as ef
from copilot_core.energy.report_generator import EnergyReportGenerator


class _FakePatternLearner:
    def __init__(self) -> None:
        self.calls: list[tuple[float, datetime, datetime]] = []

    def get_pattern_summaries(self, *, min_confidence: float, window_start: datetime, window_end: datetime):
        return self.get_pattern_window_summaries(
            min_confidence=min_confidence,
            window_start=window_start,
            window_end=window_end,
        )

    def get_pattern_window_summaries(self, *, min_confidence: float, window_start: datetime, window_end: datetime):
        self.calls.append((min_confidence, window_start, window_end))
        current_start = datetime(2026, 4, 15, 0, 0, tzinfo=timezone.utc)
        if window_start == current_start:
            return [
                {
                    "pattern_id": "pattern_001",
                    "category": "climate",
                    "zone": "wohnzimmer",
                    "occurrence_count": 4,
                    "confidence": 0.84,
                    "last_occurrence": "2026-04-17T08:30:00+00:00",
                    "estimated_energy_impact_kwh": 2.5,
                    "estimated_cost_impact_eur": 0.0,
                    "window_metrics_source": "observations",
                },
                {
                    "pattern_id": "pattern_002",
                    "category": "media",
                    "zone": "buero",
                    "occurrence_count": 1,
                    "confidence": 0.63,
                    "last_occurrence": "2026-04-17T20:15:00+00:00",
                    "estimated_energy_impact_kwh": 0.0,
                    "estimated_cost_impact_eur": 1.2,
                    "window_metrics_source": "observations",
                },
            ]

        return [
            {
                "pattern_id": "pattern_001",
                "category": "climate",
                "zone": "wohnzimmer",
                "occurrence_count": 2,
                "confidence": 0.84,
                "last_occurrence": "2026-04-14T08:30:00+00:00",
                "estimated_energy_impact_kwh": 2.0,
                "estimated_cost_impact_eur": 0.0,
                "window_metrics_source": "observations",
            }
        ]


def _make_app(pattern_learner: _FakePatternLearner) -> Flask:
    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {"pattern_learner": pattern_learner}
    app.register_blueprint(ef.energy_forecast_bp)
    return app


def test_usage_pattern_export_route_returns_canonical_report_payload():
    learner = _FakePatternLearner()
    app = _make_app(learner)
    client = app.test_client()

    response = client.get(
        "/api/v1/energy/reports/usage-patterns/export"
        "?window_start=2026-04-15T00:00:00Z"
        "&window_end=2026-04-18T00:00:00Z"
        "&min_confidence=0.5"
    )

    assert response.status_code == 200, response.get_data(as_text=True)

    expected = EnergyReportGenerator().export_usage_pattern_summary(
        learner,
        window_start=datetime(2026, 4, 15, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc),
        min_confidence=0.5,
    )

    assert response.get_json() == expected
    assert learner.calls[:2] == [
        (
            0.5,
            datetime(2026, 4, 15, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc),
        ),
        (
            0.5,
            datetime(2026, 4, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 15, 0, 0, tzinfo=timezone.utc),
        ),
    ]


def test_usage_pattern_export_route_rejects_invalid_min_confidence():
    learner = _FakePatternLearner()
    app = _make_app(learner)
    client = app.test_client()

    response = client.get(
        "/api/v1/energy/reports/usage-patterns/export?min_confidence=not-a-number"
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Query parameter 'min_confidence' must be a float between 0.0 and 1.0"
    }
