"""Regression coverage for zone aggregates optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import zone_aggregates as zone_aggregates_module  # noqa: E402
from copilot_core.api.v1.zone_aggregates import init_zone_aggregates_api, zone_aggregates_bp  # noqa: E402


class _FakeAggregateResult:
    def __init__(self, category_id: str, entity_ids: list[str]):
        self.category_id = category_id
        self.entity_ids = entity_ids

    def to_dict(self):
        return {"category_id": self.category_id, "entity_ids": self.entity_ids}


class _FakeAggregator:
    def aggregate_zone(self, entity_ids: list[str]):
        return [_FakeAggregateResult("lights", entity_ids)]


class _FakeZoneAutomation:
    def get_zone_entities_by_role(self, zone_id: str):
        return {"lights": ["light.wohnzimmer_decke"]}

    def get_all_states(self):
        return [{"zone_id": "wohnbereich", "name": "Wohnbereich"}]


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(zone_aggregates_module, "http_requests", None)

    app = Flask(__name__)
    app.register_blueprint(zone_aggregates_bp)
    init_zone_aggregates_api(
        aggregator=_FakeAggregator(),
        zone_automation=_FakeZoneAutomation(),
    )
    return app.test_client()


def test_zone_aggregates_read_endpoint_stays_available_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get("/api/v1/zone/aggregates/wohnbereich", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["zone_id"] == "wohnbereich"
    assert payload["aggregates"][0]["category_id"] == "lights"


def test_zone_aggregates_scene_endpoints_degrade_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    capture = client.post(
        "/api/v1/zone/aggregates/wohnbereich/scene/capture",
        headers=headers,
        json={"name": "Abend", "create_ha_scene": True},
    )
    assert capture.status_code == 503
    assert capture.get_json()["error"] == "zone_aggregates_unavailable"

    apply_resp = client.post(
        "/api/v1/zone/aggregates/wohnbereich/scene/apply",
        headers=headers,
        json={"scene_id": "hz_wohnbereich_test"},
    )
    assert apply_resp.status_code == 503
    assert apply_resp.get_json()["error"] == "zone_aggregates_unavailable"
