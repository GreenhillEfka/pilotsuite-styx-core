# Ingest Contract — Slice 1 (2026-03-25)

## Status: AUTHORITATIVE

## Canonical Ingest Path

```
Home Assistant (Events Forwarder)
  → POST /api/v1/events (BatchEventPayload, X-Auth-Token)
  → EventStore.ingest_batch()  [copilot_core/ingest/event_store.py]
  → Post-Ingest Callback Chain:
      1. EventProcessor (copilot_core/ingest/event_processor.py)
      2. Brain Graph feeding (copilot_core/brain_graph/feeding.py)
  → ModuleRouter.ingest_event() (network modules)
```

## Authoritative Components

| Component | File | Role |
|---|---|---|
| **Ingest Endpoint** | `api/v1/events_ingest.py` | Canonical POST /api/v1/events |
| **Event Store** | `ingest/event_store.py` | Authoritative storage |
| **Event Processor** | `ingest/event_processor.py` | Post-processing callback |
| **Blueprint Registration** | `core_setup.py` → `register_blueprints(app, services)` → `api_v1` | Production wiring |

## Legacy (RETIRED as of this contract)

| File | Endpoint | Status |
|---|---|---|
| `api/v1/events.py` | POST /events, GET /events | **DEPRECATED** — retired as of this contract |
| `storage/events.py` | EventStore (legacy) | **DEPRECATED** — unused in production |

The old `events.py` blueprint was registered directly in `app.py` with its own
EventStore singleton (`_STORE`). This is superseded by the centralized
`events_ingest.py` path.

## Key Design Decisions

### 1. EventStore Singleton Pattern
- `events_ingest.py` uses lazy singleton: `get_store()` creates `EventStore()` on first call
- `set_store(store)` allows injection for tests
- Post-ingest callback registered via `set_post_ingest_callback()`

### 2. Batch Ingest
- `POST /api/v1/events` accepts `BatchEventPayload { items: [...] }`
- Deduplication via idempotency keys
- Returns `{ accepted, rejected, deduped, accepted_events }`

### 3. Post-Ingest Chain
```
accepted_events → _post_ingest_callback(accepted_events)
                 → EventProcessor.process_events()
                 → Brain Graph feeding
                 → ModuleRouter.ingest_event() (accumulation)
```

### 4. HA Event Forwarder Contract
- HA sends: `{ "items": [ { "type": "state_changed", "entity_id": "...", "new": {...}, ... } ] }`
- HA includes: `X-Auth-Token` header
- Batch size: configurable, default no limit

## Data Flow

```
[HA Event Forwarder]
        │
        ▼ POST /api/v1/events (BatchEventPayload)
[Flask @require_token + @validate_json(BatchEventPayload)]
        │
        ▼ store.ingest_batch(items)
[EventStore — canonical store]
        │
        ├─► _post_ingest_callback(accepted_events)
        │         │
        │         ▼ EventProcessor.process_events()
        │         │
        │         ▼ feed_events_to_graph(graph_svc, events)
        │         │
        │         ▼ module_router.ingest_event(event)
        │
        ▼ { accepted, rejected, deduped }
```

## Test Contract

Route-level tests must use the **registered app** (blueprint via `core_setup`),
not a naked blueprint instance. See test conventions in `tests/`.

## Contract Owner

- **PilotClaw** — Core API, Ingest, Event Store
- **Stxy** — RAG Styx consumer of Event Store
