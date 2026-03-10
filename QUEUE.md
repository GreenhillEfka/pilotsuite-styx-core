# QUEUE.md - Reconciliation Queue

## 2026-03-10 STYX-OLLAMA-1-TASK-002: /api/v1/hub* Reconciliation Batch 1

**Status:** DONE
**Timestamp:** 2026-03-10 01:19 GMT+1
**Action:** Mirrored 5 clusters from HA to Core (~23 paths total)

### Clusters reconciled:
1. `/api/v1/hub/dashboard*` (4 paths)
   - `/api/v1/hub/dashboard` (GET)
   - `/api/v1/hub/dashboard/widget/{widget_type}` (GET, DELETE)
   - `/api/v1/hub/dashboard/layout` (POST)
   - `/api/v1/hub/dashboard/widget` (POST)

2. `/api/v1/hub/homes*` (4 paths)
   - `/api/v1/hub/homes` (GET, POST)
   - `/api/v1/hub/homes/{home_id}` (GET, DELETE)
   - `/api/v1/hub/homes/{home_id}/activate` (POST)
   - `/api/v1/hub/homes/{home_id}/status` (POST)

3. `/api/v1/hub/integration*` (5 paths)
   - `/api/v1/hub/integration` (GET)
   - `/api/v1/hub/integration/status` (GET)
   - `/api/v1/hub/integration/wiring` (GET)
   - `/api/v1/hub/integration/dispatch` (POST)
   - `/api/v1/hub/integration/auto-wire` (POST)

4. `/api/v1/hub/maintenance*` (5 paths)
   - `/api/v1/hub/maintenance` (GET)
   - `/api/v1/hub/maintenance/device/{device_id}` (GET)
   - `/api/v1/hub/maintenance/register` (POST)
   - `/api/v1/hub/maintenance/ingest` (POST)
   - `/api/v1/hub/maintenance/evaluate` (POST)

5. `/api/v1/hub/plugins*` (5 paths)
   - `/api/v1/hub/plugins` (GET)
   - `/api/v1/hub/plugins/{plugin_id}` (GET)
   - `/api/v1/hub/plugins/{plugin_id}/activate` (POST)
   - `/api/v1/hub/plugins/{plugin_id}/disable` (POST)
   - `/api/v1/hub/plugins/{plugin_id}/config` (POST)

### Verification:
- All 23 paths inserted after `/api/v1/hub/modes`
- Path counts verified: dashboard(4), homes(4), integration(5), maintenance(5), plugins(5)
- Exact path match with HA source confirmed

---

## 2026-03-10 STYX-OLLAMA-1-TASK-004: /api/v1/hub* Reconciliation Batch 3

**Status:** DONE
**Timestamp:** 2026-03-10 01:28 GMT+1
**Action:** Mirrored 4 clusters from HA to Core (35 new paths total)

### Clusters reconciled:
1. `/api/v1/hub/media*` (9 paths)
   - `/api/v1/hub/media` (GET)
   - `/api/v1/hub/media/follow` (POST)
   - `/api/v1/hub/media/playback` (POST)
   - `/api/v1/hub/media/sessions` (GET)
   - `/api/v1/hub/media/sources` (GET, POST)
   - `/api/v1/hub/media/sources/{entity_id}` (DELETE)
   - `/api/v1/hub/media/transfer` (POST)
   - `/api/v1/hub/media/zone/{zone_id}` (GET)
   - `/api/v1/hub/media/zone_enter` (POST)

2. `/api/v1/hub/scenes*` (12 paths)
   - `/api/v1/hub/scenes` (GET)
   - `/api/v1/hub/scenes/list` (GET)
   - `/api/v1/hub/scenes/active` (GET)
   - `/api/v1/hub/scenes/activate` (POST)
   - `/api/v1/hub/scenes/deactivate` (POST)
   - `/api/v1/hub/scenes/suggest` (POST)
   - `/api/v1/hub/scenes/learn` (POST)
   - `/api/v1/hub/scenes/cloud` (POST)
   - `/api/v1/hub/scenes/cloud/status` (GET)
   - `/api/v1/hub/scenes/cloud/share` (POST)
   - `/api/v1/hub/scenes/{scene_id}/rate` (POST)
   - `/api/v1/hub/scenes/custom` (POST)

3. `/api/v1/hub/zones*` extended (8 NEW paths, base existed)
   - `/api/v1/hub/zones/{zone_id}` (GET, DELETE)
   - `/api/v1/hub/zones/{zone_id}/mode` (POST)
   - `/api/v1/hub/zones/{zone_id}/room` (POST)
   - `/api/v1/hub/zones/{zone_id}/room/{room_id}` (DELETE)
   - `/api/v1/hub/zones/rooms` (GET, POST)
   - `/api/v1/hub/zones/templates` (GET)
   - `/api/v1/hub/zones/template/{template_id}` (POST)
   - `/api/v1/hub/zones/modes` (GET)

4. `/api/v1/hub/modes*` extended (6 NEW paths, base existed)
   - `/api/v1/hub/modes/available` (GET)
   - `/api/v1/hub/modes/zone/{zone_id}` (GET)
   - `/api/v1/hub/modes/activate` (POST)
   - `/api/v1/hub/modes/deactivate` (POST)
   - `/api/v1/hub/modes/expire` (POST)
   - `/api/v1/hub/modes/custom` (POST)

### Verification:
- All 35 new paths inserted in `/api/v1/hub/` section
- Path counts verified: media(9), scenes(12), zones extended(8), modes extended(6)
- Exact path match with HA source confirmed
- YAML syntax valid

---

## 2026-03-10 STYX-OLLAMA-1-TASK-005: /api/v1/hub/notifications* Cluster Reconciliation

**Status:** DONE
**Timestamp:** 2026-03-10 01:42 GMT+1
**Action:** Fixed 4 truncated endpoint definitions in Core (paths existed but were incomplete)

### Issue Found:
The `/api/v1/hub/notifications*` cluster paths already existed in Core (12 paths total) but 4 endpoint definitions were truncated/incomplete - missing operationId, tags, responses, requestBody, and security fields.

### Fixed Endpoints:
1. `/api/v1/hub/notifications/batch` (POST)
   - Was: Truncated after description line
   - Fixed: Added complete operationId `configure_notification_batch`, tags, responses, requestBody, security

2. `/api/v1/hub/notifications/dnd/status` (GET)
   - Was: Truncated after description line
   - Fixed: Added complete operationId `get_notification_dnd_status`, tags, responses, security

3. `/api/v1/hub/notifications/read-all` (POST)
   - Was: Truncated after description line
   - Fixed: Added complete operationId `mark_all_notifications_read`, tags, responses, requestBody, security

4. `/api/v1/hub/notifications/rules/{rule_id}` (DELETE)
   - Was: Truncated after description line
   - Fixed: Added complete operationId `remove_notification_rule`, tags, responses, security

### All 12 Notification Paths (verified match with HA):
1. `/api/v1/hub/notifications` (GET) - `get_notification_dashboard`
2. `/api/v1/hub/notifications/batch` (POST) - `configure_notification_batch` ✓ FIXED
3. `/api/v1/hub/notifications/batch/flush` (POST) - `flush_notification_batch`
4. `/api/v1/hub/notifications/dnd` (POST) - `set_notification_dnd`
5. `/api/v1/hub/notifications/dnd/status` (GET) - `get_notification_dnd_status` ✓ FIXED
6. `/api/v1/hub/notifications/history` (GET) - `get_notification_history`
7. `/api/v1/hub/notifications/read-all` (POST) - `mark_all_notifications_read` ✓ FIXED
8. `/api/v1/hub/notifications/rules` (GET, POST) - `get_notification_rules`, `add_notification_rule`
9. `/api/v1/hub/notifications/rules/{rule_id}` (DELETE) - `remove_notification_rule` ✓ FIXED
10. `/api/v1/hub/notifications/send` (POST) - `send_notification`
11. `/api/v1/hub/notifications/stats` (GET) - `get_notification_stats`
12. `/api/v1/hub/notifications/{notification_id}/read` (POST) - `mark_notification_read`

### One-Shot Recheck Result:
```
HA operationIds (13):  add_notification_rule, configure_notification_batch, flush_notification_batch,
                      get_notification_dashboard, get_notification_dnd_status, get_notification_history,
                      get_notification_rules, get_notification_stats, mark_all_notifications_read,
                      mark_notification_read, remove_notification_rule, send_notification, set_notification_dnd

Core operationIds (13): SAME AS HA

diff: ✓ MATCH
```