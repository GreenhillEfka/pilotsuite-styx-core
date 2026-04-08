from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_contract_inventory_guard_passes_in_light_and_full_mode():
    light = subprocess.run(
        [sys.executable, "scripts/contract_inventory_check.py", "--repo", str(REPO_ROOT), "--light"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert light.returncode == 0, light.stdout + light.stderr

    full = subprocess.run(
        [sys.executable, "scripts/contract_inventory_check.py", "--repo", str(REPO_ROOT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert full.returncode == 0, full.stdout + full.stderr


def test_openapi_inventory_documents_public_paths_and_methods():
    spec = json.loads((REPO_ROOT / "docs" / "openapi.json").read_text())
    paths = spec["paths"]

    assert sorted(paths["/version"].keys()) == ["get"]
    assert sorted(paths["/api/v1/presence"].keys()) == ["get"]
    assert sorted(paths["/api/v1/analytics"].keys()) == ["get"]
    assert sorted(paths["/api/v1/notifications"].keys()) == ["get", "post"]
    assert sorted(paths["/api/v1/notifications/send"].keys()) == ["post"]
    assert sorted(paths["/api/v1/notifications/digest"].keys()) == ["get"]
    assert sorted(paths["/api/v1/notifications/pending"].keys()) == ["get"]
    assert sorted(paths["/api/v1/notifications/stats"].keys()) == ["get"]
    assert sorted(paths["/api/v1/notifications/{notification_id}"].keys()) == ["delete", "parameters"]
    assert sorted(paths["/api/v1/notifications/{notification_id}/read"].keys()) == ["parameters", "post"]
    assert sorted(paths["/api/v1/notifications/subscribe"].keys()) == ["post"]
    assert sorted(paths["/api/v1/notifications/subscriptions"].keys()) == ["get"]
    assert sorted(paths["/api/v1/notifications/subscriptions/{device_id}"].keys()) == ["parameters", "put"]
    assert sorted(paths["/api/v1/notifications/unsubscribe"].keys()) == ["post"]
    assert sorted(paths["/api/v1/zones"].keys()) == ["get"]
    assert sorted(paths["/api/v1/widgets/positions"].keys()) == ["get", "post"]
    assert sorted(paths["/api/v1/widgets/positions/bulk"].keys()) == ["post"]
    assert sorted(paths["/api/v1/widgets/positions/{widget_id}"].keys()) == ["delete", "get", "parameters"]
    assert sorted(paths["/api/v1/widgets/positions/{widget_id}/history"].keys()) == ["post"]
    assert sorted(paths["/api/v1/widgets/positions/{widget_id}/undo"].keys()) == ["post"]
    assert sorted(paths["/api/v1/widgets/positions/{widget_id}/redo"].keys()) == ["post"]
    assert sorted(paths["/api/v1/widgets/positions/reset"].keys()) == ["post"]
