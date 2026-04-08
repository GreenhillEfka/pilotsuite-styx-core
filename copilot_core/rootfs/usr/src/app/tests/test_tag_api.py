"""Basic integration tests for the tag-system API blueprint."""
from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

try:  # pragma: no cover - dev envs without Flask should skip gracefully
    from flask import Flask
except ModuleNotFoundError:  # pragma: no cover - fallback when deps missing
    Flask = None


@pytest.fixture
def tag_app():
    """Create a test app with the tag-system blueprint registered."""
    if Flask is None:
        pytest.skip("Flask not installed")
    from copilot_core.api.v1.tag_system import bp as tag_bp
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(tag_bp)
    return app


def test_list_tags_endpoint(tag_app):
    client = tag_app.test_client()
    response = client.get("/api/v1/tag-system/tags?lang=en")
    assert response.status_code == 200
    payload = response.get_json()
    assert "tags" in payload
    assert isinstance(payload["tags"], list)


def test_assignments_crud_flow(tag_app):
    client = tag_app.test_client()
    # List assignments (initially empty)
    response = client.get("/api/v1/tag-system/assignments")
    assert response.status_code == 200
    payload = response.get_json()
    assert "assignments" in payload
    assert isinstance(payload["assignments"], list)
