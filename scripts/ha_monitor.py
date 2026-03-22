#!/usr/bin/env python3
"""HA Integration Monitor — checks if Copilot-HA is loaded and sensors exist."""
import json, sys, urllib.request

HA_URL = "http://192.168.30.18:8123"
TOKEN_FILE = "/config/secrets/homeassistant.token"

def get_token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except:
        return None

def check_ha():
    token = get_token()
    if not token:
        return {"ok": False, "error": "No HA token"}
    
    req = urllib.request.Request(
        f"{HA_URL}/api/config/config_entries/entry",
        headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            entries = json.loads(r.read())
            for e in entries:
                if e.get("domain") == "copilot_ha":
                    state = e.get("state", "unknown")
                    entry_id = e.get("entry_id", "")
                    return {
                        "ok": True,
                        "state": state,
                        "entry_id": entry_id,
                        "loaded": state == "loaded",
                        "needs_reload": state == "not_loaded"
                    }
            return {"ok": False, "error": "copilot_ha not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    result = check_ha()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("loaded") else 1)
