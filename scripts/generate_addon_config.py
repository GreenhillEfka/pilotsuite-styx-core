"""PilotSuite Core Add-on Configuration (v15.5.0 Gold).

Required for the Home Assistant Add-on Store.
"""

import json
import os

ADDON_CONFIG = {
    "name": "PilotSuite Core",
    "version": "15.5.0",
    "slug": "pilotsuite_core",
    "description": "Autonomous, self-healing smart home core with SOTA AI.",
    "arch": ["aarch64", "amd64", "armhf", "armv7", "i386"],
    "boot": "auto",
    "startup": "system",
    "webui": "http://[HOST]:[PORT:5000]/admin",
    "ingress": True,
    "ingress_port": 5000,
    "panel_icon": "mdi:brain",
    "options": {
        "log_level": "info",
        "db_url": "sqlite:////config/data/pilotsuite_platinum.db"
    },
    "schema": {
        "log_level": "list(none|fatal|error|warning|info|debug|trace)?",
        "db_url": "str?"
    }
}

# Write to disk
with open("/config/clawd/team/worktrees/pilotsuite-styx-core-current/copilot_core/rootfs/usr/src/app/config.json", "w") as f:
    json.dump(ADDON_CONFIG, f, indent=2)
