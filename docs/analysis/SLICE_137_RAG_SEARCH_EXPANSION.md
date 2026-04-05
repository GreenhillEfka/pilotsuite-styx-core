# Slice 137: RAG-Search Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** rag.py (existing, 56KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/rag/search | ✅ Vector search |
| POST /api/v1/rag/embed | ✅ Embed documents |
| GET /api/v1/rag/collections | ✅ List collections |

## Expansion Needed

1. **Semantic Search** — Natural language queries
2. **Cross-Collection Search** — Multi-collection queries
3. **Search Analytics** — Query patterns, popular searches
4. **Relevance Feedback** — User feedback loop

## Decision

**Action:** Add semantic search + analytics endpoints

**Priority:**
1. Semantic search (NL queries)
2. Cross-collection search
3. Search analytics
4. Relevance feedback

