# PilotSuite Module Inventory (2026-03-22)

This inventory reflects the production-ready baseline at `v15.0.x`.

## Scope
- Core add-on backend: `pilotsuite-styx-core`
- HA integration frontend/runtime: `pilotsuite-styx-ha`

## Module System Architecture

### Registry (module_registry.py)
- **States**: `active` | `learning` | `off`
- **Default**: `active` (global default)
- **Zone-level overrides**: per-zone module state via `set_zone_state()`
- **Persistence**: SQLite at `/data/module_states.db`

### Hub Module Inventory (hub/ — 30+ modules)

| Module | Domain | Description |
|---|---|---|
| alarm | Alarm | Alarm panel integration |
| anomaly_detection | Monitoring | Unusual pattern detection |
| automation_templates | Automation | Reusable automation patterns |
| bewgung_module | Movement | Motion-based triggers |
| brain_activity | Brain | Brain graph activity tracking |
| brain_architecture | Brain | Brain graph structure |
| brightness_filter | Light | Ambient brightness filtering |
| dashboard | UI | Styx dashboard endpoints |
| energy_advisor | Energy | Energy optimization suggestions |
| habitus_zones | Zones | Zone habitus management |
| heiz_module | Climate | Heating control |
| helligkeit_module | Light | Brightness automation |
| homeassistant_module | HA | HA integration bridge |
| licht_module | Light | Light control |
| light_intelligence | Light | Smart light orchestration |
| media_follow | Media | Media-based presence |
| module_router | Routing | Module request routing |
| multi_home | Household | Multi-home support |
| musikwolke_bridge | Media | Musikwolke integration |
| notification_intelligence | Notifications | Smart notification routing |
| plugin_manager | Plugins | Plugin lifecycle |
| praesenz_module | Presence | Presence detection |
| predictive_maintenance | Predictive | Maintenance predictions |
| presence_intelligence | Presence | Advanced presence |
| scene_intelligence | Scenes | Scene automation |
| sonos_client | Media | Sonos integration |
| system_integration | System | System-level integration |
| thread_module | Network | Thread/Zigbee |
| wecker | Alarm | Alarm clock |
| zigbee_module | Zigbee | Zigbee devices |
| zone_automation | Zones | Zone automation engine |
| zone_modes | Zones | Zone mode management |
| zone_modules | Zones | Per-zone module config |
| zwave_module | Z-Wave | Z-Wave devices |

### Core Package Domains (copilot_core/)

| Domain | State | Description |
|---|---|---|
| api | Active | REST API v1 endpoints |
| automation | Active | Automation execution |
| autonomy | Active | Autonomous decision engine |
| brain_graph | Active | Neural graph (nodes/edges) |
| candidates | Active | Habit candidate lifecycle |
| collective_intelligence | Active | Group decision making |
| energy | Active | Energy management |
| habitus_miner | Active | Pattern discovery |
| homeassistant | Active | HA integration layer |
| ingest | Active | Event ingestion + N3 |
| knowledge_graph | Active | Semantic knowledge base |
| ml | Active | Machine learning models |
| monitoring | Active | Health + diagnostics |
| mood | Active | Mood tracking + scoring |
| neurons | Active | Neuron management |
| notifications | Active | Push notifications |
| proactive_engine | Active | Proactive suggestions |
| rag | Active | Retrieval-augmented generation |
| synapses | Active | Module interconnectivity |
| system_health | Active | System health checks |
| vector_store | Active | Embedding storage |
| voice | Active | Voice processing |
| web_search | Active | Web search integration |

### HA Integration Modules (ha/)

| HA Module | State | Description |
|---|---|---|
| events_forwarder | Learning | HA → Core event streaming |
| habitus_miner | Learning | HA-side habit mining |
| history_backfill | Learning | Historical data backfill |
| dev_surface | Off | Developer surface |
| performance_scaling | Active | Dynamic scaling |
| legacy | Off | Legacy compatibility |

### API Endpoints (v1)

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/modules` | GET | List all module states |
| `/api/v1/modules/<id>` | GET | Get single module state |
| `/api/v1/modules` | POST | Create module state |
| `/api/v1/modules/<id>` | PUT | Update module state |
| `/api/v1/modules/<id>/configure` | POST | Patch module state |
| `/api/v1/zone-automation/zones` | GET | List zone configs |
| `/api/v1/zone-automation/ensure-zones` | POST | Bulk-create zones (IDs only) |
| `/api/v1/zone-automation/sync-definitions` | POST | Sync full zone definitions from HA |
| `/api/v1/zone-automation/module-schemas` | GET | Get schemas for zone modules |
| `/api/v1/zone-automation/zones/<zone_id>/modules/<module_id>` | GET/POST | Per-zone module config |
| `/api/v1/zone-automation/zones/<zone_id>/mode` | PUT | Set zone automation mode |
| `/api/v1/autonomy/execute` | POST | Execute autonomous action |
| `/api/v1/brain/graph` | GET | Brain graph state |
| `/api/v1/candidates` | GET/POST | Habit candidates |
| `/api/v1/mood` | GET | Current mood state |
| `/api/v1/notifications` | GET/POST | Notification management |

## Source of Truth
- HA: `/config/clawd/team/repos/pilotsuite-styx-ha` (origin/main)
- Core: `/config/clawd/team/repos/pilotsuite-styx-core` (origin/main)
