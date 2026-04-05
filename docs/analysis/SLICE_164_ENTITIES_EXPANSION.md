# Slice 164: Entities API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** entities.py (28KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/entities | ✅ List entities |
| GET /api/v1/entities/<id> | ✅ Get entity |

## Expansion Needed

1. **Entity Bulk Operations** — Bulk update/delete entities
2. **Entity History** — State history per entity
3. **Entity Statistics** — Usage patterns, change frequency
4. **Entity Relationships** — Parent/child, linked entities

## Decision

**Action:** Add bulk operations + history + statistics endpoints

**Priority:**
1. Entity bulk operations
2. Entity history
3. Entity statistics
4. Entity relationships

