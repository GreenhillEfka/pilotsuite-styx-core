# Slice 143: Vector API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** vector.py (17KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/vector/search | ✅ Vector search |
| POST /api/v1/vector/upsert | ✅ Upsert documents |
| DELETE /api/v1/vector/delete | ✅ Delete documents |

## Expansion Needed

1. **Collection Management** — Create/delete/list collections
2. **Similarity Metrics** — Configurable similarity (cosine, dot, euclidean)
3. **Batch Operations** — Bulk upsert/delete
4. **Vector Analytics** — Collection stats, dimension info

## Decision

**Action:** Add collection management + batch operations

**Priority:**
1. Collection management
2. Batch operations
3. Similarity metrics
4. Vector analytics

