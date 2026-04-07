# RAG Hybrid Search API

Hybrid Search kombiniert BM25-basierte lexikalische Suche mit semantischer Vektorsuche
und fusioniert die Ergebnisse mittels Reciprocal Rank Fusion (RRF).

## Architektur

```
Client Request
      │
      ▼
  /api/rag/search
      │
      ├── BM25 (SQLite)  ──────┐
      │   Okapi BM25 Scoring   │
      │   Term Frequencies     │
      │                        ▼
      │                   ┌─────────┐
      │                   │  RRF    │
      │                   │ Fusion  │
      │                   └────┬────┘
      │                        │
      └── Semantic (optional)──┘
          Embedding Search
                               ▼
                         Fused Results
```

## Endpoints

Alle Endpoints sind unter `/api/rag/` erreichbar (nicht `/api/v1/rag/`).
Authentifizierung via `X-Auth-Token` Header oder `Bearer` Token.

### 1. POST /api/rag/search — Hybrid Search

Kombinierte Suche mit BM25 + Semantic + RRF.

**Request:**
```json
{
  "query": "Python web framework",
  "namespace": "default",
  "top_k": 10,
  "use_lexical": true,
  "use_semantic": true,
  "rrf_k": 60,
  "lexical_weight": 1.0,
  "semantic_weight": 1.0,
  "include_text": true,
  "include_metadata": true
}
```

**Response:**
```json
{
  "namespace": "default",
  "query": "Python web framework",
  "mode": "hybrid_rrf",
  "results": [
    {
      "id": "doc2",
      "score": 0.032787,
      "fused_score": 0.032787,
      "lexical_rank": 1,
      "semantic_rank": 2,
      "lexical_score": 3.456,
      "semantic_score": 0.891,
      "text": "Flask is a Python web framework",
      "metadata": {"lang": "en"}
    }
  ],
  "result_count": 3,
  "warnings": [],
  "took_ms": 12.345
}
```

**Modi:**
- `hybrid_rrf` — beide Sucharten aktiv, Ergebnisse via RRF fusioniert
- `bm25` — nur lexikalische Suche (`use_semantic: false`)
- `semantic` — nur semantische Suche (`use_lexical: false`)

### 2. POST /api/rag/search/bm25 — BM25-Only

Direkte lexikalische Suche ohne Semantic-Komponente.

**Request:**
```json
{
  "query": "Flask",
  "namespace": "default",
  "top_k": 10,
  "include_text": true,
  "include_metadata": true
}
```

**Response:**
```json
{
  "namespace": "default",
  "query": "Flask",
  "mode": "bm25",
  "results": [
    {"id": "doc2", "score": 2.345, "rank": 1, "text": "...", "metadata": {...}}
  ],
  "result_count": 1,
  "took_ms": 5.678
}
```

### 3. POST /api/rag/search/semantic — Semantic-Only

Reine Vektorsuche (setzt konfigurierten Semantic-Backend voraus).

**Request:**
```json
{
  "query": "web development",
  "namespace": "default",
  "top_k": 10
}
```

**Response:** Analog zu BM25, mode = `"semantic"`.
Ohne Backend werden `warnings` zurueckgegeben und `result_count` ist 0.

### 4. POST /api/rag/rerank — RRF Reranking

Fusioniert zwei vorhandene Hit-Listen via Reciprocal Rank Fusion.
Erfordert kein Indexing — arbeitet auf uebergebenen Daten.

**Request:**
```json
{
  "lexical_hits": [
    {"id": "a", "score": 5.0, "rank": 1},
    {"id": "b", "score": 3.0, "rank": 2}
  ],
  "semantic_hits": [
    {"id": "b", "score": 0.9, "rank": 1},
    {"id": "c", "score": 0.8, "rank": 2}
  ],
  "top_k": 10,
  "rrf_k": 60,
  "lexical_weight": 1.0,
  "semantic_weight": 1.0
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "b",
      "fused_score": 0.032787,
      "lexical_rank": 2,
      "semantic_rank": 1,
      "lexical_score": 3.0,
      "semantic_score": 0.9
    }
  ],
  "result_count": 3,
  "rrf_k": 60,
  "took_ms": 0.123
}
```

### 5. GET /api/rag/stats — Index-Statistiken

Gibt BM25-Index-Statistiken und Request-Metriken zurueck.

**Query Parameter:** `?namespace=default` (optional)

**Response:**
```json
{
  "namespace": "default",
  "doc_count": 150,
  "term_count": 2345,
  "posting_count": 8901,
  "avg_doc_len": 45.6,
  "total_doc_len": 6840,
  "updated_at": 1709312400.0,
  "db_path": "/data/copilot_core_rag.sqlite3",
  "db_size_bytes": 524288,
  "schema_version": 1,
  "semantic_backend": null,
  "metrics": {
    "search_requests": 42,
    "index_requests": 5,
    "rerank_requests": 3,
    "errors": 0,
    "avg_search_ms": 15.234,
    "last_search_ms": 12.345,
    "last_error": null
  }
}
```

### 6. POST /api/rag/index — Dokumente indexieren

Upsert von Dokumenten in den BM25-Index (und optional Semantic-Index).

**Request:**
```json
{
  "namespace": "default",
  "documents": [
    {
      "id": "doc1",
      "text": "Python is a great programming language",
      "metadata": {"lang": "en", "topic": "programming"}
    }
  ],
  "index_semantic": true
}
```

**Response:**
```json
{
  "namespace": "default",
  "bm25_indexed": 1,
  "semantic_indexed": 0,
  "errors": [],
  "warnings": ["semantic backend not configured; BM25-only indexing performed"],
  "took_ms": 8.901
}
```

**Limits:**
- Max 2000 Dokumente pro Request
- `doc_id` und `text` sind Pflichtfelder
- `metadata` ist optional (beliebiges JSON-Objekt)

## RRF Algorithmus

Reciprocal Rank Fusion kombiniert Rankings aus verschiedenen Retrievern:

```
score(d) = Σ weight_i / (k + rank_i(d))
```

- `k` = 60 (Standard, konfigurierbar via `rrf_k`)
- `weight_i` = Gewichtung pro Retriever (`lexical_weight`, `semantic_weight`)
- Dokumente in beiden Listen erhalten hoehere Scores

**Vorteile:**
- Score-Normalisierung nicht notwendig (rank-basiert)
- Robust gegenueber unterschiedlichen Score-Skalen
- Einfach erweiterbar fuer weitere Retriever

## BM25 Konfiguration

| Parameter | Default | Beschreibung |
|-----------|---------|-------------|
| `k1` | 1.5 | Term-Frequency-Saettigung |
| `b` | 0.75 | Dokumentlaengen-Normalisierung |
| `db_path` | `/data/copilot_core_rag.sqlite3` | SQLite DB Pfad |

Umgebungsvariablen:
- `COPILOT_CORE_RAG_DB_PATH` — DB-Pfad ueberschreiben
- `COPILOT_CORE_RAG_SEMANTIC_BACKEND` — Python-Modul fuer Semantic-Backend

## Semantic Backend

Das Semantic-Backend ist optional und wird via Umgebungsvariable konfiguriert:

```bash
COPILOT_CORE_RAG_SEMANTIC_BACKEND=copilot_core.semantic.backend
```

Das Modul muss zwei Funktionen exportieren:
- `semantic_search(namespace, query, top_k)` → Liste von `{id, score}`
- `semantic_index(namespace, documents)` → Anzahl indexierter Dokumente

## Thread-Sicherheit

- BM25-Index: Singleton mit Double-Checked Locking
- SQLite: WAL-Modus mit Thread-lokalen Connections
- Metrics: Thread-safe via `threading.Lock`
- Semantic Backend: Lazy-Loading mit Lock-Schutz
