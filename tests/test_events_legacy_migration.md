# Legacy Test Migration: events_endpoint

**Status:** Analyzed (2026-04-05)
**Slice:** 127

## Legacy Test Files

| File | Status | Action |
|------|--------|--------|
| `copilot_core/rootfs/usr/src/app/tests/test_events_endpoint.py` | Legacy | Migrate to deprecated status |
| `tests/test_events_ingest_deprecated.py` | ✅ Correct | Already deprecated |
| `tests/test_events_ingest_contract.py` | ✅ Correct | Contract test active |

## Decision

**Legacy test `test_events_endpoint.py`** tests the deprecated `/api/v1/events` endpoint.

**Action:**
1. Add deprecation header to test file
2. Mark tests as expecting 410 Gone
3. Document migration to WebSocket API

## Migration Path

```
OLD: POST /api/v1/events (deprecated, returns 410)
NEW: WebSocket /api/v1/ha-events/subscribe
```

**Next:** Update test expectations or archive legacy test.
