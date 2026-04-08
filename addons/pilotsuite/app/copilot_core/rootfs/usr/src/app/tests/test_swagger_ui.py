"""
Tests for Swagger UI API Documentation
"""

import pytest
from flask import Flask

from copilot_core.api.v1.swagger_ui import bp as swagger_ui_bp


@pytest.fixture
def app():
    """Create test app with swagger_ui blueprint."""
    app = Flask(__name__)
    app.register_blueprint(swagger_ui_bp, url_prefix="/api/v1/docs")
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestSwaggerUI:
    """Test Swagger UI endpoints."""

    def test_swagger_ui_returns_html(self, client):
        """Test that / returns HTML."""
        response = client.get("/api/v1/docs/")
        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data
        assert b"swagger-ui" in response.data
        assert b"SwaggerUIBundle" in response.data

    def test_openapi_yaml_endpoint_exists(self, client):
        """Test that openapi.yaml endpoint exists."""
        response = client.get("/api/v1/docs/openapi.yaml")
        assert response.status_code == 200
        # Should return YAML content
        assert response.content_type in ["text/yaml", "text/yaml; charset=utf-8"]

    def test_openapi_json_endpoint_exists(self, client):
        """Test that openapi.json endpoint exists."""
        response = client.get("/api/v1/docs/openapi.json")
        assert response.status_code == 200
        # Should return JSON content
        assert response.content_type in ["application/json", "application/json; charset=utf-8"]

    def test_validate_endpoint_exists(self, client):
        """Test that validate endpoint exists."""
        response = client.get("/api/v1/docs/validate")
        assert response.status_code == 200
        # Should return JSON
        assert response.content_type in ["application/json", "application/json; charset=utf-8"]

    def test_swagger_ui_has_correct_title(self, client):
        """Test that Swagger UI HTML has correct title."""
        response = client.get("/api/v1/docs/")
        assert b"PilotSuite API Documentation" in response.data

    def test_swagger_ui_loads_from_correct_url(self, client):
        """Test that Swagger UI loads spec from correct URL."""
        response = client.get("/api/v1/docs/")
        html = response.data.decode("utf-8")
        assert "/api/v1/docs/openapi.yaml" in html