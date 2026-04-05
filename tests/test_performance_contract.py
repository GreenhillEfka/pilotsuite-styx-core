from __future__ import annotations

import sys
import types
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import performance as module  # noqa: E402


class ExplodingTracker:
    def __init__(self, target: str, message: str) -> None:
        self.target = target
        self.message = message

    def _explode(self, name: str):
        if self.target == name:
            raise RuntimeError(self.message)

    def get_startup_metrics(self):
        self._explode("startup")
        return module.StartupMetrics(
            total_startup_time_ms=2400.0,
            lazy_load_enabled=True,
            modules_loaded_count=1,
            modules_deferred_count=0,
            target_startup_time_ms=2000.0,
            actual_startup_time_ms=2400.0,
            performance_achieved=False,
        )

    def get_module_metrics(self):
        self._explode("modules")
        return []

    def get_summary(self):
        self._explode("summary")
        return {}


class FakeLoader:
    def __init__(self, load_time_ms: float, *, should_raise: bool = False) -> None:
        self.metrics = types.SimpleNamespace(load_time_ms=load_time_ms)
        self._should_raise = should_raise

    def load(self) -> None:
        if self._should_raise:
            raise RuntimeError("benchmark exploded")


def _install_fake_lazy_loader(monkeypatch, *, enabled: bool = True, should_raise: bool = False) -> None:
    fake_module = types.ModuleType("copilot_core.utils.lazy_loader")

    class FakeLazyLoader:
        @staticmethod
        def is_enabled() -> bool:
            if should_raise:
                raise RuntimeError("lazy loader exploded")
            return enabled

        @staticmethod
        def reset_all() -> None:
            if should_raise:
                raise RuntimeError("benchmark exploded")

    fake_module.LazyLoader = FakeLazyLoader
    fake_module.energy_service_loader = FakeLoader(11.5, should_raise=should_raise)
    fake_module.ml_transformer_loader = FakeLoader(22.0, should_raise=should_raise)
    fake_module.proactive_engine_loader = FakeLoader(33.5, should_raise=should_raise)
    monkeypatch.setitem(sys.modules, "copilot_core.utils.lazy_loader", fake_module)


def _build_client(monkeypatch, *, tracker=None) -> Flask.test_client:
    if tracker is None:
        tracker = module.init_performance_api()
    else:
        module.init_performance_api(tracker)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(module.performance_bp, url_prefix="/api/v1")
    return app.test_client()


def test_performance_contract_covers_all_routes(monkeypatch) -> None:
    tracker = module.init_performance_api()
    tracker._startup_metrics = module.StartupMetrics(
        total_startup_time_ms=1450.5,
        lazy_load_enabled=True,
        modules_loaded_count=2,
        modules_deferred_count=3,
        target_startup_time_ms=2000.0,
        actual_startup_time_ms=1450.5,
        performance_achieved=True,
    )
    tracker._module_metrics = {
        "energy": module.ModuleMetrics(
            name="energy",
            load_time_ms=12.5,
            memory_delta_mb=1.25,
            loaded_at=1712345678.0,
            accessed_count=3,
            is_lazy_loaded=True,
        ),
        "speech": module.ModuleMetrics(
            name="speech",
            load_time_ms=7.5,
            memory_delta_mb=0.5,
            loaded_at=1712345688.0,
            accessed_count=1,
            is_lazy_loaded=False,
        ),
    }

    _install_fake_lazy_loader(monkeypatch, enabled=True)
    client = _build_client(monkeypatch, tracker=tracker)

    response = client.get("/api/v1/performance/startup")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "metrics": {
            "total_startup_time_ms": 1450.5,
            "lazy_load_enabled": True,
            "modules_loaded_count": 2,
            "modules_deferred_count": 3,
            "target_startup_time_ms": 2000.0,
            "actual_startup_time_ms": 1450.5,
            "performance_achieved": True,
        },
    }

    response = client.get("/api/v1/performance/modules")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "count": 2,
        "modules": [
            {
                "name": "energy",
                "load_time_ms": 12.5,
                "memory_delta_mb": 1.25,
                "loaded_at": 1712345678.0,
                "accessed_count": 3,
                "is_lazy_loaded": True,
            },
            {
                "name": "speech",
                "load_time_ms": 7.5,
                "memory_delta_mb": 0.5,
                "loaded_at": 1712345688.0,
                "accessed_count": 1,
                "is_lazy_loaded": False,
            },
        ],
    }

    response = client.get("/api/v1/performance/modules?lazy_only=true")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "count": 1,
        "modules": [
            {
                "name": "energy",
                "load_time_ms": 12.5,
                "memory_delta_mb": 1.25,
                "loaded_at": 1712345678.0,
                "accessed_count": 3,
                "is_lazy_loaded": True,
            }
        ],
    }

    response = client.get("/api/v1/performance/summary")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "summary": {
            "startup": {
                "total_startup_time_ms": 1450.5,
                "lazy_load_enabled": True,
                "modules_loaded_count": 2,
                "modules_deferred_count": 3,
                "target_startup_time_ms": 2000.0,
                "actual_startup_time_ms": 1450.5,
                "performance_achieved": True,
            },
            "modules": {
                "total_count": 2,
                "lazy_loaded_count": 1,
                "eager_loaded_count": 1,
                "total_load_time_ms": 20.0,
                "total_memory_mb": 1.75,
            },
            "performance": {
                "startup_target_met": True,
                "startup_time_ms": 1450.5,
                "startup_target_ms": 2000.0,
                "improvement_vs_eager": {
                    "estimated_eager_time_ms": 1463.0,
                    "actual_lazy_time_ms": 1450.5,
                    "time_saved_ms": 12.5,
                    "improvement_percent": 0.85,
                },
            },
        },
    }

    response = client.get("/api/v1/performance/lazy-load/status")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "lazy_load": {
            "enabled": True,
            "modules_registered": 2,
            "modules_loaded": 1,
            "modules_still_deferred": 1,
            "total_accesses": 4,
            "total_load_time_ms": 20.0,
            "total_memory_mb": 1.75,
        },
    }

    response = client.post("/api/v1/performance/benchmark", json={"iterations": 3, "include_modules": True})
    assert response.status_code == 200
    benchmark = response.get_json()
    assert benchmark["success"] is True
    assert benchmark["benchmark"]["iterations"] == 3
    assert benchmark["benchmark"]["target_ms"] == 2000.0
    assert benchmark["benchmark"]["startup"]["min_ms"] >= 0
    assert benchmark["benchmark"]["startup"]["max_ms"] >= benchmark["benchmark"]["startup"]["min_ms"]

    response = client.get("/api/v1/performance/health")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "health": {
            "status": "healthy",
            "startup_time_ms": 1450.5,
            "target_ms": 2000.0,
            "target_met": True,
            "issues": [],
        },
    }


def test_performance_contract_hardens_validation_and_runtime_errors(monkeypatch) -> None:
    _install_fake_lazy_loader(monkeypatch, enabled=True)
    client = _build_client(monkeypatch)

    response = client.get("/api/v1/performance/modules?lazy_only=maybe")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "lazy_only must be 'true' or 'false'",
    }

    response = client.post("/api/v1/performance/benchmark", json=[])
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "JSON body must be an object",
    }

    response = client.post("/api/v1/performance/benchmark", json={"iterations": True})
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "iterations must be a positive integer",
    }

    response = client.post("/api/v1/performance/benchmark", json={"iterations": 0})
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "iterations must be a positive integer",
    }

    response = client.post("/api/v1/performance/benchmark", json={"iterations": "3"})
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "iterations must be a positive integer",
    }

    response = client.post("/api/v1/performance/benchmark", json={"include_modules": "yes"})
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "include_modules must be a boolean",
    }

    client = _build_client(monkeypatch, tracker=ExplodingTracker("startup", "startup exploded"))
    response = client.get("/api/v1/performance/startup")
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "startup exploded",
    }

    client = _build_client(monkeypatch, tracker=ExplodingTracker("modules", "modules exploded"))
    response = client.get("/api/v1/performance/modules")
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "modules exploded",
    }

    client = _build_client(monkeypatch, tracker=ExplodingTracker("summary", "summary exploded"))
    response = client.get("/api/v1/performance/summary")
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "summary exploded",
    }

    _install_fake_lazy_loader(monkeypatch, enabled=True, should_raise=True)
    client = _build_client(monkeypatch)
    response = client.get("/api/v1/performance/lazy-load/status")
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "lazy loader exploded",
    }

    response = client.post("/api/v1/performance/benchmark", json={"iterations": 1, "include_modules": True})
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "benchmark exploded",
    }

    client = _build_client(monkeypatch, tracker=ExplodingTracker("startup", "health exploded"))
    response = client.get("/api/v1/performance/health")
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "health exploded",
    }
