# Slice 161: Annotations API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** annotations.py (7KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/annotations | ✅ List annotations |
| POST /api/v1/annotations | ✅ Create annotation |

## Expansion Needed

1. **Annotation Layers** — Organize annotations in layers
2. **Annotation Queries** — Filter by type, zone, time
3. **Annotation Export** — Export annotations to external formats
4. **Annotation Sharing** — Share annotations between users

## Decision

**Action:** Add layers + query endpoints

**Priority:**
1. Annotation layers
2. Annotation queries
3. Annotation export
4. Annotation sharing

