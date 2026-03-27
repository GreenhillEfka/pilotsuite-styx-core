"""Truth-lane contract coverage for zone aggregates."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1.zone_aggregates import (  # noqa: E402
    _get_zone,
    get_zone_aggregates,
    init_zone_aggregates_api,
    zone_aggregates_bp,
)


class _FakeZoneEngine:
    def get_overview(self):
        return SimpleNamespace(zones=[{"zone_id": "wohnbereich"}])

    def get_zone(self, zone_id: str):
        assert zone_id == "wohnbereich"
        return {
            "zone_id": "wohnbereich",
            "name": "Wohnbereich",
            "zone_type": "living",
            "enabled_modules": ["licht_module", "media_zones"],
            "entities": ["light.wohnzimmer_decke", "binary_sensor.wohnzimmer_motion"],
        }


class _FakeZoneAutomation:
    def get_zone_entities_by_role(self, zone_id: str):
        assert zone_id == "wohnbereich"
        return {
            "lights": ["light.wohnzimmer_decke"],
            "motion": ["binary_sensor.wohnzimmer_motion"],
        }


class _FakeAggregateResult:
    def __init__(self, category_id: str, entity_ids: list[str]):
        self.category_id = category_id
        self.entity_ids = entity_ids

    def to_dict(self):
        return {"category_id": self.category_id, "entity_ids": self.entity_ids}


class _FakeAggregator:
    def aggregate_zone(self, entity_ids: list[str]):
        return [_FakeAggregateResult("lights", entity_ids)]


def test_zone_aggregates_prefers_truth_engine_and_role_merge() -> None:
    init_zone_aggregates_api(
        aggregator=_FakeAggregator(),
        zone_automation=_FakeZoneAutomation(),
        habitus_zones=_FakeZoneEngine(),
    )

    zone = _get_zone("wohnbereich")
    assert zone is not None
    assert zone["zone_id"] == "wohnbereich"
    assert zone["zone_type"] == "living"
    assert zone["enabled_modules"] == ["licht_module", "media_zones"]
    assert zone["entities"]["lights"] == ["light.wohnzimmer_decke"]
    assert zone["entities"]["motion"] == ["binary_sensor.wohnzimmer_motion"]
    assert zone["entity_ids"] == ["light.wohnzimmer_decke", "binary_sensor.wohnzimmer_motion"]


def test_zone_aggregates_endpoint_exposes_truth_metadata(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_aggregates_bp)

    init_zone_aggregates_api(
        aggregator=_FakeAggregator(),
        zone_automation=_FakeZoneAutomation(),
        habitus_zones=_FakeZoneEngine(),
    )

    with app.test_request_context(
        "/api/v1/zone/aggregates/wohnbereich",
        method="GET",
        headers={"Authorization": "Bearer test-token"},
    ):
        response = get_zone_aggregates("wohnbereich")

    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["zone_id"] == "wohnbereich"
    assert payload["zone_type"] == "living"
    assert payload["enabled_modules"] == ["licht_module", "media_zones"]
    assert payload["entities_by_role"]["lights"] == ["light.wohnzimmer_decke"]
    assert payload["total_entities"] == 2
    assert payload["aggregates"][0]["category_id"] == "lights"
