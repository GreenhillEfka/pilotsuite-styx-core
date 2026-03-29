# HA↔Core Integration Roadmap — 2026-03-29

## Status: ACTIVE — Slice 8 (HA Connection Module Hardening) IN PROGRESS

---

## 1. CURRENT STATE

### What Works ✅

| Path | Component | Status |
|------|-----------|--------|
| HA→Core event ingest | `N3EventForwarder` → `POST /api/v1/events` → `EventStore.ingest_batch()` | **Working** — Slice 1 canonical path active |
| HA→Core zone polling | `HabitusZoneSensor._fetch("/api/v1/hub/zones")` → Core `HubAPI` | **Connected** — endpoint responds (but empty) |
| Hub API blueprint | `copilot_core/hub/api.py` → `hub_bp` registered at `/api/v1/hub` | **Registered** — all routes protected with `@require_token` |
| `HabitusZoneEngine` | In-memory zone CRUD in `hub/habitus_zones.py` | **Functional** — create/get/set mode all implemented |
| Zone overview endpoint | `GET /api/v1/hub/zones` → `_zone_engine.get_overview()` | **Returns data** — returns `ZoneOverview` dataclass |
| HA→Core zone definitions sync | `CopilotApiClient.async_sync_zone_definitions()` → `POST /api/v1/zone-automation/zones/sync` | **Defined** — called from coordinator `_first_zone_sync()` |
| HA zone store | `habitus_zones_store_v2.py` → `HabitusZoneV2` entities stored in HA | **Working** — HA has its own zone definitions |
| Zone automation API | `zone-automation/zones` endpoints in Core | **Wired** |
| Candidate polling | `candidate_poller.py` polls Core `/api/v1/candidates/proposals` | **Active** |

### What's Broken ❌

| # | Problem | Severity |
|---|---------|----------|
| B1 | `HabitusZoneEngine._zones` is **always empty** on Core startup — no zones exist until HA sends `sync_zone_definitions`. If `_first_zone_sync()` hasn't run yet (or coordinator restarted before first sync), `get_overview()` returns 0 zones. | **CRITICAL** |
| B2 | `_sync_zone_definitions()` in `CopilotApiClient` **does NOT call** `HubZoneEngine.create_zone()` — it POSTs to `/zone-automation/zones/sync` but nothing restores `HubZoneEngine` state from that payload. | **CRITICAL** |
| B3 | `_first_zone_sync()` is a **one-time conditional** (`if ha_zones`) — if HA has no zones yet, or coordinator fails before first sync, Core permanently has no zones. No automatic retry or startup initialization. | **HIGH** |
| B4 | `HubZoneEngine` is **purely in-memory** — no persistence. Every Core restart/wipe kills all zone state. No `sync_from_ha()` or startup loader. | **HIGH** |
| B5 | HA event forwarder `N3EventForwarder` sends to `/api/v1/events` (correct), but `ModuleRouter.ingest_event()` **may not propagate HA events into `HubZoneEngine`** — zone engine doesn't receive HA state_changed events for entity→zone mapping. | **MEDIUM** |
| B6 | `habitat_adapter.py` (Core side) has `build_state_changed_forward_item()` but **no consumer** — events go through `EventStore → EventProcessor → ModuleRouter`. Whether `ModuleRouter.ingest_event()` updates `HubZoneEngine` is unclear. | **MEDIUM** |

### The Root Cause: "0 zones in Core live"

```
HA startup
  → coordinator._first_zone_sync()
       → reads HA zones from habitus_zones_store_v2
       → calls api.async_sync_zone_definitions(zone_defs)
            → POST /api/v1/zone-automation/zones/sync
                 → stores in ZoneAutomation system [NOT in HubZoneEngine]
       → sets result["zone_automation"]

Later:
  HA HabitusZoneSensor async_update()
       → _fetch("/api/v1/hub/zones")
            → GET /api/v1/hub/zones
                 → HubZoneEngine.get_overview()
                      → self._zones = {}  ← EMPTY (never populated!)
                      → returns ZoneOverview(total_zones=0, ...)
```

The `HabitusZoneEngine` is **never populated** from HA's zone data. Zone definitions go to the Zone Automation store but never to the `HubZoneEngine`.

---

## 2. BLOCKERS

1. **B1 (CRITICAL):** `HubZoneEngine` has no `sync_from_ha()` method — nothing populates it from HA zone definitions
2. **B2 (CRITICAL):** `_sync_zone_definitions()` in `CopilotApiClient` POSTs to wrong/unused endpoint — doesn't call any `HubZoneEngine` method
3. **B3 (HIGH):** No retry/re-init path for `_first_zone_sync()` if it skipped on first coordinator startup
4. **B4 (HIGH):** No persistence for `HabitusZoneEngine` — zones lost on every Core restart
5. **B5 (MEDIUM):** HA→Core event path doesn't update `HubZoneEngine` entity/room state
6. **B6 (MEDIUM):** `habitat_adapter.py` on Core side has inbound functions but no wiring to `HubZoneEngine`

---

## 3. PRIORITIZED ROADMAP

### Step 1 — Fix Zone Sync: `HubZoneEngine.sync_from_ha()` + Core endpoint
**File:** `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
**File:** `copilot_core/rootfs/usr/src/app/copilot_core/hub/api.py`

**What to add:**
- `HubitusZoneEngine.sync_from_ha(zones: list[dict])` method that:
  - Clears or merges existing zones
  - For each zone def: calls `create_zone()` with all params (zone_id, name, room_ids, entity_ids, zone_type, enabled_modules)
  - Registers all rooms via `register_room()` if not already present
- New Core endpoint `POST /api/v1/hub/zones/sync` in `hub/api.py`:
  ```python
  @hub_bp.route("/zones/sync", methods=["POST"])
  @require_token
  def sync_zones_from_ha():
      zones = request.get_json().get("zones", [])
      _zone_engine.sync_from_ha(zones)
      return jsonify({"ok": True, "synced": len(zones)})
  ```

**Expected outcome:** `HubZoneEngine._zones` is populated from HA data. `GET /api/v1/hub/zones` returns correct zone counts.

---

### Step 2 — Fix HA client to call the correct sync endpoint
**File:** `custom_components/copilot_ha/coordinator.py`

**What to change in `CopilotApiClient.async_sync_zone_definitions()`:**
- Change endpoint from `POST /api/v1/zone-automation/zones/sync` to `POST /api/v1/hub/zones/sync`

**Or** wire `_sync_zone_definitions()` to also call `POST /api/v1/hub/zones/sync` in addition to Zone Automation sync.

**Expected outcome:** HA zone definitions actually reach `HubZoneEngine`.

---

### Step 3 — Make `_first_zone_sync()` resilient
**File:** `custom_components/copilot_ha/coordinator.py`

**What to change:**
- `_first_zone_sync()` should run on **every** coordinator startup, not just once
- Add a `data` storage key `["zone_sync_done"]` to track if sync was completed
- If sync failed previously, retry on next coordinator refresh cycle
- Also add sync call in `CopilotDataUpdateCoordinator.__init__()` after `api` client is initialized

**Expected outcome:** No silent skip of zone sync on first startup failure.

---

### Step 4 — Add startup zone loader to `core_setup.py`
**File:** `copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py`

**What to add in `_wire_habitus_auto_mining()` or a new `_init_zone_persistence()`:**
- After `HubZoneEngine` is initialized, check for a persisted zone snapshot (JSON file in data dir)
- If snapshot exists, call `HubZoneEngine.sync_from_ha(zones_from_file)` to restore state
- On first successful zone sync from HA, save snapshot

**Alternative (simpler):** Add zone persistence to `HabitusZoneEngine` itself — store `_zones` and `_rooms` to JSON on every mutating call, reload on `__init__`.

**Expected outcome:** Zones survive Core restarts.

---

### Step 5 — Wire HA→Core events to `HubZoneEngine` entity adoption
**File:** `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
**File:** `copilot_core/rootfs/usr/src/app/copilot_core/ingest/event_processor.py`

**What to add:**
- `HubZoneEngine.apply_state_changed(entity_id, new_state)` — updates entity values in `_entity_values`, triggers room re-evaluation if an entity was adopted
- In `event_processor.py` post-ingest chain: after `feed_events_to_graph()`, call `hub_zones.apply_state_changed()` if entity belongs to a known zone room

**Expected outcome:** HA state changes flow into `HubZoneEngine` for real-time entity↔room↔zone mapping.

---

### Step 6 — Wire `habitat_adapter.py` inbound to `HubZoneEngine`
**File:** `copilot_core/rootfs/usr/src/app/copilot_core/homeassistant/habitat_adapter.py`
**File:** `copilot_core/rootfs/usr/src/app/copilot_core/ingest/event_processor.py`

**What to do:**
- `build_state_changed_forward_item()` produces a `habitat_event` + `neuron_input` structure
- In the post-ingest chain (`event_processor.py`), if `event.module_id == "homeassistant"` and it's a zone-related entity, call `HubZoneEngine.apply_state_changed()`
- Add unit tests proving the full path: HA event → Core ingest → `HubZoneEngine` update

**Expected outcome:** The `habitat_adapter.py` contract layer is actually consumed, not just defined.

---

### Step 7 — Open Items from Slice 8/10/11
**These are the currently OPEN slices that depend on Steps 1-6 being complete:**

| Slice | Item | Depends On |
|-------|------|-----------|
| Slice 8 | HA Connection Module Hardening | Steps 1-6 complete |
| Slice 10 | Decision/Execution Separation | HubZoneEngine stable |
| Slice 11 | Contract + Regression Coverage | All above |

---

## 4. QUICK WIN — Single Commit

### Fix: `_sync_zone_definitions` → actually call `HubZoneEngine.sync_from_ha()`

**What to change (one file):**

`copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py` — add this method to `HabitusZoneEngine`:

```python
def sync_from_ha(self, zone_defs: list[dict[str, Any]]) -> dict[str, Any]:
    """Sync zone definitions from HA. Replaces or merges HA-sourced zones.
    
    Args:
        zone_defs: list of zone definitions as dicts with keys:
            zone_id, name_de, room_ids, entity_ids, zone_type, enabled_modules
    """
    synced = 0
    for zd in zone_defs:
        zone_id = str(zd.get("zone_id", "")).strip()
        if not zone_id:
            continue
        
        name = zd.get("name_de", zd.get("name", zone_id))
        room_ids = list(zd.get("room_ids", []))
        entity_ids = list(zd.get("entity_ids", []))
        zone_type = str(zd.get("zone_type", "living")).strip() or "living"
        enabled = set(zd.get("enabled_modules", []))
        
        # Register rooms first
        for rid in room_ids:
            if rid not in self._rooms:
                self.register_room(room_id=rid, name=rid.replace("_", " ").title())
        
        # Create or update zone
        if zone_id in self._zones:
            zone = self._zones[zone_id]
            zone.name = name
            zone.rooms = room_ids
            zone.zone_type = zone_type
            zone.enabled_modules = enabled
            self._refresh_zone_entities(zone)
        else:
            self.create_zone(
                zone_id=zone_id,
                name=name,
                room_ids=room_ids,
                zone_type=zone_type,
                enabled_modules=enabled,
            )
        
        # Register orphaned entities not yet in any room
        for eid in entity_ids:
            in_any_room = any(eid in (self._rooms.get(rid) or RoomConfig(rid, "", "")).entities for rid in self._rooms)
            if not in_any_room:
                # Associate directly with zone (entity adoption)
                if eid not in self._entity_types:
                    domain = eid.split(".")[0] if "." in eid else "unknown"
                    self._entity_types[eid] = domain
        
        synced += 1
    
    logger.info("sync_from_ha: synced %d zones from HA", synced)
    return {"ok": True, "synced": synced}
```

**Then add the Core endpoint** in `copilot_core/rootfs/usr/src/app/copilot_core/hub/api.py`:

```python
@hub_bp.route("/zones/sync", methods=["POST"])
@require_token
def sync_zones_from_ha():
    """Receive zone definitions from HA and populate HubZoneEngine."""
    if not _zone_engine:
        return jsonify({"error": "Zone engine not initialized"}), 503
    body = request.get_json() or {}
    zones = body.get("zones", [])
    result = _zone_engine.sync_from_ha(zones)
    return jsonify({"ok": True, **result})
```

**Then update HA client** in `custom_components/copilot_ha/coordinator.py` — in `async_sync_zone_definitions()` change the POST URL from `/api/v1/zone-automation/zones/sync` to `/api/v1/hub/zones/sync`.

**Expected outcome:** After HA coordinator startup, `GET /api/v1/hub/zones` returns all HA zones. The sensor shows correct counts. All prior routes continue working (backwards compatible — `hub_bp` already exists, only a new route is added).

**Impact:** Fixes the most visible broken feature (0 zones in Core) in one focused commit.

---

## Appendix: File Map

| File | Role |
|------|------|
| `HA: coordinator.py` | `_first_zone_sync()`, `async_sync_zone_definitions()` |
| `HA: entity.py` | `_fetch()` helper, `_core_base_url()`, `_core_headers()` |
| `HA: forwarder_n3.py` | `N3EventForwarder` — HA→Core event stream |
| `HA: habitus_zone_sensor.py` | Reads `/api/v1/hub/zones` every 30s |
| `HA: habitus_zones_store_v2.py` | HA-side zone storage (HabitusZoneV2) |
| `Core: hub/api.py` | `hub_bp`, `GET /api/v1/hub/zones`, `init_hub_api()` |
| `Core: hub/habitus_zones.py` | `HabitusZoneEngine`, `get_overview()`, `create_zone()` |
| `Core: core_setup.py` | Engine wiring, `init_hub_api(services)`, `hub_bp` registration |
| `Core: ingest/event_store.py` | `ingest_batch()` — canonical HA event storage |
| `Core: ingest/event_processor.py` | Post-ingest callback chain |
| `Core: homeassistant/habitat_adapter.py` | Contract boundary (ha.input.v1) |
| `Core: api/security.py` | `@require_token` decorator |
| `Docs: ZONE_TRUTH_CONTRACT.md` | Zone truth store spec (Slice 2) |
| `Docs: INGEST_CONTRACT.md` | Canonical ingest path spec (Slice 1) |
