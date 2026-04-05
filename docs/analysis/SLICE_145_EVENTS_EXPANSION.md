# Slice 145: Events API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** events.py (25KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/events | ✅ List events |
| POST /api/v1/events | ✅ Create event |
| GET /api/v1/events/stream | ✅ Event stream |

## Expansion Needed

1. **Event Filtering** — Advanced filter by type, source, time
2. **Event Aggregation** — Group events by patterns
3. **Event Replay** — Replay events for debugging
4. **Event Export** — Export to external systems

## Decision

**Action:** Add filtering + aggregation endpoints

**Priority:**
1. Event filtering
2. Event aggregation
3. Event replay
4. Event export

