"""
Swagger UI Blueprint - Interactive API Documentation

Provides Swagger UI at /api/v1/docs for interactive API exploration.
Serves the OpenAPI spec from docs/openapi.yaml.
"""

import os
from flask import Blueprint, jsonify, Response

bp = Blueprint("swagger_ui", __name__, url_prefix="/docs")

OPENAPI_PATH = "/usr/src/app/docs/openapi.yaml"


def _get_openapi_spec() -> str:
    """Load OpenAPI spec from file."""
    try:
        # Try multiple possible locations
        paths = [
            OPENAPI_PATH,
            "/data/openapi.yaml",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "docs", "openapi.yaml"),
        ]
        for path in paths:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
    except Exception:
        pass
    return ""


@bp.get("/")
def swagger_ui():
    """Serve Swagger UI HTML."""
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PilotSuite API Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css">
    <style>
        html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
        *, *:before, *:after { box-sizing: inherit; }
        body { margin:0; padding:0; background: #fafafa; }
        .swagger-ui .topbar { display: none; }
    </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
<script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js"></script>
<script>
window.onload = function() {
    SwaggerUIBundle({
        url: "/api/v1/docs/openapi.yaml",
        dom_id: '#swagger-ui',
        presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIStandalonePreset
        ],
        layout: "StandaloneLayout",
        deepLinking: true,
        displayOperationId: false,
        displayRequestDuration: true,
        docExpansion: "list",
        filter: true,
        showExtensions: true,
        showCommonExtensions: true,
        syntaxHighlight: {
            activate: true,
            theme: "monokai"
        }
    })
}
</script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@bp.get("/openapi.yaml")
def openapi_spec():
    """Serve OpenAPI YAML spec."""
    spec = _get_openapi_spec()
    if not spec:
        # Generate minimal inline spec if file not found
        spec = _generate_inline_spec()
    return Response(spec, mimetype="text/yaml")


@bp.get("/openapi.json")
def openapi_json():
    """Serve OpenAPI JSON spec (convenience endpoint)."""
    import yaml
    spec = _get_openapi_spec()
    if not spec:
        spec = _generate_inline_spec()
    try:
        spec_dict = yaml.safe_load(spec)
        return jsonify(spec_dict)
    except Exception:
        return Response(spec, mimetype="application/json")


def _generate_inline_spec() -> str:
    """Generate a minimal OpenAPI spec inline if file not found."""
    return """openapi: 3.0.3
info:
  title: PilotSuite API
  version: 0.4.33
  description: |
    Interactive API documentation loaded from external file.
    If you see this, the openapi.yaml file could not be found.
paths:
  /api/v1/docs:
    get:
      summary: Swagger UI
      responses:
        '200':
          description: Swagger UI HTML
"""


# Additional endpoint for spec validation
@bp.get("/validate")
def validate_spec():
    """Validate OpenAPI spec and return status."""
    import yaml
    spec = _get_openapi_spec()
    if not spec:
        return jsonify({
            "ok": False,
            "error": "OpenAPI spec not found",
            "checked_paths": [
                OPENAPI_PATH,
                "/data/openapi.yaml"
            ]
        })
    try:
        spec_dict = yaml.safe_load(spec)
        return jsonify({
            "ok": True,
            "version": spec_dict.get("info", {}).get("version", "unknown"),
            "title": spec_dict.get("info", {}).get("title", "unknown"),
            "path_count": len(spec_dict.get("paths", {})),
            "tag_count": len(spec_dict.get("tags", []))
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        })