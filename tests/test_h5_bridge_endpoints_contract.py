from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)

from copilot_core.api.v1 import config as config_api
from copilot_core.api.v1 import entity_normalization as entity_norm_api
from copilot_core.api.v1 import user_management as user_mgmt_api
from copilot_core.api.v1 import users as users_api
from copilot_core.api.v1 import version as version_api
from copilot_core.integration.entity_normalization import NormalizedType


def _set_auth(allowed: bool) -> None:
    validator = (lambda _request: True) if allowed else (lambda _request: False)
    config_api.validate_token = validator
    entity_norm_api.validate_token = validator
    user_mgmt_api.validate_token = validator
    users_api.validate_token = validator
    version_api.validate_token = validator


def _reset_state() -> None:
    users_api._USER_ENGINE = None
    entity_norm_api._ENTITY_NORMALIZATION_ENGINE = None


def _make_app(*, auth_allowed: bool = True) -> Flask:
    _reset_state()
    _set_auth(auth_allowed)
    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {"beta": object(), "alpha": object()}
    app.register_blueprint(config_api.config_bp)
    app.register_blueprint(entity_norm_api.entity_normalization_bp)
    app.register_blueprint(user_mgmt_api.user_management_bp)
    app.register_blueprint(users_api.users_bp)
    app.register_blueprint(version_api.version_bp)
    return app


def test_h5_bridge_endpoints_basic_contract() -> None:
    app = _make_app()
    client = app.test_client()

    version_resp = client.get("/api/v1/version")
    assert version_resp.status_code == 200
    assert version_resp.get_json()["ok"] is True
    assert version_resp.get_json()["api_version"] == "v1"

    config_resp = client.get("/api/v1/config")
    assert config_resp.status_code == 200
    config_payload = config_resp.get_json()
    assert config_payload["service_count"] == 2
    assert config_payload["service_keys"] == ["alpha", "beta"]

    services_resp = client.get("/api/v1/config/services")
    assert services_resp.status_code == 200
    assert services_resp.get_json()["services"] == ["alpha", "beta"]

    users_resp = client.get("/api/v1/users")
    assert users_resp.status_code == 200
    assert users_resp.get_json()["count"] == 0

    summary_resp = client.get("/api/v1/user-management/summary")
    assert summary_resp.status_code == 200
    assert summary_resp.get_json()["summary"]["total_users"] == 0

    roles_resp = client.get("/api/v1/user-management/roles")
    assert roles_resp.status_code == 200
    assert roles_resp.get_json()["count"] >= 4

    entity_resp = client.get("/api/v1/entity-normalization/health")
    assert entity_resp.status_code == 200
    assert entity_resp.get_json()["statistics"]["total_mappings"] == 0


def test_h5_bridge_endpoints_enforce_auth() -> None:
    app = _make_app(auth_allowed=False)
    client = app.test_client()

    for path in (
        "/api/v1/version",
        "/api/v1/config",
        "/api/v1/users",
        "/api/v1/user-management/summary",
        "/api/v1/entity-normalization/health",
    ):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.get_json()["error"] == "unauthorized"


def test_h5_user_management_stateful_contract() -> None:
    app = _make_app()
    client = app.test_client()

    invalid_resp = client.post("/api/v1/user-management/users", json={"username": "andreas"})
    assert invalid_resp.status_code == 400
    assert invalid_resp.get_json()["error"] == "invalid_request"

    create_resp = client.post(
        "/api/v1/user-management/users",
        json={
            "username": "andreas",
            "email": "andreas@example.com",
            "password": "secret-123",
            "roles": ["role_admin"],
        },
    )
    assert create_resp.status_code == 201
    create_payload = create_resp.get_json()
    user_id = create_payload["user_id"]
    assert create_payload["user"]["username"] == "andreas"
    assert create_payload["user"]["roles"] == ["role_admin"]
    assert create_payload["user"]["enabled"] is True

    users_resp = client.get("/api/v1/users")
    assert users_resp.status_code == 200
    assert users_resp.get_json()["count"] == 1

    user_resp = client.get(f"/api/v1/users/{user_id}")
    assert user_resp.status_code == 200
    assert user_resp.get_json()["user"]["email"] == "andreas@example.com"

    missing_user_resp = client.get("/api/v1/users/user_missing")
    assert missing_user_resp.status_code == 404
    assert missing_user_resp.get_json()["error"] == "not_found"

    disable_resp = client.post(f"/api/v1/user-management/users/{user_id}/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.get_json()["enabled"] is False
    assert client.get(f"/api/v1/users/{user_id}").get_json()["user"]["enabled"] is False

    enable_resp = client.post(f"/api/v1/user-management/users/{user_id}/enable")
    assert enable_resp.status_code == 200
    assert enable_resp.get_json()["enabled"] is True

    missing_toggle_resp = client.post("/api/v1/user-management/users/user_missing/disable")
    assert missing_toggle_resp.status_code == 404
    assert missing_toggle_resp.get_json()["error"] == "not_found"

    summary_resp = client.get("/api/v1/user-management/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.get_json()["summary"]
    assert summary["total_users"] == 1
    assert summary["enabled_users"] == 1


def test_h5_entity_normalization_zone_payload_contract() -> None:
    app = _make_app()
    client = app.test_client()
    engine = entity_norm_api._get_engine()

    engine.map_entity(
        "sensor.living_room_temperature",
        "living_room",
        NormalizedType.TEMPERATURE,
        normalization_params={"min": 0, "max": 40},
    )
    engine.update_state(
        "sensor.living_room_temperature",
        21,
        {"unit_of_measurement": "°C"},
    )

    mappings_resp = client.get("/api/v1/entity-normalization/mappings?zone_id=living_room")
    assert mappings_resp.status_code == 200
    mappings = mappings_resp.get_json()["mappings"]
    assert len(mappings) == 1
    assert mappings[0]["ha_entity_id"] == "sensor.living_room_temperature"

    zone_resp = client.get("/api/v1/entity-normalization/zones/living_room")
    assert zone_resp.status_code == 200
    zone_payload = zone_resp.get_json()
    assert zone_payload["zone_id"] == "living_room"
    assert zone_payload["registry"]["input_entities"]["temperature"]
    assert zone_payload["states"]["temperature"]["raw_value"] == 21
    assert zone_payload["states"]["temperature"]["unit"] == "°C"

    unknown_zone_resp = client.get("/api/v1/entity-normalization/zones/unknown_zone")
    assert unknown_zone_resp.status_code == 200
    unknown_payload = unknown_zone_resp.get_json()
    assert unknown_payload["registry"] is None
    assert unknown_payload["states"] == {}
