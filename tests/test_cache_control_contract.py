from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
MODULE_PATH = CORE_APP_ROOT / "copilot_core" / "api" / "v1" / "cache_control.py"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import security as api_security_module  # noqa: E402

spec = importlib.util.spec_from_file_location("ps_cache_control_contract_module", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeRedisClient:
    def __init__(self, *, connected: bool = True) -> None:
        self.is_connected = connected
        self.host = "redis.local"
        self.port = 6379
        self.raise_on_connect = False

    async def connect(self):
        if self.raise_on_connect:
            raise RuntimeError("connect exploded")
        return True


class FakeAPICache:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.invalidated_keys: list[str] = []
        self.invalidated_patterns: list[str] = []
        self.invalidate_all_calls = 0
        self.invalidate_entities_calls = 0
        self.invalidate_states_calls = 0

    async def invalidate_all(self):
        if self.raise_on == "invalidate_all":
            raise RuntimeError("invalidate all exploded")
        self.invalidate_all_calls += 1
        return True

    async def invalidate(self, key: str):
        if self.raise_on == "invalidate":
            raise RuntimeError("invalidate key exploded")
        self.invalidated_keys.append(key)
        return key != "missing:key"

    async def invalidate_pattern(self, pattern: str):
        if self.raise_on == "invalidate_pattern":
            raise RuntimeError("invalidate pattern exploded")
        self.invalidated_patterns.append(pattern)
        return 4

    async def invalidate_entities(self):
        if self.raise_on == "invalidate_entities":
            raise RuntimeError("invalidate entities exploded")
        self.invalidate_entities_calls += 1
        return 3

    async def invalidate_states(self):
        if self.raise_on == "invalidate_states":
            raise RuntimeError("invalidate states exploded")
        self.invalidate_states_calls += 1
        return 2

    async def get_stats(self):
        if self.raise_on == "get_stats":
            raise RuntimeError("stats exploded")
        return {
            "hits": 8,
            "misses": 2,
            "total": 10,
            "hit_ratio": 0.8,
        }


def _build_client(monkeypatch, *, authorized: bool = True, redis_client=None, cache=None):
    monkeypatch.setattr(api_security_module, "validate_token", lambda _request: authorized)
    monkeypatch.setattr(module, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(module, "get_api_cache", lambda: cache)

    app = Flask(__name__)
    app.register_blueprint(module.cache_control_bp, url_prefix="/api/v1/cache")
    return app.test_client()


def test_cache_control_contract_covers_all_routes(monkeypatch) -> None:
    redis_client = FakeRedisClient(connected=False)
    cache = FakeAPICache()
    client = _build_client(monkeypatch, redis_client=redis_client, cache=cache)

    response = client.get("/api/v1/cache/status")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "connected": False,
            "host": "redis.local",
            "port": 6379,
            "using_fallback": True,
            "redis_available": False,
        },
    }

    response = client.post("/api/v1/cache/invalidate")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "invalidated_entities": 3,
            "invalidated_states": 2,
            "total": 5,
        },
    }
    assert cache.invalidate_entities_calls == 1
    assert cache.invalidate_states_calls == 1

    response = client.post("/api/v1/cache/invalidate", json={"all": True})
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "invalidated": "all",
            "message": "All cache entries cleared",
        },
    }
    assert cache.invalidate_all_calls == 1

    response = client.post("/api/v1/cache/invalidate", json={"key": "entity:kitchen"})
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "key": "entity:kitchen",
            "invalidated": True,
        },
    }
    assert cache.invalidated_keys == ["entity:kitchen"]

    response = client.post("/api/v1/cache/invalidate", json={"key": "missing:key"})
    assert response.status_code == 404
    assert response.get_json() == {
        "success": False,
        "data": {
            "key": "missing:key",
            "invalidated": False,
        },
    }

    response = client.post("/api/v1/cache/invalidate", json={"pattern": "entity:*"})
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "pattern": "entity:*",
            "invalidated_count": 4,
        },
    }
    assert cache.invalidated_patterns == ["entity:*"]

    response = client.get("/api/v1/cache/stats")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "hits": 8,
            "misses": 2,
            "total": 10,
            "hit_ratio": 0.8,
        },
    }


def test_cache_control_contract_hardens_uninitialized_validation_and_runtime_errors(monkeypatch) -> None:
    client = _build_client(monkeypatch, redis_client=None, cache=None)

    response = client.get("/api/v1/cache/status")
    assert response.status_code == 503
    assert response.get_json() == {"success": False, "error": "cache client not initialized"}

    response = client.post("/api/v1/cache/invalidate")
    assert response.status_code == 503
    assert response.get_json() == {"success": False, "error": "cache not initialized"}

    response = client.get("/api/v1/cache/stats")
    assert response.status_code == 503
    assert response.get_json() == {"success": False, "error": "cache not initialized"}

    redis_client = FakeRedisClient()
    cache = FakeAPICache()
    client = _build_client(monkeypatch, redis_client=redis_client, cache=cache)

    response = client.post("/api/v1/cache/invalidate", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "JSON object required"}

    response = client.post("/api/v1/cache/invalidate", json={"all": "yes"})
    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "all must be a boolean"}

    response = client.post("/api/v1/cache/invalidate", json={"key": 7})
    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "key must be a non-empty string"}

    response = client.post("/api/v1/cache/invalidate", json={"key": "   "})
    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "key must be a non-empty string"}

    response = client.post("/api/v1/cache/invalidate", json={"pattern": []})
    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "pattern must be a non-empty string"}

    response = client.post("/api/v1/cache/invalidate", json={"pattern": ""})
    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "pattern must be a non-empty string"}

    monkeypatch.setattr(module, "get_redis_client", lambda: (_ for _ in ()).throw(RuntimeError("status exploded")))
    response = client.get("/api/v1/cache/status")
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "status exploded"}

    monkeypatch.setattr(module, "get_redis_client", lambda: redis_client)

    cache.raise_on = "invalidate_all"
    response = client.post("/api/v1/cache/invalidate", json={"all": True})
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "invalidate all exploded"}

    cache.raise_on = "get_stats"
    response = client.get("/api/v1/cache/stats")
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "stats exploded"}


def test_cache_control_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(
        monkeypatch,
        authorized=False,
        redis_client=FakeRedisClient(),
        cache=FakeAPICache(),
    )

    response = client.get("/api/v1/cache/status")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }
