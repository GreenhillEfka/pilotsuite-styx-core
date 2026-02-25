# PilotSuite Core Add-on -- API-Referenz

> Vollstaendige REST-API-Dokumentation fuer das PilotSuite Core Add-on (Styx).
> Flask + Waitress auf Port **8909**.

---

## Inhaltsverzeichnis

1. [Authentifizierung](#1-authentifizierung)
2. [OpenAI-kompatible Endpoints](#2-openai-kompatible-endpoints)
3. [System-Endpoints](#3-system-endpoints)
4. [Brain Graph](#4-brain-graph)
5. [Habitus Miner](#5-habitus-miner)
6. [Candidates](#6-candidates)
7. [Mood Engine](#7-mood-engine)
8. [Events](#8-events)
9. [Neurons](#9-neurons)
10. [Search](#10-search)
11. [Notifications](#11-notifications)
12. [Knowledge Graph](#12-knowledge-graph)
13. [Vector Store](#13-vector-store)
14. [Weather](#14-weather)
15. [Energy](#15-energy)
16. [Media Zones](#16-media-zones)
17. [System Health](#17-system-health)
18. [Performance](#18-performance)
19. [Habitus Dashboard Cards](#19-habitus-dashboard-cards)
20. [Conversation (Legacy)](#20-conversation-legacy)
21. [Dev / Debug](#21-dev--debug)
22. [Response-Format und Header](#22-response-format-und-header)
23. [Circuit Breaker](#23-circuit-breaker)
24. [Rate Limiting](#24-rate-limiting)

---

## 1. Authentifizierung

Alle Endpoints (ausser `/health` und `/version`) erfordern eine gueltige Authentifizierung.

### Token-Uebermittlung

Es gibt zwei Moeglichkeiten, den Token zu senden:

| Methode | Header | Format |
|---------|--------|--------|
| Bearer Token | `Authorization` | `Bearer <token>` |
| Direkter Token | `X-Auth-Token` | `<token>` |

### Konfiguration

Der Token wird in der HACS-Integration konfiguriert und im Core Add-on ueber eine der folgenden Quellen gelesen:

1. Umgebungsvariable `COPILOT_AUTH_TOKEN`
2. `/data/options.json` -> Feld `auth_token`

### First-Run-Verhalten

Wenn **kein Token konfiguriert** ist (leerer String), werden alle Requests ohne Authentifizierung zugelassen. Dies ermoeglicht eine reibungslose Ersteinrichtung.

### Authentifizierung deaktivieren

Ueber `COPILOT_AUTH_REQUIRED=false` (Umgebungsvariable) oder `auth_required: false` in `options.json` kann die Authentifizierung vollstaendig deaktiviert werden.

### Fehlerantwort bei fehlgeschlagener Authentifizierung

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "ok": false,
  "error": "Authentication required",
  "message": "Valid X-Auth-Token header or Bearer token required"
}
```

---

## 2. OpenAI-kompatible Endpoints

Diese Endpoints sind kompatibel mit dem OpenAI-SDK, `extended_openai_conversation` (jekalmin) und jedem OpenAI-kompatiblen Client.

**Base-URL fuer OpenAI-SDK:**

```
http://<addon-host>:8909/v1
```

### POST /v1/chat/completions

Chat-Completion mit optionalem Streaming und Tool-Calling.

**Request:**

```http
POST /v1/chat/completions
Authorization: Bearer <token>
Content-Type: application/json

{
  "model": "qwen3:0.6b",
  "messages": [
    {"role": "system", "content": "Du bist ein hilfreicher Assistent."},
    {"role": "user", "content": "Schalte das Licht im Wohnzimmer ein."}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 1024,
  "tools": [...]
}
```

**Parameter:**

| Feld | Typ | Pflicht | Beschreibung |
|------|-----|---------|--------------|
| `messages` | Array | Ja | Chat-Nachrichten (role: system/user/assistant/tool) |
| `model` | String | Nein | Modell-Override (Default: konfiguriertes Modell) |
| `stream` | Boolean | Nein | SSE-Streaming aktivieren (Default: false) |
| `temperature` | Float | Nein | Sampling-Temperatur |
| `max_tokens` | Integer | Nein | Maximale Antwortlaenge |
| `tools` | Array | Nein | OpenAI-kompatible Tool-Definitionen |

**Response (nicht-streaming):**

```json
{
  "id": "chatcmpl-a1b2c3d4e5f6",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "qwen3:0.6b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Ich habe das Licht im Wohnzimmer eingeschaltet."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 42,
    "completion_tokens": 15,
    "total_tokens": 57
  },
  "system_fingerprint": "pilotsuite-ollama"
}
```

**Response mit Tool-Calls:**

Wenn das Modell Tool-Calling unterstuetzt und Tools angefordert werden, kann `finish_reason` den Wert `"tool_calls"` haben:

```json
{
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "",
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "ha.call_service",
              "arguments": "{\"domain\":\"light\",\"service\":\"turn_on\",\"service_data\":{\"entity_id\":\"light.wohnzimmer\"}}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}
```

**Streaming-Response (SSE):**

Bei `"stream": true` wird die Antwort als Server-Sent Events zurueckgegeben:

```
data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hallo"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**Rate-Limit:** 60 Calls pro Stunde (konfigurierbar ueber `LLM_MAX_CALLS_PER_HOUR`).

**Rate-Limit-Fehler:**

```json
{
  "error": {
    "message": "Rate limit exceeded",
    "type": "rate_limit_error",
    "code": "rate_limit_exceeded"
  }
}
```

### GET /v1/models

Listet alle verfuegbaren Modelle auf (von Ollama + konfiguriertes Default-Modell).

**Response:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "qwen3:0.6b",
      "object": "model",
      "created": 1700000000,
      "owned_by": "ollama"
    },
    {
      "id": "qwen3:0.6b",
      "object": "model",
      "created": 1700000000,
      "owned_by": "ollama"
    }
  ]
}
```

### GET /v1/models/:model_id

Einzelnes Modell abrufen.

**Response:**

```json
{
  "id": "qwen3:0.6b",
  "object": "model",
  "created": 1700000000,
  "owned_by": "ollama"
}
```

### Verfuegbare LLM-Modelle

| Modell | Groesse | Tool-Calling | Beschreibung |
|--------|---------|-------------|--------------|
| `qwen3:0.6b` | 400 MB | Ja | Default: schnell, low-RAM, Tool-Calling |
| `qwen3:4b` | 2.5 GB | Ja | Optional fuer hoehere Antwortqualitaet |
| `lfm2.5-thinking` | 731 MB | Nein | Optionales Legacy-Modell |
| `llama3.2:3b` | 2 GB | Ja | Meta 3B, 128K Kontext |
| `mistral:7b` | 4 GB | Ja | Bewaehrtes Function-Calling |
| `fixt/home-3b-v3` | 2 GB | Ja | HA-optimiert, 97% Genauigkeit |

---

## 3. System-Endpoints

### GET /health

Liveness-Probe. Liefert immer 200, solange der Prozess laeuft.

```json
{"ok": true, "time": "2025-01-15T10:30:00+00:00"}
```

### GET /ready

Readiness-Probe. Liefert 200 nur wenn kritische Services initialisiert sind, sonst 503.

```json
{
  "ready": true,
  "brain_graph": true,
  "conversation_memory": true,
  "vector_store": true,
  "uptime_s": 3600
}
```

### GET /version

Version und Name des Add-ons.

```json
{
  "name": "Styx",
  "suite": "PilotSuite",
  "version": "7.7.13",
  "time": "2025-01-15T10:30:00+00:00"
}
```

### GET /api/v1/health/deep

Tiefgehender Health-Check aller Services und externen Abhaengigkeiten.

**Response:**

```json
{
  "healthy": true,
  "version": "7.7.13",
  "uptime_s": 7200,
  "checks": {
    "brain_graph_service": true,
    "conversation_memory": true,
    "vector_store": true,
    "mood_service": true,
    "habitus_service": true,
    "neuron_manager": true,
    "ha_supervisor": true,
    "ollama": true,
    "conversation_memory_db": true,
    "vector_store_db": true,
    "disk_free_mb": 4096,
    "disk_used_pct": 35,
    "request_metrics": {
      "total": 1234,
      "slow": 5,
      "errors": 2
    },
    "circuit_breakers": [
      {"name": "ha_supervisor", "state": "closed", "failure_count": 0},
      {"name": "ollama", "state": "closed", "failure_count": 0}
    ]
  },
  "time": "2025-01-15T10:30:00+00:00"
}
```

### GET /api/v1/health/metrics

Request-Timing-Metriken: Endpoint-Latenzen, langsame Requests, Fehlerraten.

```json
{
  "total_requests": 5000,
  "slow_requests": 12,
  "errors": 3,
  "slow_threshold_s": 2.0,
  "top_endpoints_by_latency": {
    "POST /v1/chat/completions": {
      "count": 200,
      "total_ms": 45000,
      "max_ms": 8500,
      "errors": 1
    }
  },
  "uptime_s": 7200
}
```

### POST /api/v1/echo

Echo-Endpoint fuer Konnektivitaetstests. Erfordert Authentifizierung.

**Request:**

```json
{"test": "hello"}
```

**Response:**

```json
{
  "time": "2025-01-15T10:30:00+00:00",
  "received": {"test": "hello"}
}
```

### Agent-Status und Self-Heal (`/api/v1/agent/*`)

Token-protected Endpoints fuer HA-Zero-Config, Agent-Health und automatische Reparatur.

#### GET /api/v1/agent/status

Liefert den aktuellen Agent-/LLM-Status.

```json
{
  "ok": true,
  "agent_name": "Styx",
  "agent_version": "7.7.15",
  "status": "ready",
  "llm_available": true,
  "llm_model": "qwen3:0.6b",
  "llm_backend": "ollama",
  "features": ["conversation", "openai_compatible_api"]
}
```

#### POST /api/v1/agent/verify

Bidirektionaler Handshake fuer HA-Integration.

```json
{
  "message": "ha_handshake",
  "source": "ha_integration"
}
```

#### POST /api/v1/agent/self-heal

Best-effort Reparatur nach Setup/Update-Problemen.

Fuehrt u. a. aus:
- Provider-Konfiguration neu laden.
- Installierte Ollama-Modelle pruefen.
- Fehlende lokale Modelle im Hintergrund ziehen.

```json
{
  "reason": "auto_setup_connectivity_failed",
  "source": "ha_integration"
}
```

### Onyx Bridge (`/api/v1/onyx/*`)

Token-protected Bruecke fuer Onyx-Agenten: deterministische HA-Service-Calls mit optionalem State-Rueckkanal.

#### GET /api/v1/onyx/status

Liefert den Bridge-Status und die HA-Reachability.

```json
{
  "ok": true,
  "bridge": "onyx",
  "supervisor_api": "http://supervisor/core/api",
  "has_supervisor_token": true,
  "ha_reachable": true,
  "allowed_domains": ["light", "switch", "scene"]
}
```

#### POST /api/v1/onyx/ha/service-call

Fuehrt einen kontrollierten HA-Service-Call aus.

```json
{
  "domain": "light",
  "service": "turn_on",
  "entity_id": "light.retrolampe",
  "service_data": {"brightness_pct": 45},
  "readback": true
}
```

Antwort enthaelt `readback_states` fuer den Rueckkanal (falls `readback=true`).

---

## 4. Brain Graph

Praefix: `/api/v1/graph`

Der Brain Graph ist ein In-Memory-Zustandsgraph mit Nodes (Entities, Zonen, Devices) und Edges (Beziehungen mit Gewicht und Decay).

### GET /api/v1/graph/state

Aktuellen Graph-Zustand abrufen.

**Query-Parameter:**

| Parameter | Typ | Default | Beschreibung |
|-----------|-----|---------|--------------|
| `kind` | String (multi) | alle | Node-Typen filtern (entity, zone, service, ...) |
| `domain` | String (multi) | alle | HA-Domains filtern (light, switch, ...) |
| `center` | String | - | Zentrum fuer Ego-Graph |
| `hops` | Integer | 1 | Tiefe fuer Ego-Graph (0-2) |
| `limitNodes` | Integer | 200 | Max. Nodes (1-500) |
| `limitEdges` | Integer | 400 | Max. Edges (1-1500) |
| `nocache` | String | "0" | "1" um Cache zu umgehen |

**Response:**

```json
{
  "nodes": [
    {"id": "ha.entity:light.wohnzimmer", "kind": "entity", "label": "Wohnzimmer Licht", "score": 2.5}
  ],
  "edges": [
    {"from": "ha.entity:light.wohnzimmer", "to": "ha.entity:switch.tv", "type": "observed_with", "weight": 1.8}
  ],
  "generated_at_ms": 1700000000000,
  "limits": {"max_nodes": 500, "max_edges": 1500},
  "_cached": false
}
```

### GET /api/v1/graph/stats

Graph-Statistiken fuer Health-Checks.

```json
{
  "version": 1,
  "ok": true,
  "nodes": 45,
  "edges": 120,
  "updated_at_ms": 1700000000000,
  "limits": {"max_nodes": 500, "max_edges": 1500},
  "cache": {
    "enabled": true,
    "size": 3,
    "max_size": 128,
    "hits": 42,
    "misses": 15,
    "hit_rate": 0.737
  }
}
```

### GET /api/v1/graph/patterns

Entdeckte Muster im Graph.

```json
{
  "version": 1,
  "ok": true,
  "generated_at_ms": 1700000000000,
  "patterns": [
    {"type": "co_occurrence", "entities": ["light.wohnzimmer", "switch.tv"], "weight": 3.2}
  ]
}
```

### GET /api/v1/graph/snapshot.svg

SVG-Visualisierung des Brain Graph (Kreis-Layout). Content-Type: `image/svg+xml`.

### POST /api/v1/graph/ops

Bounded Graph-Operationen mit Idempotency-Support.

**Request:**

```json
{
  "op": "touch_edge",
  "from": "ha.entity:light.wohnzimmer",
  "to": "ha.entity:switch.tv",
  "type": "observed_with",
  "delta": 1.0,
  "idempotency_key": "evt-abc123"
}
```

**Erlaubte Edge-Typen:** `observed_with`, `controls`

**Idempotency:** Unterstuetzt via `Idempotency-Key` Header oder `idempotency_key` im Body. Doppelte Requests innerhalb von 20 Minuten werden dedupliziert.

**Response:**

```json
{
  "ok": true,
  "idempotent": false,
  "key": "hdr:evt-abc123",
  "edge": {
    "from": "ha.entity:light.wohnzimmer",
    "to": "ha.entity:switch.tv",
    "type": "observed_with",
    "delta": 1.0
  }
}
```

### POST /api/v1/graph/cache/clear

Cache leeren.

```json
{"ok": true, "message": "Cache cleared", "timestamp_ms": 1700000000000}
```

---

## 5. Habitus Miner

Praefix: `/api/v1/habitus`

Association Rule Mining: Erkennt A->B Verhaltensmuster aus Event-Streams.

### GET /api/v1/habitus/status

Mining-Status und Statistiken.

```json
{
  "status": "ok",
  "version": "0.1.0",
  "statistics": {
    "total_rules": 15,
    "total_events_processed": 5000
  },
  "config": {
    "windows": [60, 300, 900],
    "min_support_A": 5,
    "min_hits": 3,
    "min_confidence": 0.6,
    "min_lift": 1.2,
    "max_rules": 200
  }
}
```

### GET /api/v1/habitus/rules

Entdeckte A->B Regeln mit optionaler Filterung.

**Query-Parameter:**

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `limit` | Integer | Max. Anzahl Regeln |
| `min_score` | Float | Mindest-Score |
| `a_filter` | String | Filter fuer Antecedent |
| `b_filter` | String | Filter fuer Consequent |
| `domain_filter` | String | Filter nach HA-Domain |

**Response:**

```json
{
  "status": "ok",
  "total_rules": 15,
  "rules": [
    {
      "A": "switch.kaffeemaschine:on",
      "B": "switch.muehle:on",
      "dt_sec": 120,
      "nA": 50,
      "nB": 45,
      "nAB": 42,
      "confidence": 0.840,
      "confidence_lb": 0.750,
      "lift": 3.20,
      "leverage": 0.125,
      "score": 0.820,
      "observation_period_days": 30,
      "created_at_ms": 1700000000000,
      "evidence": {
        "hit_examples": ["2025-01-14T08:15:00Z"],
        "miss_examples": ["2025-01-10T09:00:00Z"],
        "latency_quantiles": [5.0, 30.0, 120.0]
      }
    }
  ]
}
```

### GET /api/v1/habitus/rules/summary

Regelzusammenfassung mit Domain-Statistiken.

### GET /api/v1/habitus/rules/:rule_key/explain

Menschenlesbare Erklaerung einer Regel. Format von `rule_key`: `A_key->B_key`.

### POST /api/v1/habitus/mine

Mining aus bereitgestellten HA-Events ausloesen.

**Request:**

```json
{
  "events": [
    {"entity_id": "switch.kaffeemaschine", "state": "on", "timestamp": "2025-01-15T08:00:00Z"},
    {"entity_id": "switch.muehle", "state": "on", "timestamp": "2025-01-15T08:02:00Z"}
  ],
  "config": {
    "min_confidence": 0.5,
    "windows": [60, 300]
  }
}
```

**Response:**

```json
{
  "status": "ok",
  "mining_time_sec": 0.45,
  "total_input_events": 200,
  "discovered_rules": 8,
  "top_rules": [
    {
      "A": "switch.kaffeemaschine:on",
      "B": "switch.muehle:on",
      "confidence": 0.840,
      "lift": 3.20,
      "dt_sec": 120
    }
  ]
}
```

### GET /api/v1/habitus/config

Aktuelle Mining-Konfiguration abrufen.

### POST /api/v1/habitus/config

Mining-Konfiguration aktualisieren.

### POST /api/v1/habitus/reset

Alle gecachten Daten und entdeckten Regeln zuruecksetzen.

---

## 6. Candidates

Praefix: `/api/v1/candidates`

Governance-Workflow fuer Vorschlaege: pending -> offered -> accepted/dismissed.

### GET /api/v1/candidates

Liste aller Candidates.

**Query-Parameter:**

| Parameter | Typ | Default | Beschreibung |
|-----------|-----|---------|--------------|
| `limit` | Integer | 50 | Max. Anzahl |
| `kind` | String | - | Nach Art filtern (z.B. "seed") |

**Response:**

```json
{
  "ok": true,
  "count": 5,
  "items": [
    {
      "candidate_id": "cand_abc123",
      "kind": "seed",
      "title": "Kaffeemaschine-Muehle Automation",
      "status": "pending",
      "created_at_ms": 1700000000000
    }
  ]
}
```

### POST /api/v1/candidates

Neuen Candidate erstellen (Upsert).

**Request:**

```json
{
  "candidate_id": "cand_abc123",
  "kind": "seed",
  "title": "Neue Automation vorschlagen",
  "data": {
    "candidate_type": "automation_suggestion",
    "entities": ["switch.kaffeemaschine", "switch.muehle"]
  }
}
```

**Response:**

```json
{"ok": true, "candidate": {"candidate_id": "cand_abc123", "kind": "seed", "title": "..."}}
```

### GET /api/v1/candidates/:candidate_id

Einzelnen Candidate abrufen. 404 wenn nicht gefunden.

### DELETE /api/v1/candidates/:candidate_id

Candidate loeschen.

```json
{"ok": true}
```

### GET /api/v1/candidates/stats

Statistiken des Candidate-Stores.

```json
{"ok": true, "count": 12, "max_items": 500}
```

### GET /api/v1/candidates/graph_candidates

Governance-ready Candidates aus dem Brain Graph generieren (Preview, keine Aenderung).

**Query-Parameter:**

| Parameter | Typ | Default | Beschreibung |
|-----------|-----|---------|--------------|
| `limit` | Integer | 10 | Max. Candidates (1-25) |
| `type` | String (multi) | controls, observed_with | Edge-Typen filtern |

---

## 7. Mood Engine

Praefix: `/api/v1/mood`

3D-Stimmungsbewertung: Comfort, Joy, Frugality (je 0.0-1.0) pro Zone.

### POST /api/v1/mood/score

Mood-Score berechnen. Optional mit eigenen Events, sonst aus dem Event-Store.

**Request (optional):**

```json
{
  "events": [
    {"entity_id": "sensor.temperatur", "state": "22.5", "domain": "sensor"}
  ]
}
```

**Response:**

```json
{
  "ok": true,
  "mood": {
    "comfort": 0.78,
    "joy": 0.65,
    "frugality": 0.82,
    "dominant": "comfort",
    "timestamp": "2025-01-15T10:30:00+00:00"
  }
}
```

### GET /api/v1/mood/state

Aktueller Mood-State aus gespeicherten Events.

### GET /api/v1/mood/zones/status

Status aller Zonen.

```json
{
  "ok": true,
  "zones": {
    "living_room": {"mood": "comfort", "comfort": 0.8, "joy": 0.6, "frugality": 0.7},
    "bedroom": {"mood": "relax", "comfort": 0.9, "joy": 0.4, "frugality": 0.8}
  }
}
```

### GET /api/v1/mood/zones/:zone_name/status

Status einer einzelnen Zone. 404 wenn Zone nicht gefunden.

### POST /api/v1/mood/zones/:zone_name/orchestrate

Mood-Inferenz und Aktionen fuer eine Zone orchestrieren.

**Request:**

```json
{
  "sensor_data": {"temperature": 22.5, "humidity": 45},
  "dry_run": false,
  "force_actions": false
}
```

### POST /api/v1/mood/zones/:zone_name/force_mood

Admin-Override: Stimmung fuer eine Zone erzwingen.

**Request:**

```json
{
  "mood": "relax",
  "duration_minutes": 60
}
```

---

## 8. Events

Praefix: `/api/v1/events`

Event-Ingest-Pipeline mit Deduplizierung und Brain-Graph-Feeding.

### POST /api/v1/events

Events einspeisen (Einzel oder Batch).

**Einzelnes Event:**

```http
POST /api/v1/events
Idempotency-Key: evt-12345
Content-Type: application/json

{
  "entity_id": "light.wohnzimmer",
  "domain": "light",
  "state": "on",
  "old_state": "off",
  "event_type": "state_changed",
  "data": {"brightness": 255}
}
```

**Response (Einzel):**

```json
{
  "ok": true,
  "stored": true,
  "deduped": false,
  "event": {"entity_id": "light.wohnzimmer", "state": "on", "...": "..."},
  "graph": {
    "nodes_touched": 2,
    "edges_touched": 1,
    "observed_with_pairs": 0
  }
}
```

**Batch (bis 500 Items):**

```json
{
  "items": [
    {"entity_id": "light.wohnzimmer", "state": "on"},
    {"entity_id": "switch.tv", "state": "on"}
  ]
}
```

**Response (Batch):**

```json
{
  "ok": true,
  "ingested": 2,
  "graph": {"nodes_touched": 4, "edges_touched": 2, "observed_with_pairs": 1}
}
```

**Idempotency:** Unterstuetzt via `Idempotency-Key`, `X-Idempotency-Key` oder `X-Event-Id` Header. TTL: 20 Minuten.

### GET /api/v1/events

Gespeicherte Events abfragen.

**Query-Parameter:**

| Parameter | Typ | Default | Beschreibung |
|-----------|-----|---------|--------------|
| `limit` | Integer | 50 | Max. Anzahl |
| `since` | String | - | ISO-Timestamp fuer Zeitfilter |

---

## 9. Neurons

Praefix: `/api/v1/neurons`

14+ Bewertungs-Neuronen (Presence, Energy, Weather, Context, Camera, Media, UniFi, ...).

### GET /api/v1/neurons

Alle Neuronen auflisten.

```json
{
  "success": true,
  "data": {
    "context": {"presence": {...}, "time_of_day": {...}},
    "state": {"energy_level": {...}, "temperature": {...}},
    "mood": {"comfort": {...}, "joy": {...}},
    "total_count": 14
  }
}
```

### GET /api/v1/neurons/:neuron_id

Zustand eines spezifischen Neurons abrufen (z.B. `context.presence`, `state.energy_level`).

### POST /api/v1/neurons/evaluate

Volle Neural-Pipeline-Evaluation ausfuehren.

**Request (optional):**

```json
{
  "states": {"light.wohnzimmer": {"state": "on", "brightness": 200}},
  "context": {"time_of_day": "evening"},
  "trigger": "manual"
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "timestamp": "2025-01-15T10:30:00+00:00",
    "context_values": {"presence": 0.8, "time_of_day": 0.6},
    "state_values": {"energy_level": 0.4, "temperature": 0.7},
    "mood_values": {"comfort": 0.75, "joy": 0.60, "frugality": 0.80},
    "dominant_mood": "comfort",
    "mood_confidence": 0.85,
    "suggestions": ["Temperatur in Zone Wohnzimmer erhoehen"],
    "neuron_count": 14
  }
}
```

### POST /api/v1/neurons/update

HA-States aktualisieren ohne volle Evaluation.

**Request:**

```json
{
  "states": {
    "sensor.temperatur": {"state": "22.5"},
    "binary_sensor.motion": {"state": "on"}
  }
}
```

### POST /api/v1/neurons/configure

Neuronen aus HA konfigurieren.

### GET /api/v1/neurons/mood

Aktueller Mood-State der Neural-Pipeline.

### POST /api/v1/neurons/mood/evaluate

Mood-Evaluation erzwingen.

### GET /api/v1/neurons/mood/history

Mood-Verlauf abrufen. Query: `limit` (Default: 10).

### GET /api/v1/neurons/suggestions

Aktuelle Vorschlaege aus der letzten Evaluation.

---

## 10. Search

Praefix: `/api/v1/search`

Schnellsuche ueber HA-Entities, Automationen, Skripte, Szenen und Services.

### GET /api/v1/search

Volltextsuche ueber alle Typen.

**Query-Parameter:**

| Parameter | Typ | Pflicht | Beschreibung |
|-----------|-----|---------|--------------|
| `q` | String | Ja | Suchbegriff |
| `types` | String | Nein | Komma-getrennte Typen: entity,automation,script,scene,service |
| `limit` | Integer | Nein | Max. Ergebnisse (Default: 20, Max: 100) |

**Response:**

```json
{
  "success": true,
  "data": {
    "query": "wohnzimmer",
    "results": [
      {
        "id": "light.wohnzimmer",
        "type": "entity",
        "title": "Wohnzimmer Licht",
        "subtitle": "light . on",
        "domain": "light",
        "state": "on",
        "icon": "mdi:lightbulb",
        "score": 0.95,
        "metadata": {"entity_id": "light.wohnzimmer", "area": "wohnzimmer"}
      }
    ],
    "total_count": 3,
    "execution_time_ms": 2.5
  }
}
```

### GET /api/v1/search/entities

Entities nach Domain/State/Area filtern.

**Query-Parameter:** `domain`, `state`, `area`, `limit` (Default: 50, Max: 200).

### GET /api/v1/search/stats

Suchindex-Statistiken.

### POST /api/v1/search/index

Suchindex mit HA-Daten aktualisieren.

**Request:**

```json
{
  "entities": {"light.wohnzimmer": {"state": "on", "attributes": {"friendly_name": "Wohnzimmer"}}},
  "automations": {...},
  "scripts": {...},
  "scenes": {...},
  "services": {...}
}
```

---

## 11. Notifications

Praefix: `/api/v1/notifications`

Push-Benachrichtigungen fuer Mood-Changes, Alerts, Suggestions und System-Warnungen.

### POST /api/v1/notifications/send

Benachrichtigung senden.

**Request:**

```json
{
  "title": "Stimmungswechsel",
  "message": "Wohnzimmer von Comfort zu Relax gewechselt",
  "priority": "low",
  "type": "mood_change",
  "action_data": {"zone": "living_room"},
  "action_url": "/dashboard/mood",
  "target_devices": ["mobile_alice"],
  "tags": ["mood", "mood_change"]
}
```

**Priority-Stufen:** `low`, `normal`, `high`, `urgent`

**Typen:** `mood_change`, `alert`, `suggestion`, `system`, `info`, `warning`

### GET /api/v1/notifications

Benachrichtigungen abrufen.

**Query-Parameter:** `unread_only` (true/false), `type`, `limit` (Default: 20, Max: 100).

### POST /api/v1/notifications/:notification_id/read

Benachrichtigung als gelesen markieren.

### DELETE /api/v1/notifications/:notification_id

Benachrichtigung schliessen.

### POST /api/v1/notifications/clear

Alle Benachrichtigungen loeschen (optional nach Typ filtern).

**Request (optional):**

```json
{"type": "alert"}
```

### POST /api/v1/notifications/subscribe

Geraet fuer Push-Benachrichtigungen registrieren.

**Request:**

```json
{
  "device_id": "mobile_alice",
  "device_name": "Alice iPhone",
  "device_type": "mobile",
  "push_token": "fcm_token_...",
  "ha_entity_id": "notify.mobile_app_alice",
  "preferences": {
    "notify_mood": true,
    "notify_alerts": true,
    "notify_suggestions": true,
    "notify_system": false
  }
}
```

### POST /api/v1/notifications/unsubscribe

Geraet abmelden.

### GET /api/v1/notifications/subscriptions

Alle Geraete-Abonnements abrufen.

### PUT /api/v1/notifications/subscriptions/:device_id

Abonnement-Praeferenzen aktualisieren.

---

## 12. Knowledge Graph

Praefix: `/api/v1/kg`

Semantischer Knowledge Graph fuer Entity-Beziehungen, Zonen und Muster.

### GET /api/v1/kg/stats

Graph-Statistiken.

### GET /api/v1/kg/nodes

Nodes auflisten. Query: `type` (entity, zone, pattern, mood, ...), `limit` (Max: 500).

### GET /api/v1/kg/nodes/:node_id

Einzelnen Node abrufen.

### POST /api/v1/kg/nodes

Neuen Node erstellen.

**Request:**

```json
{
  "id": "entity:light.wohnzimmer",
  "type": "entity",
  "label": "Wohnzimmer Licht",
  "properties": {"domain": "light", "area": "wohnzimmer"}
}
```

### GET /api/v1/kg/edges

Edges auflisten. **Pflicht:** `source` oder `target` angeben. Optional: `type`, `limit`.

### POST /api/v1/kg/edges

Neue Edge erstellen.

**Request:**

```json
{
  "source": "entity:light.wohnzimmer",
  "target": "zone:wohnzimmer",
  "type": "located_in",
  "weight": 1.0,
  "confidence": 0.95
}
```

### POST /api/v1/kg/query

Graph-Abfrage ausfuehren.

**Request:**

```json
{
  "query_type": "structural",
  "entity_id": "light.wohnzimmer",
  "max_results": 10,
  "min_confidence": 0.5,
  "include_evidence": true
}
```

### GET /api/v1/kg/entity/:entity_id/related

Verwandte Entities abrufen. Query: `min_confidence`, `limit`.

### GET /api/v1/kg/zone/:zone_id/entities

Alle Entities einer Zone abrufen.

### GET /api/v1/kg/mood/:mood/patterns

Muster fuer eine Stimmung abrufen.

### GET /api/v1/kg/pattern/:pattern_id

Details zu einem Muster abrufen.

### POST /api/v1/kg/import/entities

Entities aus HA-States importieren.

### POST /api/v1/kg/import/patterns

Muster aus Habitus-Miner-Output importieren.

### POST /api/v1/kg/entities

Entity erstellen/aktualisieren (Upsert).

### POST /api/v1/kg/moods

Mood erstellen/aktualisieren.

### POST /api/v1/kg/zones

Zone erstellen/aktualisieren.

---

## 13. Vector Store

Praefix: `/api/v1/vector`

Bag-of-Words Embedding-Engine fuer semantische Aehnlichkeitssuche.

### POST /api/v1/vector/embeddings

Embedding generieren und speichern.

**Request (Entity):**

```json
{
  "type": "entity",
  "id": "light.wohnzimmer",
  "domain": "light",
  "area": "wohnzimmer",
  "capabilities": ["brightness", "color_temp"],
  "tags": ["frequently_used"],
  "state": {"state": "on", "brightness": 200}
}
```

**Request (User-Preference):**

```json
{
  "type": "user_preference",
  "id": "user_alice",
  "preferences": {"preferred_temperature": 22, "wake_time": "07:00"}
}
```

**Request (Pattern):**

```json
{
  "type": "pattern",
  "id": "pattern_morgen",
  "pattern_type": "learned",
  "entities": ["light.wohnzimmer", "switch.kaffeemaschine"],
  "conditions": {"time": "morning"},
  "confidence": 0.85
}
```

**Typen:** `entity`, `user_preference`, `pattern`

### POST /api/v1/vector/embeddings/bulk

Mehrere Embeddings auf einmal erstellen.

**Request:**

```json
{
  "entities": [{"id": "light.wohnzimmer", "domain": "light", "area": "wohnzimmer"}],
  "user_preferences": [{"id": "user_alice", "preferences": {"temp": 22}}],
  "patterns": [{"id": "pattern_1", "entities": ["light.a", "switch.b"]}]
}
```

### GET /api/v1/vector/similar/:entry_id

Aehnliche Eintraege finden.

**Query-Parameter:**

| Parameter | Typ | Default | Beschreibung |
|-----------|-----|---------|--------------|
| `type` | String | - | Filter nach Typ (entity, user_preference, pattern) |
| `limit` | Integer | 10 | Max. Ergebnisse (Max: 100) |
| `threshold` | Float | 0.7 | Mindest-Aehnlichkeit |

**Response:**

```json
{
  "ok": true,
  "query_id": "entity:light.wohnzimmer",
  "query_type": "entity",
  "results": [
    {"id": "entity:light.schlafzimmer", "similarity": 0.92, "type": "entity", "metadata": {...}}
  ],
  "count": 3
}
```

### POST /api/v1/vector/similarity

Cosinus-Aehnlichkeit zwischen zwei Eintraegen oder Vektoren berechnen.

**Request (IDs):**

```json
{"id1": "light.wohnzimmer", "id2": "light.schlafzimmer"}
```

**Request (Vektoren):**

```json
{"vector1": [0.1, 0.5, 0.3], "vector2": [0.2, 0.4, 0.35]}
```

### GET /api/v1/vector/vectors

Vektoren auflisten. Query: `type`, `limit` (Default: 50, Max: 200).

### GET /api/v1/vector/vectors/:entry_id

Einzelnen Vektor abrufen (inkl. Vektordaten).

### DELETE /api/v1/vector/vectors/:entry_id

Vektor loeschen.

### DELETE /api/v1/vector/vectors

Vektoren loeschen. Query: `type` (optional, sonst alle).

### GET /api/v1/vector/stats

Vector-Store-Statistiken.

---

## 14. Weather

Praefix: `/api/v1/weather`

Wetterdaten via Open-Meteo API (kein API-Key erforderlich) oder HA Weather-Entities.

### GET /api/v1/weather/

Aktueller Wetter-Snapshot.

```json
{
  "status": "ok",
  "data": {
    "timestamp": "2025-01-15T10:30:00+00:00",
    "condition": "partly_cloudy",
    "temperature_c": 8.5,
    "humidity_percent": 52.0,
    "cloud_cover_percent": 30,
    "uv_index": 3,
    "sunrise": "2025-01-15T07:00:00+00:00",
    "sunset": "2025-01-15T18:00:00+00:00",
    "forecast_pv_production_kwh": 18.5,
    "recommendation": "moderate_usage"
  }
}
```

### GET /api/v1/weather/forecast

Wettervorhersage. Query: `days` (Default: 3, Max: 7).

### GET /api/v1/weather/pv-recommendations

PV-basierte Energieempfehlungen.

```json
{
  "status": "ok",
  "data": {
    "recommendations": [
      {
        "id": "charge_ev",
        "recommendation_type": "charge_ev",
        "reason": "High PV surplus expected: 12.5 kWh",
        "pv_surplus_kwh": 12.5,
        "confidence": 0.9,
        "suggested_action": "Schedule EV charging between 10:00-16:00",
        "estimated_savings_eur": 3.75
      }
    ]
  }
}
```

### GET /api/v1/weather/health

Health-Check des Weather-Service.

---

## 15. Energy

Praefix: `/api/v1/energy`

Energieueberwachung mit Anomalie-Erkennung und Load-Shifting-Empfehlungen.

### GET /api/v1/energy

Kompletter Energie-Snapshot.

```json
{
  "timestamp": "2025-01-15T10:30:00+00:00",
  "total_consumption_today_kwh": 8.5,
  "total_production_today_kwh": 12.0,
  "current_power_watts": 450,
  "peak_power_today_watts": 3200,
  "anomalies_detected": 1,
  "shifting_opportunities": 2,
  "baselines": {"daily_avg_kwh": 15.0, "weekly_avg_kwh": 105.0}
}
```

### GET /api/v1/energy/anomalies

Erkannte Energie-Anomalien.

### GET /api/v1/energy/shifting

Load-Shifting-Moeglichkeiten.

```json
{
  "count": 1,
  "opportunities": [
    {
      "id": "opp_123",
      "device_type": "waschmaschine",
      "reason": "High PV production expected",
      "current_cost_eur": 0.35,
      "optimal_cost_eur": 0.08,
      "savings_estimate_eur": 0.27,
      "suggested_window_start": "10:00",
      "suggested_window_end": "14:00",
      "confidence": 0.85
    }
  ]
}
```

### GET /api/v1/energy/explain/:suggestion_id

Erklaerung fuer einen Energievorschlag.

### GET /api/v1/energy/baselines

Verbrauchsbaselines.

### GET /api/v1/energy/suppress

Pruefen ob Energievorschlaege unterdrueckt werden sollen.

### GET /api/v1/energy/health

Health-Status des Energy-Service.

---

## 16. Media Zones

Praefix: `/api/v1/media`

Media-Player-Verwaltung pro Habituszone, Playback-Steuerung und Musikwolke (Smart Audio Follow).

### Zone-Management

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET | `/zones` | Alle Zonen-Zuweisungen |
| GET | `/zones/:zone_id` | Player einer Zone |
| POST | `/zones/:zone_id/assign` | Player zuweisen |
| DELETE | `/zones/:zone_id/:entity_id` | Player entfernen |

### Playback-Steuerung

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| POST | `/zones/:zone_id/play` | Wiedergabe starten |
| POST | `/zones/:zone_id/pause` | Wiedergabe pausieren |
| POST | `/zones/:zone_id/volume` | Lautstaerke setzen (Body: `{"volume": 0.65}`) |
| POST | `/zones/:zone_id/play-media` | Bestimmte Medien abspielen |
| GET | `/zones/:zone_id/state` | Aktueller Medien-Status |

### Musikwolke (Smart Audio Follow)

Musik folgt einer Person automatisch durch die Raeume.

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| POST | `/musikwolke/start` | Session starten (Body: `person_id`, `source_zone`) |
| POST | `/musikwolke/:session_id/update` | Zone-Wechsel melden (Body: `entered_zone`) |
| POST | `/musikwolke/:session_id/stop` | Session beenden |
| GET | `/musikwolke` | Aktive Sessions auflisten |

### Proaktive Vorschlaege

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| POST | `/proactive/zone-entry` | Vorschlaege bei Zone-Eintritt |
| POST | `/proactive/deliver` | Vorschlag ausliefern |
| POST | `/proactive/dismiss` | Vorschlags-Typ ablehnen |
| POST | `/proactive/reset-dismissals` | Ablehnungen zuruecksetzen |

---

## 17. System Health

Praefix: `/api/v1/system_health`

Gesundheitschecks fuer Zigbee, Z-Wave, Recorder und Updates.

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET | `/api/v1/system_health` | Kompletter Gesundheitsstatus |
| GET | `/api/v1/system_health/zigbee` | Zigbee-Mesh-Gesundheit |
| GET | `/api/v1/system_health/zwave` | Z-Wave-Mesh-Gesundheit |
| GET | `/api/v1/system_health/recorder` | Recorder-DB-Gesundheit |
| GET | `/api/v1/system_health/updates` | Verfuegbare Updates |
| GET | `/api/v1/system_health/suppress` | Suggestion-Unterdrueckung pruefen |

Query-Parameter fuer Mesh-Endpoints: `force=true` um Cache zu umgehen.

---

## 18. Performance

Praefix: `/api/v1/performance`

Cache- und Connection-Pool-Management.

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET | `/stats` | Performance-Statistiken |
| POST | `/cache/clear` | Alle Caches leeren |
| POST | `/cache/:cache_name` | Spezifischen Cache leeren (brain_graph, ml, api) |
| POST | `/cache/invalidate` | Cache-Eintraege nach Pattern invalidieren |
| POST | `/cache/cleanup` | Abgelaufene Cache-Eintraege entfernen |
| GET | `/pool/status` | Connection-Pool-Status |
| POST | `/pool/cleanup` | Idle Connections entfernen |
| GET | `/metrics` | Performance-Metriken (Query: `name`) |
| POST | `/metrics/reset` | Metriken zuruecksetzen |

---

## 19. Habitus Dashboard Cards

Praefix: `/api/v1/habitus/dashboard_cards`

Dashboard-Empfehlungen und Lovelace-Card-Templates basierend auf Habitus-Mustern.

### GET /api/v1/habitus/dashboard_cards

Dashboard-Muster und Templates abrufen.

**Query-Parameter:**

| Parameter | Typ | Default | Beschreibung |
|-----------|-----|---------|--------------|
| `type` | String | all | overview, room, energy, sleep, zone |
| `format` | String | json | json oder yaml |
| `zone` | String | - | Zone-ID fuer zonenspezifische Muster |

### GET /api/v1/habitus/dashboard_cards/zones

Verfuegbare Zonen aus dem Brain Graph.

### GET /api/v1/habitus/dashboard_cards/zone/:zone_id

Zonenspezifische Muster und Templates.

### GET /api/v1/habitus/dashboard_cards/rules

Dashboard-Cards aus entdeckten A->B Regeln generieren.

**Query-Parameter:** `min_confidence` (Default: 0.7), `limit` (Default: 10), `zone`.

### GET /api/v1/habitus/dashboard_cards/health

Health-Check des Moduls.

---

## 20. Conversation (Legacy)

Praefix: `/chat`

Legacy-Conversation-API (Vorgaenger der OpenAI-kompatiblen `/v1/*` Endpoints).

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| POST | `/chat/completions` | Legacy Chat-Completion (gleiche Logik wie `/v1/chat/completions`) |
| GET | `/chat/tools` | Verfuegbare MCP-Tools auflisten |
| GET | `/chat/characters` | Character-Presets auflisten |
| GET | `/chat/models/recommended` | Empfohlene Ollama-Modelle |
| GET | `/chat/status` | LLM-Verfuegbarkeit und Konfiguration |
| GET | `/chat/memory` | Conversation-Memory + RAG Vector-Store Statistiken |
| GET | `/chat/memory/preferences` | Gelernte User-Praeferenzen |

### Verfuegbare Character-Presets

| ID | Name | Beschreibung |
|----|------|--------------|
| `copilot` | Styx | Standard -- hilfsbereit und smart |
| `butler` | Butler | Formal, aufmerksam, serviceorientiert |
| `energy_manager` | Energiemanager | Fokus auf Energieeffizienz |
| `security_guard` | Sicherheitswache | Sicherheitsfokussiert |
| `friendly` | Freundlicher Assistent | Laessig und gespraechig |
| `minimal` | Minimal | Kurz, direkt, effizient |

### Verfuegbare MCP-Tools

Das System bietet zahlreiche Server-Side-Tools fuer die Konversation:

- `ha.call_service` -- HA-Service aufrufen
- `ha.get_states` -- Entity-Zustaende abfragen
- `ha.get_history` -- Historie abrufen
- `ha.activate_scene` -- Szene aktivieren
- `ha.get_config` -- HA-Konfiguration lesen
- `ha.get_services` -- Verfuegbare Services auflisten
- `ha.fire_event` -- Event feuern
- `pilotsuite.create_automation` -- Automation erstellen
- `pilotsuite.list_automations` -- Erstellte Automationen auflisten
- `pilotsuite.web_search` -- Websuche (DuckDuckGo)
- `pilotsuite.get_news` -- Nachrichten abrufen (RSS)
- `pilotsuite.get_warnings` -- Regionale Warnungen (NINA/DWD)
- `pilotsuite.play_zone` -- Media-Zone steuern
- `pilotsuite.musikwolke` -- Musikwolke steuern
- `pilotsuite.save_scene` -- Szene speichern
- `pilotsuite.apply_scene` -- Szene anwenden
- `pilotsuite.calendar_events` -- Kalender-Termine abrufen
- `pilotsuite.shopping_list` -- Einkaufsliste verwalten
- `pilotsuite.reminder` -- Erinnerungen verwalten

---

## 21. Dev / Debug

### POST /api/v1/dev/logs

Entwickler-Logs einspeisen.

**Request:**

```json
{"level": "info", "message": "Test log entry", "module": "test"}
```

### GET /api/v1/dev/logs

Gespeicherte Dev-Logs abrufen. Query: `limit` (Default: 50, Max: 200).

### POST /api/v1/echo

Echo-Endpoint fuer Konnektivitaetstests.

---

## 22. Response-Format und Header

### Allgemeines JSON-Format

Die meisten Endpoints verwenden eines dieser Response-Formate:

**ok-Pattern:**

```json
{"ok": true, "data": {...}}
{"ok": false, "error": "error_code", "detail": "..."}
```

**success-Pattern (Neurons, Search, Notifications):**

```json
{"success": true, "data": {...}}
{"success": false, "error": "..."}
```

**status-Pattern (Habitus, Weather):**

```json
{"status": "ok", "data": {...}}
{"status": "error", "message": "..."}
```

### Correlation-Header

Jede Response enthaelt Correlation- und Timing-Header:

| Header | Beschreibung |
|--------|--------------|
| `X-Request-ID` | Eindeutige Request-ID (aus Request uebernommen oder generiert) |
| `X-Response-Time` | Bearbeitungszeit (z.B. `0.042s`) |
| `Content-Encoding` | `gzip` (GZIP-Kompression fuer Responses > 500 Bytes) |

### Request-ID weiterleiten

Um Requests end-to-end zu korrelieren, kann der Client einen `X-Request-ID` Header mitsenden. Der Server uebernimmt diesen oder generiert einen eigenen.

```http
GET /api/v1/graph/stats
X-Request-ID: req-abc-12345

HTTP/1.1 200 OK
X-Request-ID: req-abc-12345
X-Response-Time: 0.008s
```

### Langsame Requests

Requests die laenger als 2 Sekunden dauern werden serverseitig als SLOW REQUEST geloggt.

### Validierungsfehler (Pydantic)

Endpoints mit Schema-Validierung geben bei fehlerhaften Requests strukturierte Fehler zurueck:

```json
{
  "ok": false,
  "error": "validation_error",
  "detail": [
    {
      "field": "type",
      "message": "edge_type_not_allowed: must be one of ['controls', 'observed_with']",
      "type": "value_error"
    }
  ]
}
```

### Upload-Limit

Maximale Request-Groesse: **16 MB**.

---

## 23. Circuit Breaker

Schuetzt vor Kaskadenfehlern wenn externe Services ausfallen.

### Konfiguration

| Service | Failure Threshold | Recovery Timeout | Beschreibung |
|---------|-------------------|-----------------|--------------|
| `ha_supervisor` | 5 Fehler | 30 Sekunden | HA Supervisor REST API |
| `ollama` | 3 Fehler | 60 Sekunden | Lokaler Ollama LLM-Server |

### Zustaende

| Zustand | Beschreibung |
|---------|--------------|
| `closed` | Normal -- Anfragen werden weitergeleitet |
| `open` | Fehlerhaft -- Anfragen werden sofort abgelehnt |
| `half_open` | Test -- Naechste Anfrage wird als Probe weitergeleitet |

### Ablauf

1. **CLOSED:** Normaler Betrieb. Bei Fehlern wird der Zaehler hochgezaehlt.
2. **OPEN:** Nach Erreichen des Thresholds werden alle Calls sofort mit Fehler beantwortet (fail fast). Kein Timeout-Warten.
3. **HALF_OPEN:** Nach Ablauf des Recovery-Timeouts wird ein einzelner Probe-Call durchgelassen. Bei Erfolg -> CLOSED, bei Fehler -> OPEN.

### Status abfragen

Der Circuit-Breaker-Status ist im Deep-Health-Check enthalten:

```
GET /api/v1/health/deep
```

```json
{
  "circuit_breakers": [
    {
      "name": "ha_supervisor",
      "state": "closed",
      "failure_count": 0,
      "failure_threshold": 5,
      "recovery_timeout_s": 30.0
    },
    {
      "name": "ollama",
      "state": "open",
      "failure_count": 3,
      "failure_threshold": 3,
      "recovery_timeout_s": 60.0
    }
  ]
}
```

---

## 24. Rate Limiting

In-Memory Rate-Limiter mit konfigurierbaren Limits pro Endpoint.

### Standard-Limits

| Endpoint | Requests pro Minute |
|----------|---------------------|
| `/api/v1/events` | 200 |
| `/api/v1/habitus` | 100 |
| `/api/v1/tags` | 100 |
| `/api/v1/mood` | 50 |
| `/api/v1/graph` | 50 |
| `/api/v1/notifications` | 50 |
| `/api/v1/search` | 30 |
| `/api/v1/hints` | 20 |
| `/v1/chat/completions` | 60 pro Stunde |

### Response-Header

Rate-Limit-Informationen werden in Response-Headern zurueckgegeben:

| Header | Beschreibung |
|--------|--------------|
| `X-RateLimit-Limit` | Maximale Requests pro Periode |
| `X-RateLimit-Remaining` | Verbleibende Requests |
| `X-RateLimit-Reset` | Unix-Timestamp fuer Limit-Reset |

### Rate-Limit ueberschritten

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{
  "ok": false,
  "error": "Rate limit exceeded",
  "message": "Too many requests to /api/v1/events",
  "rate_limit": {
    "remaining": 0,
    "reset": 1700000060,
    "limit": 200,
    "period": 60
  }
}
```

### Konfiguration via Umgebungsvariablen

Limits koennen per Umgebungsvariable ueberschrieben werden:

```
COPILOT_RATE_LIMIT_EVENTS=300
COPILOT_RATE_LIMIT_MOOD=100
COPILOT_RATE_LIMIT_GRAPH=80
```

### Client-Identifikation

Der Client wird identifiziert ueber:
1. `X-Forwarded-For` Header (oder `REMOTE_ADDR`)
2. Die ersten 8 Zeichen des `X-Auth-Token` Headers

Format: `<ip>:<token_prefix>`

---

## Anhang: Schnellreferenz-Tabelle

| Bereich | Praefix | Wichtigste Endpoints |
|---------|---------|---------------------|
| OpenAI | `/v1` | POST chat/completions, GET models |
| System | `/` | GET health, GET version, GET ready |
| Brain Graph | `/api/v1/graph` | GET state, GET stats, GET patterns, POST ops |
| Habitus | `/api/v1/habitus` | GET status, GET rules, POST mine |
| Candidates | `/api/v1/candidates` | GET, POST, DELETE /:id, GET stats |
| Mood | `/api/v1/mood` | POST score, GET zones/status |
| Events | `/api/v1/events` | POST (ingest), GET (query) |
| Neurons | `/api/v1/neurons` | GET, POST evaluate, GET mood |
| Search | `/api/v1/search` | GET ?q=..., GET entities, POST index |
| Notifications | `/api/v1/notifications` | POST send, GET, DELETE /:id |
| Knowledge Graph | `/api/v1/kg` | GET nodes, POST query, GET entity/related |
| Vector Store | `/api/v1/vector` | POST embeddings, GET similar/:id |
| Weather | `/api/v1/weather` | GET /, GET forecast, GET pv-recommendations |
| Energy | `/api/v1/energy` | GET, GET anomalies, GET shifting |
| Media Zones | `/api/v1/media` | GET zones, POST play/pause/volume |
| System Health | `/api/v1/system_health` | GET, GET zigbee, GET recorder |
| Performance | `/api/v1/performance` | GET stats, POST cache/clear |
| Dashboard Cards | `/api/v1/habitus/dashboard_cards` | GET, GET zones, GET rules |
| Conversation | `/chat` | POST completions, GET tools, GET status |
| Dev/Debug | `/api/v1/dev` | POST logs, GET logs |
