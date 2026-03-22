#!/usr/bin/env python3
"""PilotSuite E2E Health Check — full system status."""
import json, sys, urllib.request, urllib.error

HA_TOKEN_FILE = "/config/secrets/homeassistant.token"
CORE_BASE = "http://localhost:8909"

def get(path):
    try:
        r = urllib.request.urlopen(CORE_BASE + path, timeout=5)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": str(e)}

def ha_get(path):
    try:
        with open(HA_TOKEN_FILE) as f:
            token = f.read().strip()
        req = urllib.request.Request(
            CORE_BASE.replace("localhost:8909","192.168.30.18:8123") + path,
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

checks = {
    "core_styx_dashboard": get("/styx"),
    "core_zones": get("/api/v1/zones"),
    "core_modules": get("/api/v1/modules"),
    "ha_integration_state": ha_get("/api/config/config_entries/entry"),
}

# Parse HA integration state
ha_state = checks.get("ha_integration_state", {})
if isinstance(ha_state, list):
    for e in ha_state:
        if e.get("domain") == "copilot_ha":
            checks["ha_integration_loaded"] = e.get("state") == "loaded"
            checks["ha_integration_state"] = e.get("state")

print(json.dumps(checks, indent=2, default=str))
sys.exit(0 if checks.get("ha_integration_loaded", False) else 1)
