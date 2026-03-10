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