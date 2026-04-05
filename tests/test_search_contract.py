from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Blueprint, Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
MODULE_PATH = CORE_APP_ROOT / "copilot_core" / "api" / "v1" / "search.py"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

spec = importlib.util.spec_from_file_location("ps_search_contract_module", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeEngine:
    def __init__(self) -> None:
        self.raise_on: str | None = None

    def search(self, query, types=None, limit=20):
        if self.raise_on == "search":
            raise RuntimeError("search exploded")
        return module.SearchResponse(query=query)

    def filter_entities(self, domain=None, state=None, area=None, limit=50):
        if self.raise_on == "filter_entities":
            raise RuntimeError("filter exploded")
        return []

    def get_stats(self):
        if self.raise_on == "get_stats":
            raise RuntimeError("stats exploded")
        return {
            "entities": 0,
            "automations": 0,
            "scripts": 0,
            "scenes": 0,
            "services": 0,
            "domains": {},
        }

    def update_entities(self, payload):
        if self.raise_on == "update_entities":
            raise RuntimeError("entities exploded")

    def update_automations(self, payload):
        if self.raise_on == "update_automations":
            raise RuntimeError("automations exploded")

    def update_scripts(self, payload):
        if self.raise_on == "update_scripts":
            raise RuntimeError("scripts exploded")

    def update_scenes(self, payload):
        if self.raise_on == "update_scenes":
            raise RuntimeError("scenes exploded")

    def update_services(self, payload):
        if self.raise_on == "update_services":
            raise RuntimeError("services exploded")


def _build_client(monkeypatch, *, authorized: bool = True, engine=None):
    if engine is None:
        engine = module.QuickSearchEngine()

    monkeypatch.setattr(module, "_validate_token", lambda _request: authorized)
    monkeypatch.setattr(module, "get_search_engine", lambda: engine)

    app = Flask(__name__)
    api_v1 = Blueprint("api_v1_test", __name__, url_prefix="/api/v1")
    api_v1.register_blueprint(module.bp)
    app.register_blueprint(api_v1)
    return app.test_client(), engine


def test_search_contract_covers_index_search_entities_and_stats(monkeypatch) -> None:
    client, _engine = _build_client(monkeypatch)

    response = client.post(
        "/api/v1/search/index",
        json={
            "entities": {
                "light.kitchen": {
                    "state": "on",
                    "attributes": {
                        "friendly_name": "Kitchen Light",
                        "area_id": "kitchen",
                        "brightness": 255,
                        "access_token": "secret",
                    },
                },
                "sensor.outdoor_temperature": {
                    "state": "18",
                    "attributes": {
                        "friendly_name": "Outdoor Temperature",
                        "unit_of_measurement": "°C",
                    },
                },
            },
            "automations": {
                "automation.kitchen_evening": {
                    "alias": "Kitchen Evening",
                    "trigger": [{"platform": "state"}],
                    "condition": [{"condition": "state", "entity_id": "sun.sun"}],
                    "action": [{"service": "light.turn_on"}],
                    "enabled": True,
                }
            },
            "scripts": {
                "script.good_night": {
                    "alias": "Good Night",
                    "sequence": [{"service": "light.turn_off"}],
                    "mode": "single",
                }
            },
            "scenes": {
                "scene.relax": {
                    "alias": "Relax",
                    "entities": {"light.kitchen": {"state": "dimmed"}},
                }
            },
            "services": {
                "light.turn_on": {
                    "description": "Turns on a light",
                    "fields": {"entity_id": {"required": True}},
                }
            },
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "indexed": {
                "entities": 2,
                "automations": 1,
                "scripts": 1,
                "scenes": 1,
                "services": 1,
                "domains": {"light": 1, "sensor": 1},
            },
            "message": "Search index updated",
        },
    }

    response = client.get("/api/v1/search?q=kitchen&types=entity&limit=5")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["query"] == "kitchen"
    assert payload["data"]["total_count"] == 1
    assert payload["data"]["results"][0] == {
        "id": "light.kitchen",
        "type": "entity",
        "title": "Kitchen Light",
        "subtitle": "light • on • kitchen",
        "domain": "light",
        "state": "on",
        "icon": "mdi:lightbulb",
        "score": 0.95,
        "metadata": {
            "entity_id": "light.kitchen",
            "area": "kitchen",
            "attributes": {
                "area_id": "kitchen",
                "brightness": 255,
            },
        },
    }
    assert isinstance(payload["data"]["execution_time_ms"], float)
    assert payload["data"]["execution_time_ms"] >= 0.0

    response = client.get("/api/v1/search/entities?domain=light&state=on&area=kitchen&limit=10")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "results": [
                {
                    "id": "light.kitchen",
                    "title": "Kitchen Light",
                    "subtitle": "light • on",
                    "domain": "light",
                    "state": "on",
                    "icon": "mdi:lightbulb",
                    "metadata": {
                        "attributes": {
                            "area_id": "kitchen",
                            "brightness": 255,
                        }
                    },
                }
            ],
            "count": 1,
        },
    }

    response = client.get("/api/v1/search/stats")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "entities": 2,
            "automations": 1,
            "scripts": 1,
            "scenes": 1,
            "services": 1,
            "domains": {"light": 1, "sensor": 1},
        },
    }


def test_search_contract_hardens_auth_validation_and_runtime_errors(monkeypatch) -> None:
    client, _engine = _build_client(monkeypatch, authorized=False)

    response = client.get("/api/v1/search?q=kitchen")
    assert response.status_code == 401
    assert response.get_json() == {
        "error": "unauthorized",
        "message": "Valid X-Auth-Token or Bearer token required",
    }

    client, _engine = _build_client(monkeypatch)

    response = client.get("/api/v1/search")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Query parameter 'q' is required",
    }

    response = client.get("/api/v1/search?q=kitchen&limit=0")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "limit must be a positive integer <= 100",
    }

    response = client.get("/api/v1/search?q=kitchen&limit=bad")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "limit must be a positive integer <= 100",
    }

    response = client.get("/api/v1/search?q=kitchen&types=entity,unknown")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "invalid search types: unknown; allowed: automation, entity, scene, script, service",
    }

    response = client.get("/api/v1/search/entities?limit=201")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "limit must be a positive integer <= 200",
    }

    response = client.post("/api/v1/search/index", data="not-json", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Request body must be valid JSON",
    }

    response = client.post("/api/v1/search/index", json=[])
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Request body must be a JSON object",
    }

    response = client.post("/api/v1/search/index", json={"entities": []})
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Field 'entities' must be an object",
    }

    engine = FakeEngine()
    client, _ = _build_client(monkeypatch, engine=engine)

    engine.raise_on = "search"
    response = client.get("/api/v1/search?q=kitchen")
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "search exploded",
    }

    engine.raise_on = "filter_entities"
    response = client.get("/api/v1/search/entities")
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "filter exploded",
    }

    engine.raise_on = "get_stats"
    response = client.get("/api/v1/search/stats")
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "stats exploded",
    }

    engine.raise_on = "update_entities"
    response = client.post("/api/v1/search/index", json={"entities": {"light.kitchen": {}}})
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "entities exploded",
    }
