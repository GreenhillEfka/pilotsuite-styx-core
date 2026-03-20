from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copilot_core.api.v1 import zone_config as zone_config_mod


def _make_client() -> TestClient:
    zone_config_mod._zone_configs = {}
    app = FastAPI()
    app.include_router(zone_config_mod.router, prefix="/api/v1")
    return TestClient(app)


def test_list_zone_configs_returns_integrated_defaults() -> None:
    client = _make_client()

    response = client.get("/api/v1/zone-config")

    assert response.status_code == 200
    data = response.json()
    assert data["total_zones"] == 10
    assert data["supported_module_ids"] == [
        "light",
        "motion",
        "music",
        "volume",
        "tv",
        "climate",
        "camera",
    ]

    wohnbereich = next(zone for zone in data["zones"] if zone["zone_id"] == "wohnbereich")
    assert wohnbereich["zone_type"] == "area"
    assert len(wohnbereich["modules"]) == 7
    assert wohnbereich["aggregation_rules"][0]["target_zone"] == "wohnbereich"
    assert wohnbereich["fallback_semantics"]["unmatched_fallback_zone_id"] == "ungeordnet"


def test_get_single_zone_config_exposes_room_registry_and_modules() -> None:
    client = _make_client()

    response = client.get("/api/v1/zone-config/badbereich")

    assert response.status_code == 200
    data = response.json()
    assert data["zone_id"] == "badbereich"
    assert {mapping["area_id"] for mapping in data["room_mappings"]} == {"badezimmer", "wc"}

    modules = {module["module_id"]: module for module in data["modules"]}
    assert modules["climate"]["enabled"] is True
    assert modules["camera"]["enabled"] is False


def test_post_updates_zone_module_and_preserves_contract_shape() -> None:
    client = _make_client()

    response = client.post(
        "/api/v1/zone-config",
        json={
            "zone_id": "wohnbereich",
            "modules": [
                {
                    "module_id": "tv",
                    "enabled": True,
                    "direct_execution_enabled": True,
                    "approval_required": False,
                    "explanation_required": False,
                    "autonomy_mode": "autonomous",
                    "notes": "Operator explicitly enabled direct TV execution.",
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    modules = {module["module_id"]: module for module in data["modules"]}
    assert len(modules) == 7
    assert modules["tv"]["enabled"] is True
    assert modules["tv"]["direct_execution_enabled"] is True
    assert modules["tv"]["approval_required"] is False
    assert modules["light"]["enabled"] is True


def test_put_requires_matching_zone_id() -> None:
    client = _make_client()

    response = client.put(
        "/api/v1/zone-config/wohnbereich",
        json={"zone_id": "badbereich"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "ZONE_ID_MISMATCH"


def test_delete_resets_zone_to_integrated_defaults() -> None:
    client = _make_client()

    update_response = client.post(
        "/api/v1/zone-config",
        json={
            "zone_id": "gangbereich",
            "modules": [
                {
                    "module_id": "camera",
                    "enabled": False,
                    "notes": "Temporarily disabled for testing.",
                }
            ],
        },
    )
    assert update_response.status_code == 200
    updated_zone = update_response.json()
    updated_camera = next(module for module in updated_zone["modules"] if module["module_id"] == "camera")
    assert updated_camera["enabled"] is False

    delete_response = client.delete("/api/v1/zone-config/gangbereich")

    assert delete_response.status_code == 200
    data = delete_response.json()
    assert data["ok"] is True
    assert data["action"] == "reset_to_defaults"
    reset_camera = next(module for module in data["zone"]["modules"] if module["module_id"] == "camera")
    assert reset_camera["enabled"] is True
