from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import ha_module as module  # noqa: E402


class FakeDashboard:
    def __init__(self) -> None:
        self.connection = {
            "connected": True,
            "base_url": "http://homeassistant.local:8123",
            "last_error": None,
        }
        self.event_forwarding = {
            "enabled": True,
            "forwarded_domains": ["light", "climate"],
            "forwarded_event_count": 12,
        }
        self.webhook = {
            "enabled": True,
            "webhook_id": "ha-core",
            "received_count": 2,
        }
        self.supervisor = {"available": True, "healthy": True}
        self.integration_entity_count = 21
        self.module_count = 5
        self.active_dashboard_views = ["overview", "diagnostics"]


class FakeEngine:
    def __init__(self) -> None:
        self.dashboard = FakeDashboard()
        self.config = {
            "enabled": True,
            "forwarded_domains": ["light", "climate"],
            "webhook_retry_count": 3,
        }
        self.diagnostics = {"pipeline": "healthy", "webhook_lag_ms": 15}
        self.pipeline_health = {"health": "green", "stages": ["ingest", "route"]}
        self.forwarded_domains_calls: list[list[str]] = []
        self.updated_payloads: list[dict[str, object]] = []
        self.recorded_webhooks: list[str] = []
        self._webhook_received_count = 2

    def get_status(self) -> FakeDashboard:
        return self.dashboard

    def configure_forwarded_domains(self, domains: list[str]) -> None:
        self.forwarded_domains_calls.append(domains)
        self.dashboard.event_forwarding["forwarded_domains"] = domains

    def get_config(self) -> dict[str, object]:
        return dict(self.config)

    def update_config(self, data: dict[str, object]) -> dict[str, object]:
        self.updated_payloads.append(data)
        self.config = {**self.config, **data}
        return dict(self.config)

    def get_diagnostics(self) -> dict[str, object]:
        return dict(self.diagnostics)

    def get_pipeline_health(self) -> dict[str, object]:
        return dict(self.pipeline_health)

    def record_webhook(self, event_type: str) -> None:
        self.recorded_webhooks.append(event_type)
        self._webhook_received_count += 1


class FakeRouter:
    def __init__(self) -> None:
        self.updated_configs: list[tuple[str, dict[str, object]]] = []
        self.refresh_calls = 0

    def update_config(self, module_name: str, config: dict[str, object]) -> None:
        self.updated_configs.append((module_name, config))

    async def async_refresh_from_ha(self) -> dict[str, object]:
        self.refresh_calls += 1
        return {"refreshed_modules": 4, "updated": ["licht", "heiz"]}


def _build_client(monkeypatch, *, engine=None, router=None, authorized: bool = True):
    monkeypatch.setattr(module, "_validate_token", lambda _request: authorized)
    app = Flask(__name__)
    services = {}
    if engine is not None:
        services["ha_module_engine"] = engine
    if router is not None:
        services["module_router"] = router
    app.config["COPILOT_SERVICES"] = services
    app.register_blueprint(module.ha_module_bp)
    return app.test_client(), app


def test_ha_module_contract_covers_status_config_diagnostics_webhook_and_refresh(monkeypatch) -> None:
    engine = FakeEngine()
    router = FakeRouter()
    client, _app = _build_client(monkeypatch, engine=engine, router=router)

    response = client.get("/api/v1/modules/homeassistant/status")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "module": "homeassistant",
        "connection": engine.dashboard.connection,
        "event_forwarding": engine.dashboard.event_forwarding,
        "webhook": engine.dashboard.webhook,
        "supervisor": engine.dashboard.supervisor,
        "integration_entity_count": 21,
        "module_count": 5,
        "active_dashboard_views": ["overview", "diagnostics"],
    }

    response = client.get("/api/v1/modules/homeassistant/connection")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", **engine.dashboard.connection}

    response = client.get("/api/v1/modules/homeassistant/events")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", **engine.dashboard.event_forwarding}

    response = client.post(
        "/api/v1/modules/homeassistant/events/config",
        json={"domains": ["light", "switch"]},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "message": "Event forwarding configured for 2 domains",
        "domains": ["light", "switch"],
    }
    assert engine.forwarded_domains_calls == [["light", "switch"]]

    response = client.get("/api/v1/modules/homeassistant/config")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "module": "homeassistant",
        "config": engine.config,
    }

    response = client.post(
        "/api/v1/modules/homeassistant/config",
        json={"webhook_retry_count": 5, "forwarded_domains": ["light"]},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "module": "homeassistant",
        "config": {
            "enabled": True,
            "forwarded_domains": ["light"],
            "webhook_retry_count": 5,
        },
    }
    assert engine.updated_payloads == [{"webhook_retry_count": 5, "forwarded_domains": ["light"]}]
    assert router.updated_configs == [
        (
            "homeassistant",
            {"enabled": True, "forwarded_domains": ["light"], "webhook_retry_count": 5},
        )
    ]

    response = client.get("/api/v1/modules/homeassistant/diagnostics")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "module": "homeassistant",
        "diagnostics": engine.diagnostics,
        "pipeline_health": engine.pipeline_health,
    }

    response = client.get("/api/v1/modules/homeassistant/health")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "module": "homeassistant",
        **engine.pipeline_health,
    }

    response = client.post("/api/v1/modules/homeassistant/webhook-received", json={"event_type": "state_changed"})
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "message": "Webhook recorded: state_changed",
        "webhook_received_count": 3,
    }
    assert engine.recorded_webhooks == ["state_changed"]

    response = client.post("/api/v1/modules/homeassistant/refresh")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "module": "homeassistant",
        "refreshed_modules": 4,
        "updated": ["licht", "heiz"],
    }
    assert router.refresh_calls == 1


def test_ha_module_contract_hardens_auth_lazy_init_validation_and_missing_router(monkeypatch) -> None:
    engine = FakeEngine()
    client, _app = _build_client(monkeypatch, engine=engine, authorized=False)

    response = client.get("/api/v1/modules/homeassistant/status")
    assert response.status_code == 401
    assert response.get_json() == {
        "error": "unauthorized",
        "message": "Valid X-Auth-Token or Bearer token required",
    }

    monkeypatch.setattr(module, "HomeAssistantModuleEngine", FakeEngine)
    client, app = _build_client(monkeypatch)

    response = client.get("/api/v1/modules/homeassistant/status")
    assert response.status_code == 200
    assert response.get_json()["module"] == "homeassistant"
    assert isinstance(app._ha_module_engine, FakeEngine)

    response = client.post("/api/v1/modules/homeassistant/events/config")
    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "message": "Missing or invalid 'domains' list in request body",
    }

    response = client.post("/api/v1/modules/homeassistant/events/config", json=["bad"])
    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "JSON body must be an object"}

    response = client.post("/api/v1/modules/homeassistant/events/config", json={"domains": []})
    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "message": "At least one domain string required",
    }

    response = client.post("/api/v1/modules/homeassistant/config")
    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "Request body required"}

    response = client.post("/api/v1/modules/homeassistant/config", json=["bad"])
    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "JSON body must be an object"}

    response = client.post("/api/v1/modules/homeassistant/webhook-received", json=["bad"])
    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "JSON body must be an object"}

    response = client.post("/api/v1/modules/homeassistant/webhook-received", json={"event_type": "  "})
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "message": "Webhook recorded: unknown",
        "webhook_received_count": 3,
    }

    client, _app = _build_client(monkeypatch, engine=engine)
    response = client.post("/api/v1/modules/homeassistant/refresh")
    assert response.status_code == 503
    assert response.get_json() == {"status": "error", "message": "ModuleRouter not available"}


def test_ha_module_contract_returns_json_500_for_runtime_errors(monkeypatch) -> None:
    engine = FakeEngine()
    router = FakeRouter()
    client, _app = _build_client(monkeypatch, engine=engine, router=router)

    def explode() -> None:
        raise RuntimeError("ha module exploded")

    def explode_configure(_domains: list[str]) -> None:
        raise RuntimeError("ha module exploded")

    def explode_update(_payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("ha module exploded")

    def explode_record(_event_type: str) -> None:
        raise RuntimeError("ha module exploded")

    async def explode_refresh() -> dict[str, object]:
        raise RuntimeError("ha module exploded")

    monkeypatch.setattr(engine, "get_status", explode)
    response = client.get("/api/v1/modules/homeassistant/status")
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "ha module exploded"}

    monkeypatch.setattr(engine, "configure_forwarded_domains", explode_configure)
    response = client.post("/api/v1/modules/homeassistant/events/config", json={"domains": ["light"]})
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "ha module exploded"}

    monkeypatch.setattr(engine, "update_config", explode_update)
    response = client.post("/api/v1/modules/homeassistant/config", json={"enabled": False})
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "ha module exploded"}

    monkeypatch.setattr(engine, "get_diagnostics", explode)
    response = client.get("/api/v1/modules/homeassistant/diagnostics")
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "ha module exploded"}

    monkeypatch.setattr(engine, "get_pipeline_health", explode)
    response = client.get("/api/v1/modules/homeassistant/health")
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "ha module exploded"}

    monkeypatch.setattr(engine, "record_webhook", explode_record)
    response = client.post("/api/v1/modules/homeassistant/webhook-received", json={"event_type": "state_changed"})
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "ha module exploded"}

    monkeypatch.setattr(router, "async_refresh_from_ha", explode_refresh)
    response = client.post("/api/v1/modules/homeassistant/refresh")
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "ha module exploded"}
