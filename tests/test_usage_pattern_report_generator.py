from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.automation.pattern_learner import Pattern, PatternLearner  # noqa: E402
from copilot_core.energy.report_generator import EnergyReportGenerator  # noqa: E402


def test_pattern_learner_exposes_bounded_summary_adapter(tmp_path):
    learner = PatternLearner(data_dir=str(tmp_path / "patterns"))
    learner.patterns = {
        "pattern_001": Pattern(
            pattern_id="pattern_001",
            pattern_type="weather_based",
            entity_id="climate.wohnzimmer",
            action="set_temperature",
            occurrence_count=7,
            confidence=0.84,
            first_occurrence=datetime(2026, 4, 14, 8, 0, 0),
            last_occurrence=datetime(2026, 4, 17, 8, 30, 0),
            metadata={
                "zone": "wohnzimmer",
                "estimated_energy_impact_kwh": 4.0,
            },
        ),
        "pattern_002": Pattern(
            pattern_id="pattern_002",
            pattern_type="time_based",
            entity_id="media_player.kueche",
            action="turn_on",
            occurrence_count=2,
            confidence=0.41,
            first_occurrence=datetime(2026, 4, 10, 19, 0, 0),
            last_occurrence=datetime(2026, 4, 10, 19, 5, 0),
            metadata={"zone_name": "kueche"},
        ),
    }

    summaries = learner.get_pattern_summaries(
        min_confidence=0.5,
        window_start=datetime(2026, 4, 15, 0, 0, 0),
        window_end=datetime(2026, 4, 18, 0, 0, 0),
    )

    assert summaries == [
        {
            "pattern_id": "pattern_001",
            "pattern_type": "weather_based",
            "category": "climate",
            "entity_id": "climate.wohnzimmer",
            "action": "set_temperature",
            "zone": "wohnzimmer",
            "confidence": 0.84,
            "occurrence_count": 7,
            "last_occurrence": "2026-04-17T08:30:00",
            "hour_of_day": None,
            "day_of_week": None,
            "estimated_energy_impact_kwh": 4.0,
            "estimated_cost_impact_eur": 0.0,
        }
    ]


def test_energy_report_generator_builds_d1_usage_pattern_summary(tmp_path):
    learner = PatternLearner(data_dir=str(tmp_path / "patterns"))
    learner.patterns = {
        "pattern_001": Pattern(
            pattern_id="pattern_001",
            pattern_type="weather_based",
            entity_id="climate.wohnzimmer",
            action="set_temperature",
            occurrence_count=7,
            confidence=0.84,
            first_occurrence=datetime(2026, 4, 14, 8, 0, 0),
            last_occurrence=datetime(2026, 4, 17, 8, 30, 0),
            metadata={
                "zone": "wohnzimmer",
                "estimated_energy_impact_kwh": 4.0,
            },
        ),
        "pattern_003": Pattern(
            pattern_id="pattern_003",
            pattern_type="time_based",
            entity_id="media_player.buero",
            action="turn_on",
            occurrence_count=5,
            confidence=0.73,
            first_occurrence=datetime(2026, 4, 15, 18, 0, 0),
            last_occurrence=datetime(2026, 4, 17, 21, 15, 0),
            metadata={
                "zone_name": "buero",
                "estimated_cost_impact_eur": 2.5,
            },
        ),
    }

    generator = EnergyReportGenerator(grid_price_eur_kwh=0.31)
    report = generator.generate_usage_pattern_summary(
        learner,
        window_start=datetime(2026, 4, 15, 0, 0, 0),
        window_end=datetime(2026, 4, 18, 0, 0, 0),
        min_confidence=0.5,
    )

    assert report == {
        "status": "ok",
        "window": {
            "from": "2026-04-15T00:00:00",
            "to": "2026-04-18T00:00:00",
        },
        "comparison_window": {
            "from": "2026-04-12T00:00:00",
            "to": "2026-04-15T00:00:00",
        },
        "patterns": [
            {
                "pattern_id": "pattern_001",
                "category": "climate",
                "zone": "wohnzimmer",
                "frequency": 7,
                "previous_frequency": 0,
                "frequency_delta": 7,
                "confidence": 0.84,
                "last_seen": "2026-04-17T08:30:00",
                "trend": "stable",
            },
            {
                "pattern_id": "pattern_003",
                "category": "media",
                "zone": "buero",
                "frequency": 5,
                "previous_frequency": 0,
                "frequency_delta": 5,
                "confidence": 0.73,
                "last_seen": "2026-04-17T21:15:00",
                "trend": "stable",
            },
        ],
        "impact": {
            "estimated_cost_impact_eur": 3.74,
            "estimated_energy_impact_kwh": 4.0,
        },
        "drift": {
            "summary": {
                "new_patterns": 0,
                "fading_patterns": 0,
                "rising_patterns": 0,
                "stable_patterns": 0,
                "falling_patterns": 0,
            },
            "new_patterns": [],
            "fading_patterns": [],
        },
    }


def test_pattern_learner_exposes_windowed_pattern_summaries_from_observations(tmp_path):
    learner = PatternLearner(data_dir=str(tmp_path / "patterns"))
    learner.patterns = {
        "pattern_001": Pattern(
            pattern_id="pattern_001",
            pattern_type="weather_based",
            entity_id="climate.wohnzimmer",
            action="set_temperature",
            weather_condition="sunny",
            occurrence_count=9,
            confidence=0.84,
            first_occurrence=datetime(2026, 4, 12, 8, 0, 0),
            last_occurrence=datetime(2026, 4, 17, 8, 30, 0),
            metadata={
                "zone": "wohnzimmer",
                "estimated_energy_impact_kwh": 4.0,
            },
        ),
    }
    learner.observations = [
        {
            "timestamp": "2026-04-13T08:00:00",
            "entity_id": "climate.wohnzimmer",
            "action": "set_temperature",
            "context": {"weather_condition": "sunny"},
        },
        {
            "timestamp": "2026-04-16T08:00:00",
            "entity_id": "climate.wohnzimmer",
            "action": "set_temperature",
            "context": {"weather_condition": "sunny"},
        },
        {
            "timestamp": "2026-04-17T08:30:00",
            "entity_id": "climate.wohnzimmer",
            "action": "set_temperature",
            "context": {"weather_condition": "sunny"},
        },
    ]

    summaries = learner.get_pattern_window_summaries(
        min_confidence=0.5,
        window_start=datetime(2026, 4, 15, 0, 0, 0),
        window_end=datetime(2026, 4, 18, 0, 0, 0),
    )

    assert summaries == [
        {
            "pattern_id": "pattern_001",
            "pattern_type": "weather_based",
            "category": "climate",
            "entity_id": "climate.wohnzimmer",
            "action": "set_temperature",
            "zone": "wohnzimmer",
            "confidence": 0.84,
            "occurrence_count": 2,
            "last_occurrence": "2026-04-17T08:30:00",
            "hour_of_day": None,
            "day_of_week": None,
            "estimated_energy_impact_kwh": 4.0,
            "estimated_cost_impact_eur": 0.0,
            "window_metrics_source": "observations",
        }
    ]


def test_energy_report_generator_builds_d2_usage_pattern_trend_and_drift_summary(tmp_path):
    learner = PatternLearner(data_dir=str(tmp_path / "patterns"))
    learner.patterns = {
        "pattern_001": Pattern(
            pattern_id="pattern_001",
            pattern_type="weather_based",
            entity_id="climate.wohnzimmer",
            action="set_temperature",
            weather_condition="sunny",
            occurrence_count=10,
            confidence=0.84,
            first_occurrence=datetime(2026, 4, 12, 8, 0, 0),
            last_occurrence=datetime(2026, 4, 17, 8, 30, 0),
            metadata={
                "zone": "wohnzimmer",
                "estimated_energy_impact_kwh": 4.0,
            },
        ),
        "pattern_002": Pattern(
            pattern_id="pattern_002",
            pattern_type="time_based",
            entity_id="light.kueche",
            action="turn_off",
            occurrence_count=4,
            confidence=0.66,
            first_occurrence=datetime(2026, 4, 12, 22, 0, 0),
            last_occurrence=datetime(2026, 4, 14, 22, 15, 0),
            metadata={"zone_name": "kueche"},
        ),
        "pattern_003": Pattern(
            pattern_id="pattern_003",
            pattern_type="time_based",
            entity_id="media_player.buero",
            action="turn_on",
            occurrence_count=6,
            confidence=0.73,
            first_occurrence=datetime(2026, 4, 12, 19, 0, 0),
            last_occurrence=datetime(2026, 4, 17, 21, 15, 0),
            metadata={
                "zone_name": "buero",
                "estimated_cost_impact_eur": 2.5,
            },
        ),
        "pattern_004": Pattern(
            pattern_id="pattern_004",
            pattern_type="time_based",
            entity_id="sensor.solar_surplus",
            action="report",
            occurrence_count=2,
            confidence=0.68,
            first_occurrence=datetime(2026, 4, 16, 12, 0, 0),
            last_occurrence=datetime(2026, 4, 17, 12, 30, 0),
            metadata={"zone": "dach"},
        ),
    }
    learner.observations = [
        {
            "timestamp": "2026-04-13T08:00:00",
            "entity_id": "climate.wohnzimmer",
            "action": "set_temperature",
            "context": {"weather_condition": "sunny"},
        },
        {
            "timestamp": "2026-04-16T08:00:00",
            "entity_id": "climate.wohnzimmer",
            "action": "set_temperature",
            "context": {"weather_condition": "sunny"},
        },
        {
            "timestamp": "2026-04-17T08:30:00",
            "entity_id": "climate.wohnzimmer",
            "action": "set_temperature",
            "context": {"weather_condition": "sunny"},
        },
        {
            "timestamp": "2026-04-13T19:00:00",
            "entity_id": "media_player.buero",
            "action": "turn_on",
            "context": {},
        },
        {
            "timestamp": "2026-04-14T19:05:00",
            "entity_id": "media_player.buero",
            "action": "turn_on",
            "context": {},
        },
        {
            "timestamp": "2026-04-16T21:00:00",
            "entity_id": "media_player.buero",
            "action": "turn_on",
            "context": {},
        },
        {
            "timestamp": "2026-04-17T21:15:00",
            "entity_id": "media_player.buero",
            "action": "turn_on",
            "context": {},
        },
        {
            "timestamp": "2026-04-13T22:00:00",
            "entity_id": "light.kueche",
            "action": "turn_off",
            "context": {},
        },
        {
            "timestamp": "2026-04-14T22:15:00",
            "entity_id": "light.kueche",
            "action": "turn_off",
            "context": {},
        },
        {
            "timestamp": "2026-04-16T12:00:00",
            "entity_id": "sensor.solar_surplus",
            "action": "report",
            "context": {},
        },
        {
            "timestamp": "2026-04-17T12:30:00",
            "entity_id": "sensor.solar_surplus",
            "action": "report",
            "context": {},
        },
    ]

    generator = EnergyReportGenerator(grid_price_eur_kwh=0.31)
    report = generator.generate_usage_pattern_summary(
        learner,
        window_start=datetime(2026, 4, 15, 0, 0, 0),
        window_end=datetime(2026, 4, 18, 0, 0, 0),
        min_confidence=0.5,
    )

    assert report == {
        "status": "ok",
        "window": {
            "from": "2026-04-15T00:00:00",
            "to": "2026-04-18T00:00:00",
        },
        "comparison_window": {
            "from": "2026-04-12T00:00:00",
            "to": "2026-04-15T00:00:00",
        },
        "patterns": [
            {
                "pattern_id": "pattern_001",
                "category": "climate",
                "zone": "wohnzimmer",
                "frequency": 2,
                "previous_frequency": 1,
                "frequency_delta": 1,
                "confidence": 0.84,
                "last_seen": "2026-04-17T08:30:00",
                "trend": "rising",
            },
            {
                "pattern_id": "pattern_003",
                "category": "media",
                "zone": "buero",
                "frequency": 2,
                "previous_frequency": 2,
                "frequency_delta": 0,
                "confidence": 0.73,
                "last_seen": "2026-04-17T21:15:00",
                "trend": "stable",
            },
            {
                "pattern_id": "pattern_004",
                "category": "energy",
                "zone": "dach",
                "frequency": 2,
                "previous_frequency": 0,
                "frequency_delta": 2,
                "confidence": 0.68,
                "last_seen": "2026-04-17T12:30:00",
                "trend": "rising",
            },
        ],
        "impact": {
            "estimated_cost_impact_eur": 3.74,
            "estimated_energy_impact_kwh": 4.0,
        },
        "drift": {
            "summary": {
                "new_patterns": 1,
                "fading_patterns": 1,
                "rising_patterns": 1,
                "stable_patterns": 1,
                "falling_patterns": 0,
            },
            "new_patterns": [
                {
                    "pattern_id": "pattern_004",
                    "category": "energy",
                    "zone": "dach",
                    "frequency": 2,
                    "last_seen": "2026-04-17T12:30:00",
                }
            ],
            "fading_patterns": [
                {
                    "pattern_id": "pattern_002",
                    "category": "automation",
                    "zone": "kueche",
                    "previous_frequency": 2,
                    "last_seen": "2026-04-14T22:15:00",
                }
            ],
        },
    }
