# Entwicklungsrunde: Robustness, Performance & Coverage

## Iteration 1 — Robustness: API-Validation & Error Handling

**Ziel:** Alle API-Endpunkte mit Input-Validierung absichern, bare excepts durch spezifische Exceptions ersetzen, konsistente Fehler-Responses.

### 1.1 API Request Validation Decorator
- Neuer `@validate_json(schema)` Decorator für konsistente Request-Body-Validierung
- Schema-basierte Validierung mit klaren 400-Responses
- Anwenden auf: styx_chat, integration/feedback, events_ingest, conversation

### 1.2 Input Sanitization & Length Limits
- Chat-Query: max 10.000 Zeichen, Strip, non-empty Check
- Entity-IDs: Format-Validierung
- TZ_OFFSET: Bounds-Check (-12..+14)
- Graph-API: hops Parameter Bounds (1-5)

### 1.3 Bare Except Cleanup
- event_store.py: Spezifische Exceptions statt bare except
- user_preferences.py: IOError/JSONDecodeError statt Exception
- graph.py: ValueError statt bare except für int-Parsing
- automation_api.py: Strukturierte Error-Codes statt String-Matching

### 1.4 Konsistente Error-Response-Struktur
- Einheitliches Format: `{"ok": false, "error": "message", "code": "ERROR_CODE"}`
- HTTP Status Codes standardisieren

---

## Iteration 2 — Performance: Data Structures & Caching

**Ziel:** Performance-Bottlenecks beheben, effizientere Datenstrukturen, intelligenteres Caching.

### 2.1 Deque statt List für LRU/FIFO
- candidates.py: `list.pop(0)` → `collections.deque` (O(1) statt O(n))
- event_store.py: Dedup-Pruning optimieren

### 2.2 Event Pipeline Hardening
- event_store.py: Dedup-Map Shrink-Strategie verbessern (gradual statt 50% drop)
- Bounded dedup mit TTL-basiertem Expiry statt Size-Check

### 2.3 Integration Bus Resilience
- Subscriber-Timeout: Max 5s pro Callback, dann Warning
- Dead-Letter Queue: Failed events für Debugging speichern
- Bus-Metrics: Latenz pro Event-Typ tracken

### 2.4 Connection Pool Improvements
- Health-Check Retry mit Backoff
- Connection-State Tracking (healthy/degraded/down)

---

## Iteration 3 — Test Coverage: Critical Path Tests

**Ziel:** Fehlende Tests für kritische Pfade ergänzen, Edge Cases absichern.

### 3.1 Event Pipeline Tests
- event_store: Batch ingestion mit Dedup
- event_store: Prune-Zyklen und Bounded-Map
- event_processor: End-to-End Pipeline

### 3.2 Integration Bus Edge Cases
- Subscriber Exception Isolation
- Event Ordering Guarantees
- High-Volume Throughput Test
- Unsubscribe-During-Publish Safety

### 3.3 NeuronManager Callback Chain
- Multiple Callbacks pro Event
- Callback Exception → andere Callbacks laufen weiter
- Bus Integration unter Last

### 3.4 API Validation Tests
- Alle neuen Validierungen testen (leere Inputs, zu lange Strings, invalide Typen)
- Error-Response Format Tests
