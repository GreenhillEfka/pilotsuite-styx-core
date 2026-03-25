# RAG Module (Retrieval-Augmented Generation)

Das RAG-Modul bietet hybride Suche kombiniert aus **BM25** (lexikalisch) und **Semantischer Suche** (Embeddings) mit **Reciprocal Rank Fusion (RRF)**.

## Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│                          RAG Pipeline                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Query → [Query Router] ─┬─▶ BM25 (lexikalisch) ─┐            │
│                           │                       │              │
│                           └─▶ Semantik (Embeddings) │            │
│                                                   ▼            │
│                                          [RRF Fusion]           │
│                                                   │            │
│                                                   ▼            │
│                                           Ranked Results       │
└─────────────────────────────────────────────────────────────────┘
```

## Module

| Modul | Beschreibung |
|-------|-------------|
| `bm25.py` | BM25 Retriever mit SQLite-Persistenz |
| `semantic_backend.py` | Embedding-basierter Retriever (sentence-transformers) |
| `hybrid_search.py` | RRF Fusion (Reciprocal Rank Fusion) |
| `query_router.py` | Query-Klassifikation (local/web/hybrid) |
| `indexer.py` | Namespace-basierter Index-Manager |
| `searxng_client.py` | SearXNG Web-Suche Integration |

## API Endpoints

### GET/POST `/api/v1/rag/search`

Hybride Suche (BM25 + Semantisch).

**GET Beispiel:**
```bash
curl "http://localhost:5000/api/v1/rag/search?q=heizung+einstellung&namespace=ha_docs&top_k=5"
```

**POST Beispiel:**
```bash
curl -X POST http://localhost:5000/api/v1/rag/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "heizung einstellung",
    "namespace": "ha_docs",
    "top_k": 10,
    "use_lexical": true,
    "use_semantic": true,
    "rrf_k": 60,
    "lexical_weight": 1.0,
    "semantic_weight": 1.0
  }'
```

**Response:**
```json
{
  "namespace": "ha_docs",
  "query": "heizung einstellung",
  "mode": "hybrid_rrf",
  "results": [
    {
      "id": "doc_123",
      "score": 0.95,
      "text": "Heizung auf 21°C stellen...",
      "metadata": {"source": "manual"},
      "fused_score": 0.95,
      "lexical_rank": 1,
      "semantic_rank": 2
    }
  ],
  "result_count": 1,
  "took_ms": 45.2,
  "cache_hit": false
}
```

### POST `/api/v1/rag/search/bm25`

Nur BM25 lexikalische Suche.

```bash
curl -X POST http://localhost:5000/api/v1/rag/search/bm25 \
  -H "Content-Type: application/json" \
  -d '{"query": "licht", "namespace": "ha_docs", "top_k": 5}'
```

### POST `/api/v1/rag/search/semantic`

Nur semantische Suche (Embeddings).

```bash
curl -X POST http://localhost:5000/api/v1/rag/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "warme beleuchtung", "namespace": "ha_docs", "top_k": 5}'
```

### POST `/api/v1/rag/search/enhanced`

Erweiterte Suche mit SearXNG Web-Integration.

```bash
curl -X POST http://localhost:5000/api/v1/rag/search/enhanced \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Wetter heute",
    "namespace": "ha_docs",
    "use_web": true,
    "searxng_categories": ["weather", "general"],
    "top_k": 10
  }'
```

### POST `/api/v1/rag/index`

Dokumente indizieren.

```bash
curl -X POST http://localhost:5000/api/v1/rag/index \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "ha_docs",
    "documents": [
      {"id": "doc1", "text": "Heizung 21°C", "metadata": {"room": "living"}},
      {"id": "doc2", "text": "Licht dimmen", "metadata": {"room": "bedroom"}}
    ],
    "index_semantic": true
  }'
```

### GET `/api/v1/rag/stats`

Index-Statistiken abrufen.

```bash
curl "http://localhost:5000/api/v1/rag/stats?namespace=ha_docs"
```

### POST `/api/v1/rag/rerank`

Bestehende Ergebnislisten neu ranken.

```bash
curl -X POST http://localhost:5000/api/v1/rag/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "lexical_hits": [{"id": "doc1", "score": 0.9, "rank": 1}],
    "semantic_hits": [{"id": "doc2", "score": 0.85, "rank": 1}],
    "top_k": 10,
    "rrf_k": 60
  }'
```

### POST `/api/v1/rag/cache/clear`

Cache invalidieren.

```bash
curl -X POST http://localhost:5000/api/v1/rag/cache/clear \
  -H "Content-Type: application/json" \
  -d '{"namespace": "ha_docs"}'
```

## Python API

### Namespace-basierter Index-Manager

```python
from copilot_core.rag import IndexManager, BM25Document

# Singleton-Instanz
mgr = IndexManager.get_instance()

# Namespace erstellen
mgr.create_namespace(
    name="user_docs",
    description="User documentation",
    tags=["docs", "user"]
)

# Dokumente indizieren
from copilot_core.rag.bm25 import BM25Document

docs = [
    BM25Document(doc_id="1", text="Heizung einstellen", metadata={"room": "all"}),
    BM25Document(doc_id="2", text="Licht dimmen", metadata={"room": "living"}),
]

success_count, errors = mgr.index("user_docs", docs)

# Suchen
results = mgr.search(
    namespace="user_docs",
    query="heizung",
    top_k=10,
    include_text=True,
    include_metadata=True
)

for hit in results:
    print(f"{hit.doc_id}: {hit.score:.2f} - {hit.text}")

# Namespace-Statistiken
stats = mgr.namespace_stats("user_docs")
print(f"Documents: {stats.doc_count}")

# Alle Namespaces auflisten
namespaces = mgr.list_namespaces()
for ns in namespaces:
    print(f"{ns.name}: {ns.doc_count} docs")
```

### Query Router (Query-Klassifikation)

```python
from copilot_core.rag import classify_query, QueryType

result = classify_query("Wetter heute")
print(result.query_type)  # QueryType.WEB
print(result.confidence)  # 0.90
print(result.reasoning)  # "Web keywords with time-sensitive context"

# Oder einfach:
should_web = classify_query("Wie ist das Wetter?").use_web_search
```

### SearXNG Client

```python
from copilot_core.rag import get_searxng_client

client = get_searxng_client(base_url="http://localhost:8080")
results = await client.search(
    query="Wetter München",
    categories=["weather", "general"],
    top_k=5
)

for r in results:
    print(f"{r.title}: {r.url}")
```

### Hybrid Search (Low-Level)

```python
from copilot_core.rag import BM25SqliteIndex, BM25Config
from copilot_core.rag.hybrid_search import reciprocal_rank_fusion, RankedHit

# BM25 Index
bm25 = BM25SqliteIndex(BM25Config())

# Suchen
lexical_hits = bm25.search(namespace="docs", query="heizung", top_k=10)

# In RankedHit umwandeln
lexical_ranked = [
    RankedHit(doc_id=h.doc_id, score=h.score, rank=h.rank)
    for h in lexical_hits
]

# Mit semantischen Ergebnissen fusionieren
from copilot_core.rag.semantic_backend import rag_semantic_search

semantic_raw = rag_semantic_search(namespace="docs", query="heizung", top_k=10)
semantic_ranked = [
    RankedHit(doc_id=r["id"], score=r["score"], rank=i+1)
    for i, r in enumerate(semantic_raw)
]

# RRF Fusion
fused = reciprocal_rank_fusion(
    lexical_hits=lexical_ranked,
    semantic_hits=semantic_ranked,
    top_k=10,
    k=60  # RRF constant
)

for f in fused:
    print(f"{f.doc_id}: {f.fused_score:.3f}")
```

## Konfiguration

### Environment Variables

| Variable | Beschreibung | Default |
|----------|-------------|---------|
| `COPILOT_CORE_RAG_DB_PATH` | BM25 SQLite DB Pfad | `/data/copilot_core_rag.sqlite3` |
| `COPILOT_CORE_RAG_REGISTRY` | Namespace Registry DB | `/data/rag_namespaces.db` |
| `COPILOT_CORE_RAG_SEARXNG_URL` | SearXNG Base URL | `http://localhost:8080` |
| `COPILOT_CORE_RAG_SEMANTIC_BACKEND` | Externer Semantic Backend | (optional) |

### Namespace Validierung

Namespace-Namen müssen folgendem Pattern entsprechen:
- `^[a-zA-Z0-9_-]+$`
- Länge: 1-128 Zeichen
- Erlaubt: Buchstaben, Zahlen, Unterstrich, Bindestrich

## Query Types

Der Query Router klassifiziert Queries in drei Typen:

| Typ | Keywords | Beschreibung |
|-----|----------|--------------|
| `LOCAL` | "verbrauch", "energie", "entity", "sensor" | Lokale HA-Daten |
| `WEB` | "wetter", "nachrichten", "news", "wikipedia" | Externe Web-Daten |
| `HYBRID` | Gemischte Keywords | Beide Quellen |

## Performance

- **BM25**: ~10ms für 10k Dokumente
- **Semantisch**: ~50-200ms (abhängig von Embedding-Modell)
- **Cache**: 600s TTL, 1000 Einträge lokal
- **RRF Fusion**: <1ms

## Abhängigkeiten

- `rank_bm25` (optional, für reines BM25)
- `sentence-transformers` (für Semantische Suche)
- `aiohttp` (für SearXNG Client)
- SQLite (built-in)

## Tests

```bash
python -m pytest tests/test_rag*.py -v
```

## Integration

Das RAG-Modul ist registriert in:
- `copilot_core.api.v1.rag` — Flask Blueprint mit allen Endpoints
- `copilot_core.app` — Blueprint wird in Flask App registriert
