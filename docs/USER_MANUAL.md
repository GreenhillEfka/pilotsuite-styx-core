# USER_MANUAL.md - PilotSuite User Guide

> **Version:** 13.9.0 (HA Integration) + 13.9.0 (Core Add-on)
> **Last Updated:** 2026-03-07

---

## ⚡ Migration Quick Reference (v13.5.3)

> **Für bestehende Integrationen:**
>
> | Legacy | Aktiv | Hinweis |
> |--------|-------|---------|
> | `/api/v1/tags` | `/api/v1/tag-system/tags` | Tag-System Namespace |
> | `/api/v1/tags/{id}` | `/api/v1/tag-system/tags/{tag_id}` | Tag-System Namespace |
> | `/api/v1/candidates/{id}` | `/api/v1/candidates/{candidate_id}` | Parameter-Name vereinheitlicht |
> | `X-API-Key` Header | `X-Auth-Token` Header | Auth-Header bevorzugt |
> | `mood_changed` Event | `mood` Event | Kanonischer Event-Typ |
>
> Für neue Integrationen ausschliesslich die aktive v13-Surface verwenden.

---

## 📖 Table of Contents

1. [Quick Setup](#quick-setup)
2. [Core Add-on Installation](#core-add-on-installation)
3. [HA Integration Installation](#ha-integration-installation)
4. [Configuration](#configuration)
5. [Zone Configuration Walkthrough](#zone-configuration-walkthrough)
6. [Parameter Explanations](#parameter-explanations)
7. [How Features Work Together](#how-features-work-together)
8. [Dashboard Cards](#dashboard-cards)
9. [Troubleshooting](#troubleshooting)

---

## ⚡ Quick Setup

```bash
# 1. Install Core Add-on via Home Assistant Add-on Store
# 2. Install HA Integration via HACS
# 3. Configure token in both
# 4. Restart Home Assistant
# 5. Access dashboard at http://<HA_IP>:8909
```

---

## 🟢 Core Add-on Installation

### Step 1: Add Repository

1. Open **Home Assistant** → **Settings** → **Add-ons**
2. Click **Add-on Store** (three dots) → **Repositories**
3. Add: `https://github.com/GreenhillEfka/pilotsuite-styx-core`

### Step 2: Install PilotSuite Core

1. Find **PilotSuite Core** in the add-on store
2. Click **Install**
3. Wait for installation to complete

### Step 3: Configure

Edit the add-on configuration:

```yaml
log_level: info
auth_token: your-secret-token-change-me
port: 8909
```

### Step 4: Start

1. Click **Start** in the add-on view
2. Wait for startup (check Logs tab)

### Verify Installation

```bash
# Health check
curl http://homeassistant.local:8909/health

# Version check
curl http://homeassistant.local:8909/version
```

---

## 🔵 HA Integration Installation

### Step 1: Install via HACS

1. Open **HACS** in Home Assistant
2. Go to **Integrations**
3. Search for **PilotSuite**
4. Click **Download**

### Step 2: Configure Integration

1. **Settings** → **Devices & Services** → **Add Integration**
2. Search for **PilotSuite**
3. Configure:
   - **Core URL:** `http://homeassistant.local:8909`
   - **Auth Token:** (same as Core add-on config)

### Step 3: Restart HA

Restart Home Assistant to load all entities and services.

---

## ⚙️ Configuration

### Core Add-on Config

| Parameter | Default | Description |
|-----------|---------|-------------|
| `port` | 8909 | HTTP port for API |
| `auth_token` | (required) | Secret token for authentication |
| `log_level` | info | Logging level (debug, info, warning, error) |
| `storage_path` | /data | Path for persistent storage |
| `max_nodes` | 500 | Brain Graph max nodes |
| `max_edges` | 1500 | Brain Graph max edges |

### HA Integration Config

The integration automatically discovers:
- All entities
- All areas/zones
- All devices

You can configure specific options in **Settings** → **Devices & Services** → **PilotSuite** → **Configure**.

### Environment Variables (Advanced)

| Variable | Description |
|----------|-------------|
| `COPILOT_TAG_ASSIGNMENTS_PATH` | Path for tag assignments store |
| `COPILOT_AUTH_TOKEN` | Override auth token |

---

## 🗺️ Zone Configuration Walkthrough

### Understanding Zone Hierarchy

PilotSuite uses a three-level hierarchy:

```
Floor → Area → Room
```

**Example:**
- Floor: `EG` (Ground Floor)
  - Area: `Wohnbereich` (Living Area)
    - Room: `Wohnzimmer` (Living Room)
    - Room: `Küche` (Kitchen)
  - Area: `Schlafbereich` (Sleeping Area)
    - Room: `Schlafzimmer` (Bedroom)
    - Room: `Bad` (Bathroom)

### Creating Zones via UI

1. **Open Core Dashboard:** `http://<HA_IP>:8909`
2. Navigate to **Habitus** → **Zones**
3. Click **Add Zone**
4. Fill in:
   - **Name:** Human-readable name
   - **Type:** floor/area/room/outdoor
   - **Parent:** Parent zone (for hierarchy)
   - **Roles:** Assign entity roles

### Creating Zones via YAML

Alternatively, edit `zones.yaml` directly:

```yaml
zones:
  - name: EG
    type: floor
    children:
      - name: Wohnbereich
        type: area
        children:
          - name: Wohnzimmer
            type: room
            roles:
              lights: light.wohnen_*
              motion: binary_sensor.motion_wohnen
              temperature: sensor.temperature_wohnen
              media: media_player.wohnbereich
```

### Zone Entity Roles

Assign roles to link entities to zones:

| Role | Entities |
|------|----------|
| `motion` | Motion sensors |
| `lights` | Light entities |
| `temperature` | Temperature sensors |
| `humidity` | Humidity sensors |
| `co2` | CO2 sensors |
| `heating` | Thermostats |
| `door` / `window` | Door/window sensors |
| `media` | Media players |
| `power` / `energy` | Power/energy monitors |

### Zone States

Zones automatically track occupancy state:

| State | Meaning |
|-------|---------|
| `idle` | No activity detected |
| `active` | Someone is present |
| `transitioning` | State changing |
| `disabled` | Zone disabled |
| `error` | Error detected |

---

## 📊 Parameter Explanations

### Habitus Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_confidence` | 0.5 | Minimum confidence for rule suggestions |
| `max_delta_seconds` | 3600 | Max time between A and B in rules |
| `min_support` | 5 | Minimum occurrences for rule |

### Brain Graph Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_nodes` | 500 | Maximum nodes in graph |
| `max_edges` | 1500 | Maximum edges in graph |
| `decay_half_life` | 7 days | Node weight decay rate |
| `prune_threshold` | 0.1 | Weight threshold for pruning |

### Tag System Parameters

| Parameter | Description |
|-----------|-------------|
| `tag_registry` | YAML file with tag definitions |
| `assignments_path` | JSON store for tag assignments |
| `auto_assign` | Auto-suggest tags based on entity type |

### API Parameters

| Endpoint | Parameters |
|----------|------------|
| `/api/v1/habitus/rules` | `limit`, `min_score`, `a_filter`, `b_filter` |
| `/api/v1/graph/state` | `kind`, `domain`, `center`, `hops`, `limit` |
| `/api/v1/tag-system/assignments` | `subject`, `tag`, `materialized`, `limit` |

---

## 🔗 How Features Work Together

### Complete Data Flow

```
┌────────────────┐     ┌─────────────┐     ┌──────────────┐
│   Entities     │────▶│  Forwarder  │────▶│   Ingest     │
│   (HA State)   │     │  (Module)   │     │   (Core)     │
└────────────────┘     └─────────────┘     └──────────────┘
                                                    │
                                                    ▼
                                            ┌──────────────┐
                                            │  EventStore  │
                                            └──────────────┘
                                                    │
                              ┌─────────────────────┼─────────────────────┐
                              ▼                     ▼                     ▼
                       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
                       │   Brain     │       │  Knowledge  │       │   Habitus   │
                       │   Graph     │       │   Graph     │       │   Miner     │
                       └─────────────┘       └─────────────┘       └─────────────┘
                              │                     │                     │
                              ▼                     ▼                     ▼
                       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
                       │  Entities   │       │   Search    │       │   Rules     │
                       │   Cards     │       │   Context   │       │  Suggestions│
                       └─────────────┘       └─────────────┘       └─────────────┘
```

### Feature Integration

#### 1. Zone System ↔ Brain Graph

- Zones create graph nodes automatically
- Entities link to zones via `located_in` edges
- Query: "What lights are on in the living room?"

#### 2. Tag System ↔ Zone System

- Tags can define zone membership rules
- Zone entities suggest relevant tags
- Cross-reference: "Find all safety_critical devices in the kitchen"

#### 3. Habitus ↔ Tag System

- Discovered rules tagged with semantic labels
- Tags filter which rules to suggest
- Example: `aicp.role.evening_routine` → suggest at evening

#### 4. Mood ↔ Energy ↔ Weather

- Mood affects suggested actions
- Energy context provides consumption insights
- Weather influences automation decisions

### Example Workflows

#### Morning Routine Discovery

1. **Input:** Entity state changes at 7:00 AM daily
2. **Processing:** Habitus Miner detects pattern
3. **Output:** Rule suggestion "Motion in hallway → Kitchen lights on"
4. **Tagging:** Rule gets `aicp.kind.morning`, `aicp.role.routine`
5. **Suggestion:** User sees automation candidate in dashboard

#### Zone-Based Lighting

1. **Zone:** Living room defined with lights + motion
2. **Brain Graph:** Creates zone node + entity links
3. **Context:** "Living room occupied" state
4. **Action:** Suggest "Turn on living room lights when occupied"

---

## 📱 Dashboard Cards

PilotSuite provides Lovelace cards for visualization.

### Available Cards

| Card | Purpose |
|------|---------|
| **Zone Context** | Zone overview with entity states |
| **Brain Graph** | Neural visualization |
| **Mood Tracker** | Mood over time |
| **Energy Distribution** | Energy consumption |
| **Weather Calendar** | Weather integration |
| **Habitus Rules** | Discovered automation rules |
| **Tag Browser** | Tag assignment management |

### Adding Cards to Lovelace

1. Edit your Lovelace dashboard
2. Add **Manual Card**
3. Paste card YAML:

```yaml
type: custom:pilotsuite-zone-context
title: Living Room
zone: living_room
```

### Card Types

#### Zone Context Card
```yaml
type: custom:pilotsuite-zone-context
title: Zone Overview
zone: wohnzimmer
show_roles:
  - lights
  - temperature
  - motion
```

#### Brain Graph Card
```yaml
type: custom:pilotsuite-brain-graph
title: Home Neural Network
center: zone.wohnzimmer
hops: 2
theme: dark
layout: dot
```

#### Habitus Rules Card
```yaml
type: custom:pilotsuite-styx-habitus-rules
title: Suggested Automations
min_confidence: 0.7
limit: 10
```

---

## 🔧 Troubleshooting

### Core Add-on Won't Start

```bash
# Check logs
docker logs copilot_core

# Common issues:
# - Port 8909 already in use
# - Invalid auth token format
# - Missing dependencies
```

### HA Integration Not Finding Core

1. Verify Core is running: `curl http://<HA_IP>:8909/health`
2. Check firewall allows port 8909
3. Verify auth token matches in both

### Entities Not Appearing

1. Check **Developer Tools** → **States**
2. Look for `ai_home_copilot.*` entities
3. Restart HA Integration

### Brain Graph Empty

- Wait for initial data collection (5-10 minutes)
- Check events are being forwarded
- Verify Core receives events: `/api/v1/events/stats`

### Zone States Wrong

- Check entity role assignments
- Verify sensors are working in HA
- Check zone parent-child hierarchy

---

## 📞 Getting Help

| Resource | Link |
|----------|------|
| GitHub Issues | https://github.com/GreenhillEfka/pilotsuite-styx-core/issues |
| Documentation | https://github.com/GreenhillEfka/pilotsuite-styx-core#readme |
| Discord | https://github.com/GreenhillEfka/pilotsuite-styx-core/discussions |

---

*Last Updated: 2026-02-20*
