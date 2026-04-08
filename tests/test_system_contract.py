from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pilotsuite_core" / "rootfs" / "usr" / "src" / "app"))

from main import create_app


def test_health_and_version_endpoints_expose_runtime_manifest_version():
    app = create_app({"TESTING": True, "APP_VERSION": "20.0.0-test"})
    client = app.test_client()

    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json() == {"status": "ok", "service": "pilotsuite-core"}

    version = client.get("/version")
    assert version.status_code == 200
    assert version.get_json() == {
        "name": "Styx",
        "suite": "PilotSuite",
        "version": "20.0.0-test",
    }
