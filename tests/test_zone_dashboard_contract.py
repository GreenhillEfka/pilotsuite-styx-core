"""Contract coverage for zone dashboard ID normalization."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1.zone_dashboard import (  # noqa: E402
    get_dashboard,
    get_dashboard_summary,
    get_mood,
    get_zone_detail,
    init_zone_dashboard_api,
    set_mood,
    zone_dashboard_bp,
)
from copilot_core.action_closure import get_action_closure_store  # noqa: E402
from copilot_core.hub.habitus_zones import HabitusZoneEngine  # noqa: E402
from copilot_core.hub.zone_automation import ZoneAutomationController  # noqa: E402


def _init_services() -> tuple[HabitusZoneEngine, ZoneAutomationController]:
    get_action_closure_store().clear()
    zone_engine = HabitusZoneEngine()
    zone_engine.sync_external_zone_topology(
        "wohnbereich",
        name="Wohnbereich",
        zone_type="living",
        enabled_modules={"light", "motion"},
        entities=["light.living_room_main", "binary_sensor.living_room_motion"],
    )

    zone_automation = ZoneAutomationController()
    zone_automation.sync_entities_from_topology(
        "wohnbereich",
        [
            {"entity_id": "light.living_room_main", "role": "lights"},
            {"entity_id": "binary_sensor.living_room_motion", "role": "motion"},
        ],
    )

    init_zone_dashboard_api(habitus_zones=zone_engine, zone_automation=zone_automation)
    return zone_engine, zone_automation


def test_zone_dashboard_detail_accepts_unprefixed_truth_zone_id() -> None:
    _init_services()
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_dashboard_bp)

    with app.test_request_context("/api/v1/zone/dashboard/wohnbereich", method="GET"):
        response = get_zone_detail.__wrapped__("wohnbereich")

    body = response.get_json()
    assert body["ok"] is True
    assert body["zone"]["zone_id"] == "wohnbereich"
    assert body["zone"]["zone_type"] == "living"
    assert body["zone"]["entity_ids"] == ["light.living_room_main", "binary_sensor.living_room_motion"]


def test_zone_dashboard_mood_update_keeps_unprefixed_truth_zone_id() -> None:
    _init_services()
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_dashboard_bp)

    with app.test_request_context(
        "/api/v1/zone/dashboard/mood/wohnbereich",
        method="PUT",
        json={"comfort": 0.7, "joy": 0.6, "frugality": 0.4},
    ):
        response = set_mood.__wrapped__("wohnbereich")

    body = response.get_json()
    assert body["ok"] is True
    assert body["zone_id"] == "wohnbereich"
    assert body["mood"]["comfort"] == 0.7


def test_zone_dashboard_summary_prefers_truth_engine_zones() -> None:
    _init_services()
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_dashboard_bp)

    with app.test_request_context("/api/v1/zone/dashboard/summary", method="GET"):
        response = get_dashboard_summary.__wrapped__()

    body = response.get_json()
    assert body["ok"] is True
    assert body["summary"]["total_zones"] == 1
    assert body["summary"]["zone_types"] == {"living": 1}
    assert body["summary"]["total_entities"] == 2


def test_zone_dashboard_surfaces_zone_scoped_action_closure_context() -> None:
    _init_services()
    store = get_action_closure_store()
    closure = store.upsert(
        source="voice.accepted",
        proposal_id="proposal:wohnbereich",
        action_id="action:wohnbereich",
        zone_id="wohnbereich",
        module_id="light",
        accepted_at="2026-04-01T21:00:00+00:00",
    )
    store.record_execution(
        closure["closure_id"],
        outcome="executed",
        runtime_source="ha.adapter",
        executed_at="2026-04-01T21:01:00+00:00",
    )

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_dashboard_bp)

    with app.test_request_context("/api/v1/zone/dashboard", method="GET"):
        dashboard_response = get_dashboard.__wrapped__()
    dashboard_body = dashboard_response.get_json()
    assert dashboard_body["zones"][0]["action_closures"]["context"]["summary"]["total_closures"] == 1
    assert any(
        "Wohnbereich" in line
        for line in dashboard_body["zones"][0]["action_closures"]["context"]["context_lines"]
    )

    with app.test_request_context("/api/v1/zone/dashboard/wohnbereich", method="GET"):
        detail_response = get_zone_detail.__wrapped__("wohnbereich")
    detail_body = detail_response.get_json()
    assert detail_body["zone"]["action_closures"]["context"]["summary"]["total_closures"] == 1
    assert detail_body["zone"]["action_closures"]["zone_name"] == "Wohnbereich"


def test_zone_dashboard_action_closure_since_param_surfaces_delta_state() -> None:
    _init_services()
    store = get_action_closure_store()
    base_revision = store.get_current_revision()
    closure = store.upsert(
        source="voice.accepted",
        proposal_id="proposal:wohnbereich:delta",
        action_id="action:wohnbereich:delta",
        zone_id="wohnbereich",
        module_id="light",
        accepted_at="2026-04-01T21:02:00+00:00",
    )

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_dashboard_bp)

    with app.test_request_context(
        f"/api/v1/zone/dashboard/wohnbereich?action_closure_since={base_revision}",
        method="GET",
    ):
        detail_response = get_zone_detail.__wrapped__("wohnbereich")

    detail_body = detail_response.get_json()
    delta = detail_body["zone"]["action_closures"]["context"]["delta"]
    assert delta["since_revision"] == base_revision
    assert delta["changed"] is True
    assert delta["changed_count"] == 1
    assert delta["recent_closures"][0]["closure_id"] == closure["closure_id"]

    current_revision = store.get_current_revision()
    with app.test_request_context(
        f"/api/v1/zone/dashboard/wohnbereich?action_closure_since={current_revision}",
        method="GET",
    ):
        unchanged_response = get_zone_detail.__wrapped__("wohnbereich")

    unchanged_body = unchanged_response.get_json()
    unchanged_delta = unchanged_body["zone"]["action_closures"]["context"]["delta"]
    assert unchanged_delta["changed"] is False
    assert unchanged_delta["changed_count"] == 0


def test_zone_dashboard_mood_list_prefers_truth_engine_zones() -> None:
    _init_services()
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(zone_dashboard_bp)

    with app.test_request_context("/api/v1/zone/dashboard/mood", method="GET"):
        response = get_mood.__wrapped__()

    body = response.get_json()
    assert body["ok"] is True
    assert body["count"] == 1
    assert set(body["mood"].keys()) == {"wohnbereich"}
