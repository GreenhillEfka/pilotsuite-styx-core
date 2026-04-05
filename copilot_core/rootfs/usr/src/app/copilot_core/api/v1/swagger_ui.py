"""
Swagger UI Blueprint - Interactive API Documentation (v2.0).

Provides Swagger UI at /docs for interactive API exploration.
Serves the OpenAPI spec from /api/v1/openapi.json endpoint.
Auto-detects Ingress base path for HA Add-on usage.

Erreichbar unter:
  - Direkt:  http://<host>:8909/api/v1/docs/
  - Ingress: http://<ha>/api/hassio_ingress/<slug>/api/v1/docs/
"""

import os
import time
from flask import Blueprint, jsonify, Response, request, current_app

bp = Blueprint("swagger_ui", __name__, url_prefix="/docs")

# Separate blueprint for /api/v1/openapi.json endpoint
openapi_bp = Blueprint("openapi_spec", __name__)

OPENAPI_SEARCH_PATHS = [
    "/usr/src/app/docs/openapi.yaml",
    "/usr/src/app/copilot_core/docs/openapi.yaml",
    "/data/openapi.yaml",
]

_spec_cache: tuple[str, float] | None = None
_CACHE_TTL = 300  # 5 min


def _get_openapi_spec() -> str:
    """Load OpenAPI spec from file (cached)."""
    global _spec_cache
    now = time.monotonic()
    if _spec_cache and (now - _spec_cache[1]) < _CACHE_TTL:
        return _spec_cache[0]
    try:
        for path in OPENAPI_SEARCH_PATHS:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    spec = f.read()
                    _spec_cache = (spec, now)
                    return spec

        # Try relative path from this file
        rel_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "..", "docs", "openapi.yaml",
        )
        if os.path.exists(rel_path):
            with open(rel_path, "r", encoding="utf-8") as f:
                spec = f.read()
                _spec_cache = (spec, now)
                return spec
    except Exception:
        pass
    return ""


def _detect_base_path() -> str:
    """Detect Ingress or direct base path from request URL."""
    # Check X-Ingress-Path header (set by HA Ingress proxy)
    ingress = request.headers.get("X-Ingress-Path", "")
    if ingress:
        return ingress.rstrip("/")
    # Fallback: extract from request path
    path = request.path
    idx = path.find("/api/v1/docs")
    if idx > 0:
        return path[:idx]
    return ""


@openapi_bp.get("/")
def swagger_ui():
    """Serve Swagger UI HTML with auto-detected base path."""
    base = _detect_base_path()
    spec_url = f"{base}/api/v1/docs/openapi.json"
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PilotSuite API Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui.css">
    <style>
        html {{ box-sizing: border-box; overflow-y: scroll; }}
        *, *:before, *:after {{ box-sizing: inherit; }}
        body {{ margin:0; padding:0; background: #1a1a2e; color: #e0e0e0; }}
        .swagger-ui .topbar {{ background: #16213e; padding: 8px 16px; }}
        .swagger-ui .topbar .download-url-wrapper {{ display: flex; align-items: center; }}
        .swagger-ui .info hgroup.main a {{ color: #7c6aef; }}
        .swagger-ui .info .title {{ color: #e0e0e0; }}
        .swagger-ui .info .description p {{ color: #b0b0b0; }}
        .swagger-ui .scheme-container {{ background: #16213e; }}
        .swagger-ui .opblock-tag {{ color: #e0e0e0; border-bottom-color: #333; }}
        .swagger-ui section.models {{ border-color: #333; }}
        .swagger-ui .model-title {{ color: #e0e0e0; }}
        .swagger-ui .btn {{ color: #e0e0e0; }}
        .swagger-ui select {{ color: #333; }}
    </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
<script src="https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui-standalone-preset.js"></script>
<script>
window.onload = function() {{
    SwaggerUIBundle({{
        url: "{spec_url}",
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
        syntaxHighlight: {{
            activate: true,
            theme: "monokai"
        }},
        validatorUrl: null,
        tryItOutEnabled: true,
        persistAuthorization: true,
        requestInterceptor: function(req) {{
            // Auto-prepend Ingress base path if needed
            var base = "{base}";
            if (base && req.url.startsWith("/api/")) {{
                req.url = base + req.url;
            }}
            return req;
        }}
    }})
}}
</script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@openapi_bp.get("/openapi.yaml")
def openapi_spec():
    """Serve OpenAPI YAML spec."""
    spec = _get_openapi_spec()
    if not spec:
        # Generate minimal inline spec if file not found
        spec = _generate_inline_spec()
    return Response(spec, mimetype="text/yaml")


@openapi_bp.get("/openapi.json")
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


# Additional endpoint for spec validation + enriched info
@openapi_bp.get("/validate")
def validate_spec():
    """Validate OpenAPI spec and return enriched status."""
    import yaml
    spec = _get_openapi_spec()
    if not spec:
        return jsonify({
            "ok": False,
            "error": "OpenAPI spec not found",
            "checked_paths": OPENAPI_SEARCH_PATHS,
            "hint": "Place openapi.yaml in one of the checked paths",
        })
    try:
        spec_dict = yaml.safe_load(spec)
        paths = spec_dict.get("paths", {})
        tags = spec_dict.get("tags", [])

        # Count methods per tag
        methods_by_tag: dict[str, int] = {}
        total_operations = 0
        for _path, methods in paths.items():
            for method, op in methods.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    total_operations += 1
                    for tag in op.get("tags", ["untagged"]):
                        methods_by_tag[tag] = methods_by_tag.get(tag, 0) + 1

        return jsonify({
            "ok": True,
            "version": spec_dict.get("info", {}).get("version", "unknown"),
            "title": spec_dict.get("info", {}).get("title", "unknown"),
            "path_count": len(paths),
            "operation_count": total_operations,
            "tag_count": len(tags),
            "tags": [t.get("name", "") for t in tags],
            "operations_by_tag": methods_by_tag,
            "servers": spec_dict.get("servers", []),
            "ui_url": "/api/v1/docs/",
            "spec_yaml_url": "/api/v1/docs/openapi.yaml",
            "spec_json_url": "/api/v1/docs/openapi.json",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@openapi_bp.get("/info")
def api_info():
    """Return API metadata and connectivity info."""
    from copilot_core import __version__ as core_version
    import sys

    # Collect registered endpoints from Flask app
    endpoint_count = 0
    blueprint_names = set()
    try:
        for rule in current_app.url_map.iter_rules():
            if rule.endpoint != "static":
                endpoint_count += 1
                parts = rule.endpoint.split(".")
                if len(parts) > 1:
                    blueprint_names.add(parts[0])
    except Exception:
        pass

    return jsonify({
        "ok": True,
        "api": {
            "version": core_version if "core_version" in dir() else "unknown",
            "framework": "Flask",
            "python": sys.version.split()[0],
            "endpoints_registered": endpoint_count,
            "blueprints": sorted(blueprint_names),
        },
        "docs": {
            "swagger_ui": "/api/v1/docs/",
            "openapi_yaml": "/api/v1/docs/openapi.yaml",
            "openapi_json": "/api/v1/docs/openapi.json",
            "validate": "/api/v1/docs/validate",
        },
        "connectivity": {
            "core_port": int(os.environ.get("PORT", 8909)),
            "ollama_port": int(os.environ.get("OLLAMA_PORT", 11435)),
            "ingress": bool(os.environ.get("INGRESS_ENTRY")),
        },
    })


# ============================================================================
# OpenAPI Spec Endpoints (for /api/v1/openapi.json and /api/v1/openapi.yaml)
# ============================================================================

@openapi_bp.get("/openapi.json")
def openapi_json_endpoint():
    """Serve OpenAPI JSON spec at /api/v1/openapi.json."""
    import yaml
    spec = _get_openapi_spec()
    if not spec:
        spec = _generate_inline_spec()
    try:
        spec_dict = yaml.safe_load(spec)
        return jsonify(spec_dict)
    except Exception:
        return Response(spec, mimetype="application/json")


@openapi_bp.get("/openapi.yaml")
def openapi_yaml_endpoint():
    """Serve OpenAPI YAML spec at /api/v1/openapi.yaml."""
    spec = _get_openapi_spec()
    if not spec:
        spec = _generate_inline_spec()
    return Response(spec, mimetype="text/yaml")