# Slice 159: Tags API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** tags.py (9KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/tags | ✅ List tags |
| POST /api/v1/tags | ✅ Create tag |

## Expansion Needed

1. **Tag Hierarchies** — Parent/child tag relationships
2. **Tag Usage** — See what entities use each tag
3. **Tag Merging** — Merge duplicate tags
4. **Tag Analytics** — Usage patterns, popular tags

## Decision

**Action:** Add hierarchies + usage endpoints

**Priority:**
1. Tag hierarchies
2. Tag usage tracking
3. Tag merging
4. Tag analytics

