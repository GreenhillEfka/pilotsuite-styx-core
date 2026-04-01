"""Contract coverage for Slice 15 multi-zone coordination API surface."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1.multizone import multizone_bp  # noqa: E402
from copilot_core.multizone.coordination_engine import create_multi_zone_coordination_engine  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {
        "multizone_engine": create_multi_zone_coordination_engine(),
    }
    app.register_blueprint(multizone_bp)
    return app.test_client()


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def test_create_and_activate_scene_exposes_pending_queue(monkeypatch) -> None:
    client = _client(monkeypatch)

    create_response = client.post(
        "/api/v1/multizone/scenes",
        headers=_headers(),
        json={
            "name": "Evening Arrival",
            "description": "Wohnzimmer und Küche vorbereiten",
            "zone_actions": {
                "zone_living": [
                    {
                        "module_id": "licht_living",
                        "entity_id": "light.living_room",
                        "domain": "light",
                        "service": "turn_on",
                        "data": {"brightness": 180},
                        "priority": 7,
                    }
                ],
                "zone_kitchen": [
                    {
                        "module_id": "licht_kitchen",
                        "entity_id": "light.kitchen",
                        "domain": "light",
                        "service": "turn_on",
                        "data": {"brightness": 255},
                        "priority": 5,
                    }
                ],
            },
        },
    )
    assert create_response.status_code == 200
    scene_body = create_response.get_json()
    assert scene_body["ok"] is True
    scene_id = scene_body["scene_id"]
    assert scene_body["scene"]["contract"] == "MultiZoneSceneV1"

    activate_response = client.post(
        f"/api/v1/multizone/scenes/{scene_id}/activate",
        headers=_headers(),
        json={"activated_by": "contract-test"},
    )
    assert activate_response.status_code == 200
    activate_body = activate_response.get_json()
    assert activate_body["ok"] is True
    assert activate_body["scene"]["is_active"] is True
    assert activate_body["scene"]["activated_by"] == "contract-test"
    assert len(activate_body["pending_actions"]) == 2
    assert activate_body["pending_actions"][0]["priority"] >= activate_body["pending_actions"][1]["priority"]


def test_conflicts_endpoint_reports_resolved_priority_decision(monkeypatch) -> None:
    client = _client(monkeypatch)

    create_response = client.post(
        "/api/v1/multizone/scenes",
        headers=_headers(),
        json={
            "name": "Conflict Scene",
            "description": "Zwei widersprüchliche Befehle für dieselbe Lampe",
            "zone_actions": {
                "zone_living": [
                    {
                        "module_id": "licht_living",
                        "entity_id": "light.living_room",
                        "domain": "light",
                        "service": "turn_off",
                        "priority": 2,
                    },
                    {
                        "module_id": "licht_living",
                        "entity_id": "light.living_room",
                        "domain": "light",
                        "service": "turn_on",
                        "priority": 9,
                    },
                ]
            },
        },
    )
    scene_id = create_response.get_json()["scene_id"]

    activate_response = client.post(
        f"/api/v1/multizone/scenes/{scene_id}/activate",
        headers=_headers(),
        json={},
    )
    assert activate_response.status_code == 200
    body = activate_response.get_json()
    assert body["ok"] is True
    assert len(body["pending_actions"]) == 1
    assert body["pending_actions"][0]["service"] == "turn_on"

    conflicts_response = client.get(
        "/api/v1/multizone/conflicts?include_resolved=true",
        headers=_headers(),
    )
    assert conflicts_response.status_code == 200
    conflicts_body = conflicts_response.get_json()
    assert conflicts_body["count"] == 1
    conflict = conflicts_body["conflicts"][0]
    assert conflict["contract"] == "MultiZoneConflictV1"
    assert conflict["conflict_type"] == "state_conflict"
    assert conflict["resolved"] is True
    assert "Priority-based" in conflict["resolution"]


def test_create_and_trigger_routine_updates_stats(monkeypatch) -> None:
    client = _client(monkeypatch)

    create_response = client.post(
        "/api/v1/multizone/routines",
        headers=_headers(),
        json={
            "name": "Good Night",
            "description": "Lichter aus und Routine zählen",
            "trigger_type": "time",
            "trigger_config": {"hour": 22, "minute": 0},
            "zone_actions": {
                "zone_bedroom": [
                    {
                        "module_id": "licht_bedroom",
                        "entity_id": "light.bedroom",
                        "domain": "light",
                        "service": "turn_off",
                        "priority": 8,
                    }
                ]
            },
        },
    )
    assert create_response.status_code == 200
    routine_id = create_response.get_json()["routine_id"]

    trigger_response = client.post(
        f"/api/v1/multizone/routines/{routine_id}/trigger",
        headers=_headers(),
    )
    assert trigger_response.status_code == 200
    trigger_body = trigger_response.get_json()
    assert trigger_body["ok"] is True
    assert trigger_body["routine"]["contract"] == "MultiZoneRoutineV1"
    assert trigger_body["routine"]["trigger_count"] == 1

    stats_response = client.get("/api/v1/multizone/stats", headers=_headers())
    assert stats_response.status_code == 200
    stats = stats_response.get_json()["stats"]
    assert stats["routines_total"] == 1
    assert stats["pending_actions"] == 1
    assert stats["conflicts_unresolved"] == 0
