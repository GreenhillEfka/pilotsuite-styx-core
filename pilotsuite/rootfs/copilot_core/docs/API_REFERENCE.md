# PilotSuite Styx Core API Reference

**Version:** 12.5.0  
**Generated:** 2026-03-01 22:12:23  
**Base URL:** `http://localhost:8909`

---

## Table of Contents

- [System Health](#system-health)
- [Brain Graph](#brain-graph)
- [Habitus](#habitus)
- [Candidates](#candidates)
- [Mood](#mood)
- [Notifications](#notifications)
- [Sharing](#sharing)
- [Collective Intelligence](#collective-intelligence)
- [Energy](#energy)
- [UniFi](#unifi)
- [Tags](#tags)
- [Dev Surface](#dev-surface)
- [Telegram](#telegram)
- [Hub](#hub)

---

## Overview

The PilotSuite Styx Core API provides comprehensive REST endpoints for home automation, AI-powered pattern mining, multi-home synchronization, and federated learning.

### Authentication

All API endpoints require authentication. Two authentication methods are supported:

#### API Key Authentication

Most endpoints use API Key authentication via the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8909/api/v1/system_health
```

#### Bearer Token Authentication

Some endpoints (Notifications, Telegram, Hub) use Bearer token authentication:

```bash
curl -H "Authorization: Bearer your-token" http://localhost:8909/api/v1/notifications
```

### Versioning

API versioning is supported via the `Accept-Version` header:

```bash
curl -H "Accept-Version: v1" http://localhost:8909/api/v1/graph/state
```

Deprecated endpoints include the following headers in responses:
- `Deprecation: true`
- `Sunset: <date>`
- `Link: <successor-url>; rel="successor-version"`

### Response Format

All responses follow a consistent JSON structure:

**Success Response:**
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

**Error Response:**
```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": { ... }
  }
}
```

### Rate Limiting

API requests are rate-limited to prevent abuse:
- **Default:** 100 requests per minute per API key
- **Burst:** 20 requests per second
- **Exceeded:** HTTP 429 Too Many Requests

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## API Modules


## System Health API

Monitor system resources, diagnostics, and service health.

### Endpoints

#### GET /api/v1/system_health

Get complete system health status.

**Authentication:** API Key  
**Response:** System health including CPU, memory, disk, and service status.

**Example Request:**
```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8909/api/v1/system_health
```

**Example Response:**
```json
{{
  "status": "healthy",
  "cpu": {{
    "usage_percent": 23.5,
    "cores": 4,
    "temperature": 45.2
  }},
  "memory": {{
    "total_mb": 8192,
    "used_mb": 4096,
    "percent": 50.0
  }},
  "disk": {{
    "total_gb": 128,
    "used_gb": 64,
    "percent": 50.0
  }},
  "services": [
    {{"name": "brain_graph", "status": "running"}},
    {{"name": "habitus", "status": "running"}},
    {{"name": "mood", "status": "running"}}
  ]
}}
```

---

#### GET /api/v1/system_health/zigbee

Get Zigbee mesh health.

**Authentication:** API Key  
**Parameters:**
- `force` (boolean, optional): Force refresh from coordinator

**Response:** Zigbee network health including signal quality and device status.

---

#### GET /api/v1/system_health/zwave

Get Z-Wave mesh health.

**Authentication:** API Key  
**Response:** Z-Wave network health including node status and routing.


---


## Brain Graph API

Knowledge graph for event storage, pattern mining, and neural visualization.

### Endpoints

#### GET /api/v1/graph/state

Get current graph state as JSON.

**Authentication:** API Key  
**Parameters:**
- `kind` (string, repeatable): Filter by node kind
- `domain` (string, repeatable): Filter by domain
- `center` (string): Center node for neighborhood query
- `hops` (integer, default: 1): Number of hops
- `limitNodes` (integer, default: 100): Maximum nodes to return
- `nocache` (boolean): Bypass cache

**Example Request:**
```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8909/api/v1/graph/state?kind=event&limitNodes=50"
```

**Example Response:**
```json
{{
  "nodes": [
    {{
      "id": "event_123",
      "kind": "event",
      "domain": "media_player",
      "score": 0.95,
      "data": {{...}}
    }}
  ],
  "edges": [
    {{
      "source": "event_123",
      "target": "zone_living_room",
      "weight": 0.8,
      "type": "occurred_in"
    }}
  ],
  "metadata": {{
    "total_nodes": 150,
    "total_edges": 420,
    "last_updated": "2026-03-01T10:00:00Z"
  }}
}}
```

---

#### POST /api/v1/graph/render

Render graph visualization.

**Authentication:** API Key  
**Request Body:**
```json
{{
  "format": "svg",
  "layout": "force",
  "filters": {{"kind": "event"}}
}}
```

**Response:** SVG or PNG visualization.

---

#### POST /api/v1/graph/query

Execute graph query.

**Authentication:** API Key  
**Request Body:**
```json
{{
  "query": "MATCH (e:event)-[:OCCURRED_IN]->(z:zone) WHERE z.id = 'living_room' RETURN e",
  "parameters": {{}}
}}
```


---


## Habitus API

Pattern mining and habitus learning for automation discovery.

### Endpoints

#### POST /api/v1/habitus/mine

Trigger habitus pattern mining.

**Authentication:** API Key  
**Request Body (optional):**
```json
{{
  "lookback_hours": 72,
  "force": false,
  "zone": "kitchen"
}}
```

**Response:**
```json
{{
  "status": "started",
  "job_id": "mine_20260301_100000",
  "estimated_duration": "5 minutes"
}}
```

---

#### GET /api/v1/habitus/stats

Get mining statistics.

**Authentication:** API Key  
**Response:**
```json
{{
  "total_patterns": 150,
  "patterns_mined_today": 12,
  "avg_confidence": 0.87,
  "last_mining_run": "2026-03-01T09:00:00Z"
}}
```

---

#### GET /api/v1/habitus/patterns

Get recent patterns.

**Authentication:** API Key  
**Parameters:**
- `limit` (integer, default: 50): Maximum patterns to return


---


## Candidates API

Automation candidate management lifecycle.

### Endpoints

#### GET /api/v1/candidates

List automation candidates.

**Authentication:** API Key  
**Parameters:**
- `state` (string): Filter by state (pending, offered, accepted, dismissed, deferred)
- `include_ready_deferred` (boolean): Include deferred candidates ready for retry
- `limit` (integer, default: 50, max: 200): Maximum results

**Example Request:**
```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8909/api/v1/candidates?state=pending&limit=20"
```

**Example Response:**
```json
{{
  "candidates": [
    {{
      "id": "cand_123",
      "pattern_id": "pat_456",
      "state": "pending",
      "title": "Evening Lighting Automation",
      "description": "Automatically turn on living room lights at sunset",
      "automation_yaml": "automation:\n  - alias: ...",
      "confidence": 0.92,
      "created_at": "2026-03-01T09:00:00Z"
    }}
  ],
  "count": 1
}}
```

---

#### POST /api/v1/candidates

Create candidate.

**Authentication:** API Key  
**Request Body:**
```json
{{
  "pattern_id": "pat_456",
  "title": "Evening Lighting Automation",
  "description": "Automatically turn on living room lights at sunset",
  "automation_yaml": "automation:\n  - alias: ...",
  "confidence": 0.92
}}
```

---

#### GET /api/v1/candidates/{{id}}

Get candidate details.

**Authentication:** API Key  
**Path Parameters:**
- `id` (string): Candidate ID

---

#### PUT /api/v1/candidates/{{id}}

Update candidate state.

**Authentication:** API Key  
**Path Parameters:**
- `id` (string): Candidate ID

**Request Body:**
```json
{{
  "state": "accepted",
  "reason": "Looks good, deploy it"
}}
```

---

#### GET /api/v1/candidates/stats

Get storage statistics.

**Authentication:** API Key  
**Response:**
```json
{{
  "total_candidates": 250,
  "by_state": {{
    "pending": 5,
    "offered": 10,
    "accepted": 200,
    "dismissed": 30,
    "deferred": 5
  }},
  "storage_used_mb": 12.5
}}
```


---


## Mood API

Zone mood scoring and ambient context.

### Endpoints

#### GET /api/v1/mood

Get all zone moods.

**Authentication:** API Key  
**Response:**
```json
{{
  "zones": [
    {{
      "zone_id": "living_room",
      "mood_score": 0.85,
      "grade": "A",
      "factors": {{...}}
    }}
  ]
}}
```

---

#### GET /api/v1/mood/{{zone_id}}

Get specific zone mood.

**Authentication:** API Key  
**Path Parameters:**
- `zone_id` (string): Zone identifier

---

#### GET /api/v1/mood/summary

Get aggregated mood stats.

**Authentication:** API Key  
**Response:**
```json
{{
  "average_mood": 0.78,
  "zones_above_threshold": 5,
  "zones_below_threshold": 2,
  "trend": "improving"
}}
```

---

#### POST /api/v1/mood/update-media

Update moods from media context.

**Authentication:** API Key  
**Request Body:**
```json
{{
  "music_active": true,
  "tv_active": false,
  "primary_player": {{
    "entity_id": "media_player.living_room",
    "state": "playing",
    "media_title": "Jazz Playlist",
    "area": "living_room"
  }}
}}
```

---

#### POST /api/v1/mood/update-habitus

Update moods from habitus.

**Authentication:** API Key  

---

#### GET /api/v1/mood/{{zone_id}}/suppress-energy-saving

Check energy-saving suppression.

**Authentication:** API Key  
**Response:**
```json
{{
  "suppress": true,
  "reason": "High mood score, comfort priority"
}}
```


---


## Notifications API

Notification engine with multi-channel delivery.

### Endpoints

#### GET /api/v1/notifications

Get notification history.

**Authentication:** Bearer Token  
**Parameters:**
- `limit` (integer, default: 50): Maximum notifications
- `source` (string): Filter by source module
- `unread_only` (boolean): Only unread notifications
- `type` (string): Filter by type (mood_change, alert, suggestion, system, info, warning)

**Example Request:**
```bash
curl -H "Authorization: Bearer your-token" \
  "http://localhost:8909/api/v1/notifications?unread_only=true&limit=20"
```

---

#### POST /api/v1/notifications

Create notification.

**Authentication:** Bearer Token  
**Request Body:**
```json
{{
  "title": "Energy Saving Opportunity",
  "message": "High energy consumption detected in kitchen",
  "type": "suggestion",
  "priority": "normal",
  "channel": "push",
  "data": {{
    "zone_id": "kitchen",
    "action_url": "/energy/kitchen"
  }}
}}
```

---

#### GET /api/v1/notifications/digest

Get notification digest.

**Authentication:** Bearer Token  
**Response:**
```json
{{
  "period": "last_24h",
  "total": 15,
  "by_type": {{
    "alert": 2,
    "suggestion": 5,
    "info": 8
  }},
  "unread": 3
}}
```

---

#### GET /api/v1/notifications/pending

Get pending notifications.

**Authentication:** Bearer Token  

---

#### GET /api/v1/notifications/stats

Get notification statistics.

**Authentication:** Bearer Token  
**Response:**
```json
{{
  "total_sent": 1250,
  "by_channel": {{
    "push": 800,
    "telegram": 300,
    "email": 150
  }},
  "delivery_rate": 0.98
}}
```


---


## Sharing API

Cross-home entity sharing and synchronization.

### Endpoints

#### GET /api/v1/sharing

Get sharing system status.

**Authentication:** API Key  
**Response:**
```json
{{
  "enabled": true,
  "peers_discovered": 2,
  "entities_shared": 45,
  "sync_status": "active"
}}
```

---

#### GET /api/v1/sharing/entities

List shared entities.

**Authentication:** API Key  

---

#### POST /api/v1/sharing/entities

Register shared entity.

**Authentication:** API Key  
**Request Body:**
```json
{{
  "entity_id": "light.living_room_main",
  "name": "Living Room Main Light",
  "type": "light",
  "home_id": "home_001",
  "capabilities": ["brightness", "color_temp"],
  "metadata": {{...}}
}}
```

---

#### GET /api/v1/sharing/sync/status

Get sync status.

**Authentication:** API Key  

---

#### GET /api/v1/sharing/discovery/peers

List discovered peers.

**Authentication:** API Key  
**Response:**
```json
{{
  "peers": [
    {{
      "home_id": "home_002",
      "name": "Vacation Home",
      "last_seen": "2026-03-01T09:30:00Z",
      "status": "online"
    }}
  ]
}}
```


---


## Collective Intelligence API

Federated learning across multiple homes.

### Endpoints

#### GET /api/v1/federated

Get federated learning status.

**Authentication:** API Key  
**Response:**
```json
{{
  "enabled": true,
  "nodes_registered": 5,
  "current_round": 12,
  "model_version": "v2.3.1"
}}
```

---

#### POST /api/v1/federated/start

Start federated learning.

**Authentication:** API Key  

---

#### POST /api/v1/federated/stop

Stop federated learning.

**Authentication:** API Key  

---

#### POST /api/v1/federated/register

Register home node.

**Authentication:** API Key  
**Request Body:**
```json
{{
  "home_id": "home_003",
  "name": "Office",
  "capabilities": ["pattern_mining", "mood_scoring"]
}}
```

---

#### POST /api/v1/federated/update

Submit model update.

**Authentication:** API Key  

---

#### POST /api/v1/federated/round

Start federated round.

**Authentication:** API Key  

---

#### POST /api/v1/federated/aggregate

Execute aggregation.

**Authentication:** API Key  

---

#### GET /api/v1/federated/rounds

Get round history.

**Authentication:** API Key  
**Response:**
```json
{{
  "rounds": [
    {{
      "round_id": 12,
      "started_at": "2026-03-01T00:00:00Z",
      "completed_at": "2026-03-01T01:00:00Z",
      "participating_nodes": 5,
      "model_improvement": 0.03
    }}
  ]
}}
```

---

#### GET /api/v1/federated/statistics

Get comprehensive statistics.

**Authentication:** API Key  
**Response:**
```json
{{
  "total_rounds": 12,
  "total_updates": 60,
  "avg_improvement": 0.025,
  "best_model_version": "v2.3.1"
}}
```


---


## Energy API

Energy monitoring and optimization.

### Endpoints

#### GET /api/v1/energy

Get energy snapshot.

**Authentication:** API Key  
**Response:**
```json
{{
  "timestamp": "2026-03-01T10:00:00Z",
  "total_consumption_today_kwh": 12.5,
  "total_production_today_kwh": 8.2,
  "current_power_watts": 450,
  "peak_power_today_watts": 2500,
  "anomalies_detected": false,
  "shifting_opportunities": [
    {{
      "device": "washer",
      "optimal_start": "2026-03-01T14:00:00Z",
      "savings_eur": 0.45
    }}
  ]
}}
```

---

#### GET /api/v1/energy/anomalies

Get energy anomalies.

**Authentication:** API Key  

---

#### GET /api/v1/energy/sankey

Get energy Sankey diagram.

**Authentication:** API Key  
**Response:** Sankey diagram data for visualization.


---


## UniFi API

UniFi network monitoring.

### Endpoints

#### GET /api/v1/unifi

Get UniFi network snapshot.

**Authentication:** Bearer Token  
**Response:**
```json
{{
  "wan": {{
    "online": true,
    "ip": "1.2.3.4",
    "download_mbps": 100,
    "upload_mbps": 40
  }},
  "clients": {{
    "total": 25,
    "active": 18
  }},
  "roaming_events": [],
  "baselines": {{...}}
}}
```


---


## Tags API

Tag system for entity organization.

### Endpoints

#### GET /api/v1/tags

List all tags.

**Authentication:** Bearer Token  

---

#### POST /api/v1/tags

Create tag.

**Authentication:** Bearer Token  

---

#### DELETE /api/v1/tags/{{id}}

Delete tag.

**Authentication:** Bearer Token  


---


## Dev Surface API

Development observability and diagnostics.

### Endpoints

#### GET /api/v1/dev/logs

Get recent logs.

**Authentication:** API Key  
**Parameters:**
- `limit` (integer, default: 100): Maximum log entries
- `level` (string): Filter by level (DEBUG, INFO, WARNING, ERROR)

---

#### GET /api/v1/dev/errors

Get error summary.

**Authentication:** API Key  
**Response:**
```json
{{
  "total_errors": 5,
  "by_type": {{
    "ValueError": 2,
    "TimeoutError": 3
  }},
  "recent_errors": [...]
}}
```


---


## Telegram API

Telegram bot integration.

### Endpoints

#### GET /telegram/status

Get Telegram bot status.

**Authentication:** Bearer Token  
**Response:**
```json
{{
  "enabled": true,
  "running": true
}}
```

---

#### POST /telegram/send

Send Telegram message.

**Authentication:** Bearer Token  
**Request Body:**
```json
{{
  "chat_id": "123456789",
  "text": "Hello from PilotSuite!"
}}
```


---


## Hub API

PilotSuite Hub - Central management interface with 120+ endpoints.

### Endpoints

#### GET /api/v1/hub/status

Get Hub status.

**Authentication:** Bearer Token  
**Response:**
```json
{{
  "version": "12.5.0",
  "engines": {{
    "zones": "running",
    "modes": "running",
    "lighting": "running",
    "media": "running",
    "energy": "running"
  }},
  "uptime_seconds": 86400
}}
```

---

#### GET /api/v1/hub/zones

List zones.

**Authentication:** Bearer Token  
**Response:**
```json
{{
  "zones": [
    {{
      "id": "living_room",
      "name": "Living Room",
      "entities": 15,
      "mode": "relax"
    }}
  ]
}}
```

---

#### GET /api/v1/hub/modes

List modes.

**Authentication:** Bearer Token  
**Response:**
```json
{{
  "modes": [
    {{
      "id": "relax",
      "name": "Relax",
      "description": "Evening relaxation mode",
      "active_zones": ["living_room"]
    }}
  ]
}}
```


---

## Schemas

Schema documentation pending...

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `BAD_REQUEST` | 400 | Invalid request parameters |
| `CONFLICT` | 409 | Resource conflict |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

---

## Changelog

### v12.5.0 (2026-03-01)
- Added comprehensive OpenAPI 3.0 specification
- Documented all Hub API endpoints (120+)
- Added federated learning API documentation
- Enhanced error response documentation

### v12.0.0 (2026-02-01)
- Phase 5: Cross-Home Sharing API
- Phase 5: Notifications API (21 endpoints)
- Phase 5: Collective Intelligence API (15 endpoints)
- Phase 6: Complete type hints

### v11.0.0 (2026-01-01)
- Initial stable API release
- Brain Graph API
- Habitus pattern mining
- Mood scoring system

---

*Generated automatically by `api_reference.py`*
