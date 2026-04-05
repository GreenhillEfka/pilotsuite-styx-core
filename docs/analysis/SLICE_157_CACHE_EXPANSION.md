# Slice 157: Cache API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** cache.py (11KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/cache/stats | ✅ Cache statistics |
| DELETE /api/v1/cache/clear | ✅ Clear cache |

## Expansion Needed

1. **Cache Keys Inspection** — List/view cached keys
2. **Cache Invalidation** — Targeted key invalidation
3. **Cache TTL Management** — Configure TTL per key/pattern
4. **Cache Analytics** — Hit/miss rates, eviction tracking

## Decision

**Action:** Add keys inspection + invalidation endpoints

**Priority:**
1. Cache keys inspection
2. Cache invalidation
3. Cache TTL management
4. Cache analytics

