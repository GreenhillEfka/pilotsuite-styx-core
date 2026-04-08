"""Basic integration tests for the tag-system API blueprint."""
from __future__ import annotations

import os
from pathlib import Path
import sys

try:  # pragma: no cover - dev envs without Flask should skip gracefully
    import flask  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - fallback when deps missing
    print("SKIP: Flask not installed; tag-system API tests skipped")
    raise SystemExit(0)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import app


def test_list_tags_endpoint():
    client = app.test_client()
    response = client.get("/api/v1/tags?lang=en")
    assert response.status_code == 200
    payload = response.get_json()
    assert "tags" in payload
    assert isinstance(payload["tags"], list)


def test_assignments_crud_flow():
    client = app.test_client()
    # List assignments (initially empty)
    response = client.get("/api/v1/assignments")
    assert response.status_code == 200
    payload = response.get_json()
    assert "assignments" in payload
    assert isinstance(payload["assignments"], list)
