# Swagger UI Documentation

This directory contains the Swagger UI integration for the PilotSuite Styx Core API.

## Files

- `index.html` - Swagger UI HTML interface
- `swagger-ui-bundle.js` - Swagger UI JavaScript bundle (stub, uses CDN)
- `swagger-ui.css` - Referenced from CDN

## Quick Start

### 1. Access Swagger UI

Once the Flask app is running with the Swagger route registered:

```
http://localhost:8909/docs
```

### 2. Register the Swagger Route

Add this to your Flask application:

```python
from copilot_core.docs.swagger_route import register_swagger_ui

# After creating your Flask app
register_swagger_ui(app)
```

### 3. Alternative: Manual Registration

```python
from copilot_core.docs.swagger_route import bp as swagger_bp

app.register_blueprint(swagger_bp)
```

## Features

✅ **Interactive API Documentation**
- Try-It-Out functionality for all 60+ endpoints
- Request/Response examples
- Schema validation

✅ **Authentication Support**
- API Key (X-API-Key header)
- Bearer Token (Authorization header)
- Persistent auth in browser session

✅ **OpenAPI Spec**
- YAML format: `/docs/openapi.yaml`
- JSON format: `/docs/openapi.json`
- Validation endpoint: `/docs/validate`

✅ **Modern UI**
- Responsive design
- Syntax highlighting
- Search/filter capabilities
- Collapsible sections

## Configuration

### Customizing the OpenAPI Spec Location

The Swagger route looks for the OpenAPI spec in these locations (in order):

1. `/usr/src/app/docs/openapi.yaml`
2. `/data/openapi.yaml`
3. `../../docs/openapi.yaml` (relative to swagger_route.py)
4. `/config/.openclaw/workspace/pilotsuite-styx-core/docs/openapi.yaml`

### Offline Usage

For offline/air-gapped environments:

1. Download the Swagger UI assets:
   ```bash
   wget https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js
   wget https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js
   wget https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css
   ```

2. Place them in the `docs/swagger/` directory

3. Update `index.html` to reference local files:
   ```html
   <link rel="stylesheet" href="./swagger-ui.css">
   <script src="./swagger-ui-bundle.js"></script>
   <script src="./swagger-ui-standalone-preset.js"></script>
   ```

## API Key Management

The Swagger UI includes a built-in API Key input field:

1. Enter your API Key in the input field at the top
2. Click "Save Key"
3. The key is stored in localStorage and automatically included in all requests

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/docs` | GET | Swagger UI HTML interface |
| `/docs/openapi.yaml` | GET | OpenAPI specification (YAML) |
| `/docs/openapi.json` | GET | OpenAPI specification (JSON) |
| `/docs/validate` | GET | Validate OpenAPI spec |

## Troubleshooting

### "OpenAPI spec not found"

Ensure `docs/openapi.yaml` exists in one of the configured paths.

Run validation:
```bash
curl http://localhost:8909/docs/validate
```

### Swagger UI not loading

Check browser console for errors. Ensure:
- CDN is accessible (or local files exist)
- Flask app is running
- Route is properly registered

### Authentication not working

Verify:
- API Key is correct
- Key is saved (check localStorage)
- Endpoint requires the auth method you're using

## Security Notes

⚠️ **Production Deployment:**

1. **Enable HTTPS** - Always serve Swagger UI over HTTPS in production
2. **Restrict Access** - Use middleware to limit access to authorized users
3. **Disable in Production** - Consider disabling Swagger UI in production environments

Example middleware:
```python
@app.before_request
def check_swagger_auth():
    if request.path.startswith('/docs'):
        if not request.headers.get('X-Admin-Key'):
            return jsonify({"error": "Unauthorized"}), 403
```

## Integration with Home Assistant

When running as a Home Assistant add-on:

1. Swagger UI is accessible at: `http://homeassistant.local:8909/docs`
2. Ensure port 8909 is exposed in the add-on configuration
3. Consider adding ingress support for Home Assistant sidebar integration

## Development

### Testing Changes

1. Modify `index.html` or `swagger_route.py`
2. Restart the Flask application
3. Hard-refresh browser (Ctrl+Shift+R)
4. Check `/docs/validate` for spec status

### Updating Swagger UI Version

Update CDN links in `index.html`:
```html
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.17.0/swagger-ui.css">
<script src="https://unpkg.com/swagger-ui-dist@5.17.0/swagger-ui-bundle.js"></script>
```

## Related Documentation

- Complete API Reference: `docs/API_COMPLETE.md`
- OpenAPI Specification: `docs/openapi.yaml`
- Architecture Overview: `docs/ARCHITECTURE.md`

## Support

- GitHub Issues: https://github.com/GreenhillEfka/pilotsuite-styx-core/issues
- Documentation: `/docs` directory
