# RAG Enhanced Search UI Spec (Slice 137)

**Status:** Drafted (Core-Lane)
**Design-Contract:** Hybrid-Search Integration

## 1. Overview
This specification defines the enhanced search endpoint for the RAG pipeline, integrating local vector search with SearXNG web results for a hybrid context.

## 2. API Contract: POST `/api/v1/rag/search/enhanced`

### Request Payload
```json
{
  "query": "String",
  "max_results": 10,
  "hybrid_ratio": 0.7,
  "context_depth": "full",
  "source_agent": "String (optional)"
}
```

### Response Structure
```json
{
  "summary": "String (LLM generated if enabled)",
  "local_hits": [
    {
      "id": "String",
      "score": 0.98,
      "text": "String",
      "metadata": {}
    }
  ],
  "web_results": [
    {
      "title": "String",
      "url": "String",
      "content": "String",
      "engine": "SearXNG"
    }
  ],
  "execution_id": "UUID-v4",
  "provenance": {
    "source_agent": "pilotclaw",
    "timestamp": "ISO-8601"
  }
}
```

## 3. Core Implementation (Slice 137)
1.  **Hybrid Logic:** Implement aggregator in `copilot_core/rag/enhanced_search.py`.
2.  **SearXNG Bridge:** Ensure clean error handling (Circuit Breaker) for web calls.
3.  **Audit:** Add standard provenance and execution tracking.

---
**Next Step:** Implement `enhanced_search.py` in Core-Worktree.
