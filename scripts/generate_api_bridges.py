#!/usr/bin/env python3
"""Generate bridge files for all API v1 modules that exist in Runtime but not in Root.

This ensures imports from blueprints_config.py resolve correctly.
"""
from __future__ import annotations

import sys
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent.parent / "copilot_core" / "api" / "v1"
    runtime_root = Path(__file__).resolve().parent.parent / "copilot_core" / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "api" / "v1"
    
    # All modules referenced in blueprints_config.py CORE_API_BLUEPRINTS
    core_blueprints = [
        "health", "metrics", "version", "auth", "users", "zones", "zone_automation",
        "zone_automation_api", "zone_editor", "zone_aggregates", "zone_health",
        "zone_dashboard", "modules", "module_control", "module_health",
        "module_router_api", "zigbee_module", "zwave_module", "thread_module",
        "ha_module", "sonos", "unifi_stub", "regional_stub", "comfort_stub",
        "habitus", "habitus_dashboard_cards", "graph", "graph_ops", "vector",
        "neurons", "neurons_ui", "neurons_visualization", "neuron_layers",
        "brain_growth", "knowledge_graph.api", "mood", "learning_viz",
        "predictive", "suggestions", "proposals", "candidates", "action_closure",
        "action_attribution", "automation_api", "autonomy", "scenes", "multizone",
        "energy_forecast", "ml_forecast", "anomaly", "energy_analytics",
        "search", "rag", "rag_ui", "notifications", "chat", "conversation",
        "voice_context_bp", "styx_voice", "user_hints", "reminders", "calendar",
        "ha_events", "events_ingest", "cache_control", "performance", "rate_limit",
        "media_ui", "media_zones", "musikwolke", "backend_ui", "dashboard",
        "styx_dashboard", "widget_positions", "config", "user_preferences",
        "user_management", "homekit", "sharing.api", "multihome",
        "collective_intelligence.api", "shopping", "haushalt", "error_digest",
        "dev", "debug", "swagger_ui", "entity_adoption", "entity_assignment",
        "entity_normalization", "alarm", "conflict_resolution",
    ]
    
    created = 0
    skipped = 0
    
    for mod in core_blueprints:
        mod_file = mod.replace(".", "/") + ".py"
        bridge_path = root / mod_file
        runtime_path = runtime_root / mod_file
        
        # Skip if bridge already exists
        if bridge_path.exists():
            skipped += 1
            continue
        
        # Skip if runtime module doesn't exist either
        if not runtime_path.exists():
            continue
        
        # Create parent directories if needed
        bridge_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate bridge content
        bridge_content = f'''"""Bridge: {mod} → Runtime-Tree.

This module forwards all imports to the real implementation in Runtime-Tree:
  copilot_core/rootfs/usr/src/app/copilot_core/api/v1/{mod_file}
"""
from __future__ import annotations

import sys
from pathlib import Path

_runtime_path = (
    Path(__file__).resolve().parents[1] / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "api" / "v1"
)

if str(_runtime_path) not in sys.path:
    sys.path.insert(0, str(_runtime_path))

# Import everything from runtime module
from {mod.replace(".", "_")} import *  # noqa: F401,F403
'''
        
        bridge_path.write_text(bridge_content)
        created += 1
        print(f"Created bridge: {mod}")
    
    print(f"\nDone: {created} bridges created, {skipped} skipped (already exist)")

if __name__ == "__main__":
    main()
