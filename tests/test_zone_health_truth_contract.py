"""Truth-lane contract coverage for zone health."""

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


from copilot_core.api.v1 import zone_health as zone_health_module  # noqa: E402
from copilot_core.api.v1.zone_health import (  # noqa: E402
    ZoneHealthChecker,
    ZoneHealthResult,
    get_zone_health_detail,
    init_zone_health_api,
    zone_health_bp,
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


class _FakeModuleRegistry:
    def get_zone_states(self, zone_id: str):
        assert zone_id == "wohnbereich"
        return {"licht_module": "active", "media_zones": "learning"}


def test_zone_health_prefers_truth_engine_and_merges_role_assignments() -> None:
    init_zone_health_api(
        zone_automation=_FakeZoneAutomation(),
        module_registry=_FakeModuleRegistry(),
        habitus_zones=_FakeZoneEngine(),
    )

    checker = ZoneHealthChecker()
    zones = checker._get_zones()

    assert len(zones) == 1
    zone = zones[0]
    assert zone["zone_id"] == "wohnbereich"
    assert zone["zone_type"] == "living"
    assert zone["enabled_modules"] == ["licht_module", "media_zones"]
    assert zone["entities"]["lights"] == ["light.wohnzimmer_decke"]
    assert zone["entities"]["motion"] == ["binary_sensor.wohnzimmer_motion"]
    assert zone["entity_ids"] == ["light.wohnzimmer_decke", "binary_sensor.wohnzimmer_motion"]


def test_zone_health_detail_exposes_truth_metadata(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(zone_health_module, "http_requests", object())
    monkeypatch.setattr(zone_health_module, "_checker", None)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_health_bp)

    init_zone_health_api(
        zone_automation=_FakeZoneAutomation(),
        module_registry=_FakeModuleRegistry(),
        habitus_zones=_FakeZoneEngine(),
    )

    zone_data = {
        "zone_id": "wohnbereich",
        "name_de": "Wohnbereich",
        "zone_type": "living",
        "enabled_modules": ["licht_module", "media_zones"],
        "entity_ids": ["light.wohnzimmer_decke"],
        "entities": {"lights": ["light.wohnzimmer_decke"]},
    }

    result = ZoneHealthResult(
        zone_id="wohnbereich",
        zone_name="Wohnbereich",
        zone_type="living",
        enabled_modules=["licht_module", "media_zones"],
        health_score=92,
        status="healthy",
    )

    monkeypatch.setattr(ZoneHealthChecker, "_get_zones", lambda self: [zone_data])
    monkeypatch.setattr(ZoneHealthChecker, "check_zone", lambda self, zone: result)

    with app.test_request_context(
        "/api/v1/zone/health/wohnbereich",
        method="GET",
        headers={"Authorization": "Bearer test-token"},
    ):
        response = get_zone_health_detail("wohnbereich")

    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["zone"]["zone_type"] == "living"
    assert payload["zone"]["enabled_modules"] == ["licht_module", "media_zones"]
    assert payload["zone"]["health_score"] == 92
