# HA → Core ingest contract (contract lane)

Status: draftable/implementable in Core without waiting for HA packaging.

## Endpoint

HA should send event batches to:

- `POST /api/v1/events`

### Current wiring status

The route-prefix duplication in Core wiring is fixed:

- `copilot_core.api.v1.events_ingest` is now registered without an extra `url_prefix`
- canonical runtime paths stay at `POST /api/v1/events`, `GET /api/v1/events`, `GET /api/v1/events/stats`
- verifier should still confirm the runtime route map, but the former `/api/v1/api/v1/events` duplication is no longer the intended wiring

Core now accepts both:

1. **canonical shape** (`kind` / `src` / structured `old`/`new`/`service`)
2. **legacy forwarder shape** (`type` / `source` / `attributes`)

Core normalizes both into one internal truth shape.

## Canonical event envelope

```json
{
  "v": 1,
  "id": "optional-upstream-event-id",
  "kind": "state_changed | call_service | heartbeat",
  "src": "ha",
  "ts": "2026-03-22T20:17:00Z",
  "entity_id": "light.kitchen",
  "domain": "light",
  "zone_ids": ["kitchen"],
  "zone_id": "kitchen",
  "context_id": "abcdef123456",
  "context_parent_id": "fedcba654321",
  "context_user_id": "112233445566",
  "trigger": "user",
  "old": {"state": "off", "attrs": {}},
  "new": {"state": "on", "attrs": {"brightness": 180}},
  "service": {
    "domain": "light",
    "service": "turn_on",
    "entity_ids": ["light.kitchen"]
  },
  "entity_count": 245
}
```

## Relevant event kinds

### `state_changed`
Required from HA:

- `ts`
- `entity_id`
- `domain` (or `attributes.domain` in legacy mode)
- before/after state:
  - canonical: `old`, `new`
  - legacy: `attributes.old_state`, `attributes.new_state`

Recommended:

- `zone_ids` (or legacy `attributes.zone_ids`)
- `context.id`
- `context.parent_id`
- `context.user_id`
- `trigger`
- sanitized `new.attrs` / legacy `attributes.state_attributes`

### `call_service`
Required from HA:

- `ts`
- target identity:
  - canonical: `service.domain`, `service.service`
  - legacy: `attributes.domain`, `attributes.service`

Recommended:

- `entity_id` and/or `service.entity_ids`
- `zone_ids`
- `context.id`
- `context.parent_id`
- `trigger`

### `heartbeat`
Required from HA:

- `ts`

Recommended:

- `entity_count`

## What Core now guarantees

Core normalizes to:

- `kind=call_service` even if HA sends alias `service_call`
- `src=ha` even if HA sends `home_assistant`
- `zone_ids[]` plus convenience `zone_id`
- structured `service = {domain, service, entity_ids}`
- structured context fields:
  - `context_id`
  - `context_parent_id`
  - `context_user_id`
  - `context { id, parent_id, user_id }`

## Exact inputs requested from HA lane

For the HA lane to fully unlock the contract, send these for every forwarded event when available:

1. `ts`
2. `entity_id` for `state_changed` (optional for `call_service` if `service.entity_ids[]` or a domain-wide action is supplied)
3. `domain`
4. `zone_ids[]`
5. `context.id`
6. `context.parent_id`
7. `context.user_id`
8. `trigger`
9. for state changes: `old.state`, `new.state`, sanitized attrs
10. for service calls: `service.domain`, `service.service`, `service.entity_ids[]`

## Notes

- Core truncates context identifiers to 12 chars for privacy/stability.
- Core does **not** require HA packaging/release work for these contract-side changes.
- Preferred long-term HA output is the canonical shape above; legacy shape remains accepted for compatibility.
