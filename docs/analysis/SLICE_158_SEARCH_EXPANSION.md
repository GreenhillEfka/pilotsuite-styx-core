# Slice 158: Search API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** search.py (19KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/search | ✅ Global search |
| GET /api/v1/search/suggest | ✅ Search suggestions |

## Expansion Needed

1. **Advanced Search** — Filters, facets, sorting
2. **Search History** — Track user search history
3. **Search Analytics** — Popular searches, no-result queries
4. **Saved Searches** — Save and reuse search queries

## Decision

**Action:** Add advanced search + analytics endpoints

**Priority:**
1. Advanced search
2. Search analytics
3. Search history
4. Saved searches

