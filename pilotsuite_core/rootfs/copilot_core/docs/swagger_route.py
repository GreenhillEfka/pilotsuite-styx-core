"""
Swagger Route - API Documentation Endpoint

Provides Swagger UI at /docs for interactive API exploration.
Loads OpenAPI spec from /api/v1/openapi.json endpoint.

This is a lightweight alternative to the full swagger_ui blueprint.
Use this if you want a simple, standalone Swagger UI route.
"""

from flask import Blueprint, Response, redirect

bp = Blueprint("swagger_docs", __name__, url_prefix="/docs")


@bp.get("/")
def swagger_ui():
    """Serve Swagger UI HTML with CDN resources."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PilotSuite Styx Core API - Swagger UI</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css">
    <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5.11.0/favicon-32x32.png">
    <style>
        html { box-sizing: border-box; overflow-y: scroll; }
        *, *:before, *:after { box-sizing: inherit; }
        body { margin: 0; background: #fafafa; }
        .swagger-ui .topbar { display: none; }
        .swagger-ui .info { margin: 20px 0; }
        .swagger-ui .info .title { font-size: 2.5em; color: #3b4151; }
        .swagger-ui .info .description { font-size: 1.1em; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    
    <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js"></script>
    
    <script>
        window.onload = function() {
            const ui = SwaggerUIBundle({
                url: '/api/v1/openapi.json',
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
                },
                validatorUrl: null,
                tryItOutEnabled: true,
                requestInterceptor: function(request) {
                    // Add auth token if available
                    const token = localStorage.getItem('pilotsuite_api_key');
                    if (token) {
                        request.headers['X-API-Key'] = token;
                    }
                    return request;
                },
                onComplete: function() {
                    console.log('Swagger UI loaded successfully');
                }
            });
            
            window.ui = ui;
        };
    </script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@bp.get("/openapi.json")
def openapi_json_redirect():
    """Redirect to actual OpenAPI JSON endpoint."""
    from flask import redirect
    return redirect("/api/v1/openapi.json")


@bp.get("/openapi.yaml")
def openapi_yaml_redirect():
    """Redirect to actual OpenAPI YAML endpoint."""
    from flask import redirect
    return redirect("/api/v1/openapi.yaml")
