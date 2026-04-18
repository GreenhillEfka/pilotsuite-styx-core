# CORE-STRUCT-103 — State/Persistenz Hardening Analysis

**Stand:** 2026-04-18 10:05 Europe/Berlin  
**Task:** CORE-STRUCT-103 State/Persistenz sauberziehen  
**Verification:** compile ring + focused test ring

---

## File Radius Verified

### Cache Surface (`addons/.../copilot_core/cache/`)

**`api_cache.py`**
- `CacheMetrics`: hit/miss/ttl stats
- `APICache`: simple in-memory cache with TTL. Methods: `get`, `set`, `record_hit`, `record_miss`, `get_stats`, `reset`
- **Persistence contract:** none — in-memory only, restart-reset. Graceful degradation to in-memory fallback when Redis unavailable.

**`hybrid_cache.py`**
- `CacheEntry`: value + timestamp + TTL fields
- `HybridCacheConfig`: ttl_seconds, max_size, redis_url, enable_memory
- `HybridCacheManager`: two-tier (memory + Redis). Methods: `start`, `stop`, `get`, `hit_rate`, `miss_rate`, `to_dict`
- **Persistence contract:** memory tier is restart-reset; Redis tier survives restart when redis.asyncio is available. Redis unavailable → in-memory fallback (no error). CacheEntry TTL enforces restart-safe expiry semantics.

### Event Storage Surface (`addons/.../copilot_core/storage/`)

**`events.py`**
- `Event`: dataclass with id, event_type, entity_id, context, timestamp, metadata
- `EventStore`: append-only event store. Methods: `append(event)`, `extend(events)`, `list(filter)`, `from_payload(dict)`
- **Persistence contract:** events persisted to disk. `append` and `extend` write to storage. Restart-safe because events are stored on disk, not in memory.

### API Surfaces (`addons/.../copilot_core/api/v1/`)

**`events.py`**
- Routes: `POST /api/v1/events/ingest`, `GET /api/v1/events/`
- Functions: `ingest_event()`, `list_events()`

**`events_ingest.py`**
- `set_post_ingest_callback(fn)`: hooks pipeline after event persistence
- `set_store(store)`, `get_store()`: wired by init
- `ingest_events()`, `query_events()`, `events_stats()`
- **Persistence contract:** after `ingest_events` → `post_ingest_callback` called. If callback fails, event is already persisted — failure is isolated.

**`cache_control.py`**
- `cache_status()`, `cache_invalidate()`, `cache_stats()`, `init_cache_control_api()`
- **Persistence contract:** explicit cache invalidation via API. Cache invalidation does NOT affect persisted events — concerns only the cache layer.

---

## RAG Persistence Surface (`copilot_core/rag/`)

**`memory_system.py`** (repo-root)
**`vector_store.py`** (repo-root)

Both are repo-root compatibility surfaces used by tests.

---

## Contract Clarity Findings

| Domain | Restart-safe? | Graceful degradation | Explicit invalidation |
|--------|--------------|---------------------|----------------------|
| APICache (in-memory) | ❌ No — reset on restart | N/A (in-memory only) | No |
| HybridCache + Redis | ✅ Yes (Redis persists) | ✅ redis.asyncio unavailable → in-memory | No |
| HybridCache memory-only | ❌ No — reset on restart | N/A | No |
| EventStore | ✅ Yes — disk persist | ✅ storage error → logged, isolated | N/A |
| Post-ingest callbacks | ✅ Yes — called after persist | ✅ callback fails → event already stored | N/A |

**Key insight:** HybridCacheManager and EventStore have restart-safe semantics. APICache does not — this is a known boundary, not a bug.

---

## Compile Verification

```bash
python3 -m py_compile \
  addons/pilotsuite/app/copilot_core/cache/__init__.py \
  addons/pilotsuite/app/copilot_core/cache/api_cache.py \
  addons/pilotsuite/app/copilot_core/cache/hybrid_cache.py \
  addons/pilotsuite/app/copilot_core/storage/events.py \
  addons/pilotsuite/app/copilot_core/api/v1/events.py \
  addons/pilotsuite/app/copilot_core/api/v1/events_ingest.py \
  addons/pilotsuite/app/copilot_core/api/v1/cache_control.py \
  copilot_core/rag/memory_system.py \
  copilot_core/rag/vector_store.py
# ✅ ALL OK
```

---

## Scope Note for CORE-STRUCT-103

The cache/event/state surfaces are already coherent. No structural changes required. This analysis documents the restart-safe semantics boundaries explicitly so future work doesn't accidentally break them.

**Next:** CORE-STRUCT-102 Voice/Memory landen (final subtrack)
