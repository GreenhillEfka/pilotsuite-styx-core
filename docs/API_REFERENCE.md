# PilotSuite Styx Core API Reference

> **Status:** LEGACY / PARTIALLY OUTDATED — do not use as contract truth
> **Current published versions (2026-03-21):** HA/HACS **15.0.3** · Core/Add-on **15.0.3**
> **Canonical API truth:** current OpenAPI / live contract checks in the active repos and release gates

**Historical reference version in this file:** 13.9.0  
**Base URL:** `http://localhost:8909`  
**Docs:** `/docs` (Swagger UI)

---

> **⚡ Migration Quick Reference (v13.5.3)**
>
> | Legacy | Active | Note |
> |--------|--------|------|
> | `/api/v1/tags` | `/api/v1/tag-system/tags` | Tag-System namespace |
> | `/api/v1/tags/{id}` | `/api/v1/tag-system/tags/{tag_id}` | Tag-System namespace |
> | `/api/v1/candidates/{id}` | `/api/v1/candidates/{candidate_id}` | Parameter name unified |
> | `X-API-Key` header | `X-Auth-Token` header | Auth header preferred |
> | `mood_changed` event | `mood` event | Canonical event type |
>
> Use active v13 surface for all new integrations.

---

## Quick Start

```bash
# Health check
curl http://localhost:8909/health

# API with auth
curl -H "X-Auth-Token: your-key" http://localhost:8909/api/v1/system_health
```

---

## Authentication

All `/api/v1/*` endpoints require authentication:

**API Key (most endpoints):**
```
X-Auth-Token: your-api-key
```
> Note: `X-API-Key` is deprecated. Use `X-Auth-Token` or `Authorization: Bearer ...`.

**Bearer Token (Notifications, Telegram, Hub):**
```
Authorization: Bearer your-token
```

---

## Core Endpoints

### System & Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe |
| GET | `/version` | App version info |
| GET | `/api/v1/system_health` | Complete system health |
| GET | `/api/v1/system_health/zigbee` | Zigbee mesh health |
| GET | `/api/v1/system_health/zwave` | Z-Wave mesh health |
| GET | `/api/v1/health/deep` | Deep health check (all services) |
| GET | `/api/v1/health/metrics` | Request timing metrics |

### Brain Graph (Visualization)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/graph/state` | Get graph state as JSON |
| POST | `/api/v1/graph/render` | Render graph visualization |
| POST | `/api/v1/graph/query` | Execute graph query |
| GET | `/api/v1/graph/summary` | Graph statistics |
| POST | `/api/v1/graph/ingest` | Ingest events into graph |

### Knowledge Graph (KG)

> **New in v13.5.4:** Knowledge Graph API for entity/relationship management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/kg/nodes` | List all KG nodes |
| GET | `/api/v1/kg/nodes/{node_id}` | Get specific node |
| GET | `/api/v1/kg/edges` | List all KG edges (relationships) |
| POST | `/api/v1/kg/edges` | Create a new edge |
| POST | `/api/v1/kg/entities` | Upsert an entity |
| GET | `/api/v1/kg/entity/{entity_id}/related` | Get related entities |
| POST | `/api/v1/kg/import/entities` | Bulk import entities |
| POST | `/api/v1/kg/import/patterns` | Import patterns from Habitus |
| GET | `/api/v1/kg/moods` | List mood-related patterns |
| GET | `/api/v1/kg/mood/{mood}/patterns` | Get patterns for specific mood |
| GET | `/api/v1/kg/pattern/{pattern_id}` | Get specific pattern |
| POST | `/api/v1/kg/query` | Execute KG query |
| GET | `/api/v1/kg/stats` | KG statistics |
| GET | `/api/v1/kg/zones` | List zones in KG |
| GET | `/api/v1/kg/zone/{zone_id}/entities` | Get entities for zone |

### Habitus (Pattern Mining)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/habitus/mine` | Trigger pattern mining |
| GET | `/api/v1/habitus/patterns` | Get discovered patterns |
| POST | `/api/v1/habitus/patterns/<id>/apply` | Apply pattern as automation |
| GET | `/api/v1/habitus/stats` | Mining statistics |

### Neurons & Neural Network

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/neurons` | List all neurons |
| GET | `/api/v1/neurons/<id>` | Get neuron details |
| POST | `/api/v1/neurons` | Create new neuron |
| PUT | `/api/v1/neurons/<id>` | Update neuron |
| DELETE | `/api/v1/neurons/<id>` | Delete neuron |
| POST | `/api/v1/neurons/<id>/activate` | Activate neuron |
| GET | `/api/v1/neurons/graph` | Neural network visualization |

### Mood & Zones

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/mood/aggregated` | Aggregated mood state |
| GET | `/api/v1/mood/zones` | Zone mood states |
| POST | `/api/v1/mood/zones/<name>/orchestrate` | Orchestrate zone mood |
| POST | `/api/v1/mood/zones/<name>/force_mood` | Force zone mood |

### Notifications

#### Core Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/notifications` | List notifications |
| POST | `/api/v1/notifications` | Create notification |
| GET | `/api/v1/notifications/{notification_id}` | Get notification |
| POST | `/api/v1/notifications/{notification_id}/read` | Mark as read |
| DELETE | `/api/v1/notifications/{notification_id}` | Delete notification |
| POST | `/api/v1/notifications/clear` | Clear all notifications |
| POST | `/api/v1/notifications/send` | Send notification |

#### Home Assistant Integration

> **New in v13.5.4:** HA device registration and notification services.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/notifications/ha/register` | Register HA device |
| GET | `/api/v1/notifications/ha/devices` | List HA devices |
| POST | `/api/v1/notifications/ha/devices/{device_id}/enable` | Enable HA device |
| POST | `/api/v1/notifications/ha/devices/{device_id}/disable` | Disable HA device |
| DELETE | `/api/v1/notifications/ha/devices/{device_id}` | Unregister HA device |
| GET | `/api/v1/notifications/ha/services` | List HA notify services |
| GET | `/api/v1/notifications/ha/test` | Test HA connection |
| POST | `/api/v1/notifications/send/ha` | Send via HA notification |

#### Subscriptions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/notifications/subscribe` | Subscribe device |
| POST | `/api/v1/notifications/unsubscribe` | Unsubscribe device |
| GET | `/api/v1/notifications/subscriptions` | List subscriptions |
| PUT | `/api/v1/notifications/subscriptions/{device_id}` | Update subscription |

### Multi-Home & Sharing

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/homes` | List all homes |
| POST | `/api/v1/homes` | Add new home |
| GET | `/api/v1/homes/<id>` | Get home details |
| GET | `/api/v1/config/diff/<source>/<target>` | Config diff |
| POST | `/api/v1/config/sync` | Sync configs |
| GET | `/api/v1/conflicts` | List conflicts |
| POST | `/api/v1/conflicts/<id>/resolve` | Resolve conflict |

### Collective Intelligence (Federated Learning)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/federated/models` | List federated models |
| POST | `/api/v1/federated/contribute` | Contribute to federated learning |
| GET | `/api/v1/federated/status` | Federated learning status |

### RAG & Vector Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/vectors` | List vector entries |
| POST | `/api/v1/vectors` | Create vector entry |
| GET | `/api/v1/vectors/<id>` | Get vector entry |
| DELETE | `/api/v1/vectors/<id>` | Delete vector entry |
| POST | `/api/v1/vectors/similarity` | Similarity search |
| POST | `/api/v1/embeddings` | Generate embeddings |
| POST | `/api/v1/embeddings/bulk` | Bulk embeddings |

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/search` | Hybrid search |
| POST | `/api/v1/search` | Advanced search |
| GET | `/api/v1/search/suggestions` | Search suggestions |

### User Preferences

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/<id>/preferences` | Get user preferences |
| POST | `/api/v1/users/<id>/preference` | Set preference |
| GET | `/api/v1/users/<id>/role` | Get user role |
| POST | `/api/v1/users/<id>/delegate` | Delegate permissions |

### Energy

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/energy/status` | Energy system status |
| GET | `/api/v1/energy/forecast` | Energy forecast |
| GET | `/api/v1/energy/pv-recommendations` | PV recommendations |
| POST | `/api/v1/energy/climate/preheat` | Preheat climate |

### UniFi Network

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/unifi/status` | UniFi controller status |
| GET | `/api/v1/unifi/devices` | List network devices |
| GET | `/api/v1/unifi/events` | Network events |

### Tags

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tag-system/tags` | List all tags |
| POST | `/api/v1/tag-system/tags` | Create tag |
| DELETE | `/api/v1/tag-system/tags/{tag_id}` | Delete tag |
| GET | `/api/v1/tag-system/tags` | Tag registry |
| GET | `/api/v1/tag-system/assignments` | List tag assignments |
| POST | `/api/v1/tag-system/assignments` | Create tag assignment |

### Calendar

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/calendar/events` | List calendar events |
| POST | `/api/v1/calendar/events` | Create event |
| DELETE | `/api/v1/calendar/events/<id>` | Delete event |

### Voice

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/voice/status` | Voice service status |
| POST | `/api/v1/voice/synthesize` | Text-to-speech |
| GET | `/api/v1/voice/voices` | Available voices |

### Weather

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/weather/current` | Current weather |
| GET | `/api/v1/weather/forecast` | Weather forecast |

### Media Zones

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/media/zones` | List media zones |
| GET | `/api/v1/media/zones/<id>/status` | Zone status |
| POST | `/api/v1/media/zones/<id>/play` | Play media |
| POST | `/api/v1/media/zones/<id>/pause` | Pause media |

### Shopping & Reminders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/shopping/list` | Get shopping list |
| POST | `/api/v1/shopping/items` | Add item |
| DELETE | `/api/v1/shopping/items/<id>` | Remove item |

### Dev & Debugging

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/dev/logs` | Get dev logs |
| POST | `/api/v1/dev/logs` | Ingest dev logs |
| GET | `/api/v1/dev/status` | Dev status |
| GET | `/api/v1/dev/support_bundle` | Download support bundle |

### Documentation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/docs` | Swagger UI |
| GET | `/api/v1/docs/openapi.json` | OpenAPI spec (JSON) |
| GET | `/api/v1/docs/openapi.yaml` | OpenAPI spec (YAML) |

---

## Response Format

**Success:**
```json
{
  "status": "success",
  "data": { ... },
  "metadata": {
    "timestamp": "2026-03-01T10:00:00Z",
    "version": "v1"
  }
}
```

**Error:**
```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message"
  }
}
```

---

## Rate Limiting

- **Default:** 100 requests/minute per API key
- **Burst:** 20 requests/second
- **Headers:** `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## API Versioning

Use `Accept-Version` header:
```bash
curl -H "Accept-Version: v1" http://localhost:8909/api/v1/graph/state
```

Deprecated endpoints return:
- `Deprecation: true`
- `Sunset: <date>`
- `Link: <successor>; rel="successor-version"`

---

**Full OpenAPI Spec:** `/api/v1/docs/openapi.json`  
**Interactive Docs:** `/docs`
