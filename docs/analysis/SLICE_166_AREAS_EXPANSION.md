# Slice 166: Areas API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** areas.py (8KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/areas | ✅ List areas |
| POST /api/v1/areas | ✅ Create area |

## Expansion Needed

1. **Area Hierarchy** — Parent/child area relationships
2. **Area Devices** — List devices per area
3. **Area Entities** — List entities per area
4. **Area Statistics** — Device/entity counts, coverage

## Decision

**Action:** Add hierarchy + devices + entities + statistics endpoints

**Priority:**
1. Area hierarchy
2. Area devices listing
3. Area entities listing
4. Area statistics

