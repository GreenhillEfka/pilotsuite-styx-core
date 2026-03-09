# PilotSuite Styx Core API - Vollständige Referenz

> ⚠️ **Legacy Documentation**
>
> This document describes historical API surfaces and is kept for reference only.
> For the current v13.5.3 API contract, see:
> - **OpenAPI Spec:** `/api/v1/docs/openapi.yaml`
> - **Swagger UI:** `/docs`
> - **Quick Reference:** `API_REFERENCE.md` (active endpoints only)
>
> Endpoints documented here may be deprecated, moved, or removed.
> Use the Migration Quick Reference below to find active paths.

**Version:** 12.6.0 (historical reference)  
**Stand:** 2026-03-07  
**Basis-URL:** `http://localhost:8909`

---

## Inhaltsverzeichnis

1. [Übersicht](#übersicht)
2. [Authentifizierung](#authentifizierung)
3. [API-Endpoints nach Kategorie](#api-endpoints-nach-kategorie)
   - [System Health](#system-health)
   - [Brain Graph](#brain-graph)
   - [Habitus & Pattern Mining](#habitus--pattern-mining)
   - [Automation Candidates](#automation-candidates)
   - [Mood & Zone Context](#mood--zone-context)
   - [Notifications](#notifications)
   - [Sharing & Multi-Home](#sharing--multi-home)
   - [Federated Learning](#federated-learning)
   - [Energy Monitoring](#energy-monitoring)
   - [UniFi Network](#unifi-network)
   - [Tag System](#tag-system)
   - [Dev Surface](#dev-surface)
   - [Telegram Integration](#telegram-integration)
   - [PilotSuite Hub](#pilotsuite-hub)
   - [Vector Search & RAG](#vector-search--rag)
   - [Voice & Conversation](#voice--conversation)
   - [Calendar](#calendar)
   - [Anomaly Detection](#anomaly-detection)
   - [User Management](#user-management)
   - [Presence Detection](#presence-detection)
   - [Media Zones](#media-zones)
   - [Module Control](#module-control)
   - [Blueprint System](#blueprint-system)
   - [HomeKit Integration](#homekit-integration)
   - [Metrics & Monitoring](#metrics--monitoring)
   - [Reminders](#reminders)
   - [Search](#search)
   - [User Hints](#user-hints)
   - [Websocket Neuron](#websocket-neuron)
   - [Voice Context](#voice-context)
   - [Styx Chat](#styx-chat)
   - [Dashboard Cards](#dashboard-cards)
   - [Service Control](#service-control)
4. [Fehlerbehandlung](#fehlerbehandlung)
5. [Rate Limiting](#rate-limiting)
6. [Versionierung](#versionierung)

---

## Übersicht

Die PilotSuite Styx Core API ist eine RESTful API, die auf Flask basiert und umfassende Funktionen für Smart-Home-Automation, KI-gesteuerte Mustererkennung und Multi-Home-Synchronisation bereitstellt.

> **📖 Quick Reference — historische Migration von v13.5.2 → v13.5.3**
>
> | Legacy | Aktiv | Hinweis |
> |--------|-------|---------|
> | `/api/v1/tags` | `/api/v1/tag-system/tags` | Tag-System Namespace |
> | `/api/v1/tags/{id}` | `/api/v1/tag-system/tags/{tag_id}` | Tag-System Namespace |
> | `/api/v1/candidates/{id}` | `/api/v1/candidates/{candidate_id}` | Parameter-Name vereinheitlicht |
> | `X-API-Key` Header | `X-Auth-Token` Header | Auth-Header bevorzugt |
> | `mood_changed` Event | `mood` Event | Kanonischer Event-Typ |
> | `neuron_update` Event | `neuron` Event | Kanonischer Event-Typ |
> | `suggestion_new` Event | `suggestion` Event | Kanonischer Event-Typ |
>
> Für neue Integrationen ausschliesslich die aktive v13-Surface verwenden.

### Basis-Informationen

- **Protokoll:** HTTP/HTTPS
- **Format:** JSON
- **Authentifizierung:** API Key (X-Auth-Token) oder Bearer Token
- **Rate Limiting:** 100 Requests/Minute pro API-Key

---

## Authentifizierung

### API Key Authentication (Standard)

Die meisten Endpoints verwenden API-Key-Authentifizierung:

```http
X-Auth-Token: dein-api-key-hier
```

> **Hinweis:** `X-API-Key` ist deprecated. Verwende stattdessen `X-Auth-Token` oder `Authorization: Bearer ...`.

### Bearer Token Authentication

Bestimmte Endpunkte (Notifications, Telegram) verwenden Bearer-Token:

```http
Authorization: Bearer dein-jwt-token
```

### Beispiel Request

```bash
curl -X GET "http://localhost:8909/api/v1/system_health" \
  -H "X-Auth-Token: your-api-key"
```

---

## API-Endpoints nach Kategorie

### System Health

Überwachung der Systemintegrität, Ressourcennutzung und Netzwerkdienste.

#### `GET /api/v1/system_health`

Kompletten System-Health-Status abrufen.

**Authentifizierung:** API Key  
**Response:**
```json
{
  "status": "healthy",
  "cpu": {
    "usage_percent": 23.5,
    "cores": 4,
    "temperature": 45.2
  },
  "memory": {
    "total_mb": 8192,
    "used_mb": 4096,
    "percent": 50.0
  },
  "disk": {
    "total_gb": 128,
    "used_gb": 64,
    "percent": 50.0
  },
  "services": [
    {
      "name": "habitus_miner",
      "status": "running"
    }
  ]
}
```

#### `GET /api/v1/system_health/zigbee`

Zigbee-Mesh-Gesundheit abrufen.

**Parameter:**
- `force` (boolean, optional): Erzwingt Refresh vom Koordinator

**Response:**
```json
{
  "coordinator": {
    "ieee": "00:12:4b:00:12:34:56:78",
    "status": "connected",
    "channel": 15
  },
  "devices": [
    {
      "ieee": "00:12:4b:00:87:65:43:21",
      "nwk": "0x1234",
      "lqi": 255,
      "rssi": -42
    }
  ]
}
```

#### `GET /api/v1/system_health/zwave`

Z-Wave-Mesh-Gesundheit abrufen.

---

### Brain Graph

Wissensgraph für Event-Speicherung, Pattern-Mining und neuronale Visualisierung.

#### `GET /api/v1/graph/state`

Aktuellen Graph-Zustand als JSON abrufen.

**Parameter:**
- `kind` (string, wiederholbar): Filter nach Node-Kind
- `domain` (string, wiederholbar): Filter nach Domain
- `center` (string, optional): Center-Node für Neighborhood-Query
- `hops` (integer, default: 1): Anzahl Hops für Neighborhood
- `limitNodes` (integer, default: 100): Maximale Nodes
- `nocache` (boolean, default: false): Cache umgehen

**Response:**
```json
{
  "nodes": [...],
  "edges": [...],
  "metadata": {
    "total_nodes": 1523,
    "total_edges": 4521,
    "last_updated": "2026-03-01T22:00:00Z"
  }
}
```

#### `POST /api/v1/graph/render`

Graph-Visualisierung generieren (SVG oder PNG).

**Request Body:**
```json
{
  "format": "svg",
  "layout": "force",
  "filters": {}
}
```

**Response:** SVG oder PNG Binary

#### `POST /api/v1/graph/query`

Komplexe Graph-Queries ausführen.

**Request Body:**
```json
{
  "query": "MATCH (n:Event) WHERE n.zone = 'living-room' RETURN n",
  "parameters": {}
}
```

---

### Habitus & Pattern Mining

Mustererkennung und Automation-Candidate-Generierung.

#### `POST /api/v1/habitus/mine`

Pattern-Mining zur Automatisierungskandidaten-Entdeckung starten.

**Request Body (optional):**
```json
{
  "lookback_hours": 72,
  "force": false,
  "zone": "living-room"
}
```

**Response:**
```json
{
  "status": "started",
  "job_id": "mining-20260301-220000",
  "estimated_duration": "5m"
}
```

#### `GET /api/v1/habitus/stats`

Mining-Statistiken abrufen.

#### `GET /api/v1/habitus/patterns`

Zuletzt entdeckte Patterns abrufen.

**Parameter:**
- `limit` (integer, default: 50)

---

### Automation Candidates

Verwaltung von Automatisierungskandidaten.

#### `GET /api/v1/candidates`

Candidates mit optionalen Filtern auflisten.

**Parameter:**
- `state` (string, optional): `pending`, `offered`, `accepted`, `dismissed`, `deferred`
- `include_ready_deferred` (boolean, default: false)
- `limit` (integer, default: 50, max: 200)

**Response:**
```json
{
  "candidates": [
    {
      "id": "cand-001",
      "pattern_id": "pat-123",
      "state": "pending",
      "title": "Licht einschalten bei Anwesenheit",
      "description": "...",
      "automation_yaml": "alias: ...\ntrigger: ...\naction: ...",
      "confidence": 0.87,
      "created_at": "2026-03-01T10:00:00Z"
    }
  ],
  "count": 1
}
```

#### `POST /api/v1/candidates`

Neuen Candidate erstellen.

**Request Body:**
```json
{
  "pattern_id": "pat-123",
  "title": "Automation Title",
  "description": "Description",
  "automation_yaml": "alias: ...\ntrigger: ...\naction: ...",
  "confidence": 0.85
}
```

#### `GET /api/v1/candidates/{id}`

Spezifischen Candidate nach ID abrufen.

#### `PUT /api/v1/candidates/{id}`

Candidate-State aktualisieren (accept/dismiss/defer).

**Request Body:**
```json
{
  "state": "accepted",
  "reason": "Looks good!"
}
```

#### `GET /api/v1/candidates/stats`

Storage-Statistiken und Health abrufen.

---

### Mood & Zone Context

Zone-Mood-Scoring und ambienter Kontext.

#### `GET /api/v1/mood`

Alle Zone-Moods abrufen.

#### `GET /api/v1/mood/{zone_id}`

Spezifischen Zone-Mood abrufen.

#### `GET /api/v1/mood/summary`

Aggregierte Mood-Statistiken über alle Zonen.

#### `POST /api/v1/mood/update-media`

Moods basierend auf Media-Player-State aktualisieren.

**Request Body:**
```json
{
  "music_active": true,
  "tv_active": false,
  "primary_player": {
    "entity_id": "media_player.living_room",
    "state": "playing"
  }
}
```

#### `POST /api/v1/mood/update-habitus`

Moods basierend auf Habitus-Patterns aktualisieren.

#### `GET /api/v1/mood/{zone_id}/suppress-energy-saving`

Prüfen, ob Energy-Saving für Zone unterdrückt werden soll.

---

### Notifications

Notification-Engine mit Multi-Channel-Delivery.

#### `GET /api/v1/notifications`

Notification-History mit Filterung abrufen.

**Authentifizierung:** Bearer Token  
**Parameter:**
- `limit` (integer, default: 50)
- `source` (string, optional)
- `unread_only` (boolean, default: false)
- `type` (string): `mood_change`, `alert`, `suggestion`, `system`, `info`, `warning`

#### `POST /api/v1/notifications`

Neue Notification erstellen.

**Authentifizierung:** Bearer Token  
**Request Body:**
```json
{
  "title": "Fenster offen",
  "message": "Das Fenster im Badezimmer ist seit 10 Minuten offen.",
  "type": "alert",
  "priority": "normal",
  "channel": "push",
  "data": {
    "entity_id": "binary_sensor.bathroom_window"
  }
}
```

#### `GET /api/v1/notifications/digest`

Notification-Digest-Zusammenfassung abrufen.

#### `GET /api/v1/notifications/pending`

Ausstehende Notifications für Delivery abrufen.

#### `GET /api/v1/notifications/stats`

Notification-Engine-Statistiken abrufen.

---

### Sharing & Multi-Home

Cross-Home Entity-Sharing und Synchronisation.

#### `GET /api/v1/sharing`

Gesamten Sharing-System-Status abrufen (Sharing, Sync, Discovery).

#### `GET /api/v1/sharing/entities`

Alle geteilten Entities auflisten.

#### `POST /api/v1/sharing/entities`

Neues Entity für Cross-Home-Sharing registrieren.

**Request Body:**
```json
{
  "entity_id": "light.living_room",
  "name": "Wohnzimmer Licht",
  "type": "light",
  "home_id": "home-001",
  "capabilities": ["on_off", "brightness"],
  "metadata": {}
}
```

#### `GET /api/v1/sharing/sync/status`

Synchronisations-Status abrufen.

#### `GET /api/v1/sharing/discovery/peers`

Entdeckte Peer-CoPilot-Instances auflisten.

---

### Federated Learning

Verbundenes Lernen über mehrere Homes.

#### `GET /api/v1/federated`

Federated-Learning-System-Status abrufen.

#### `POST /api/v1/federated/start`

Federated-Learning-Service starten.

#### `POST /api/v1/federated/stop`

Federated-Learning-Service stoppen.

#### `POST /api/v1/federated/register`

Neuen Home-Node in der Föderation registrieren.

**Request Body:**
```json
{
  "home_id": "home-001",
  "name": "Zuhause",
  "capabilities": ["habitus", "energy", "presence"]
}
```

#### `POST /api/v1/federated/update`

Lokales Model-Update an die Föderation übermitteln.

#### `POST /api/v1/federated/round`

Neue Federated-Learning-Runde starten.

#### `POST /api/v1/federated/aggregate`

Model-Aggregation für eine Runde ausführen.

#### `GET /api/v1/federated/rounds`

Historie der Federated-Learning-Runden abrufen.

#### `GET /api/v1/federated/statistics`

Umfassende Federated-Learning-Statistiken abrufen.

---

### Energy Monitoring

Energieüberwachung und -optimierung.

#### `GET /api/v1/energy`

Kompletten Energy-Snapshot abrufen.

#### `GET /api/v1/energy/anomalies`

Erkannte Energy-Anomalien abrufen.

#### `GET /api/v1/energy/sankey`

Sankey-Diagramm-Daten für Energy-Flows abrufen.

---

### UniFi Network

UniFi-Netzwerküberwachung.

#### `GET /api/v1/unifi`

Kompletten UniFi-Network-Snapshot abrufen.

**Authentifizierung:** Bearer Token

---

### Tag System

Tag-System für Entity-Organisation.

#### `GET /api/v1/tags`

Alle Tags auflisten.

**Authentifizierung:** Bearer Token

#### `POST /api/v1/tags`

Neues Tag erstellen.

**Authentifizierung:** Bearer Token

#### `DELETE /api/v1/tags/{id}`

Tag löschen.

**Authentifizierung:** Bearer Token

---

### Dev Surface

Development-Observability und Diagnostics.

#### `GET /api/v1/dev/logs`

Aktuelle Log-Einträge mit Filterung abrufen.

**Parameter:**
- `limit` (integer, default: 100)
- `level` (string): `DEBUG`, `INFO`, `WARNING`, `ERROR`

#### `GET /api/v1/dev/errors`

Fehler-Zusammenfassung und Statistiken abrufen.

---

### Telegram Integration

Telegram-Bot-Integration.

#### `GET /telegram/status`

Telegram-Bot-Status abrufen.

**Authentifizierung:** Bearer Token

#### `POST /telegram/send`

Proaktive Nachricht an Telegram-Chat senden.

**Authentifizierung:** Bearer Token  
**Request Body:**
```json
{
  "chat_id": "123456789",
  "text": "Hallo! Dies ist eine Testnachricht."
}
```

---

### PilotSuite Hub

Zentrales Management-Interface.

#### `GET /api/v1/hub/status`

Kompletten Hub-Status inkl. aller Engines abrufen.

**Authentifizierung:** Bearer Token

#### `GET /api/v1/hub/zones`

Alle konfigurierten Zonen auflisten.

**Authentifizierung:** Bearer Token

#### `GET /api/v1/hub/modes`

Alle konfigurierten Modi auflisten.

**Authentifizierung:** Bearer Token

---

### Vector Search & RAG

Vektorsuche und Retrieval-Augmented-Generation.

#### `GET /api/v1/vector`

Vektoren auflisten.

#### `POST /api/v1/vector/embeddings`

Embeddings generieren.

#### `POST /api/v1/vector/search`

Semantische Suche durchführen.

#### `POST /api/v1/vector/rerank`

Suchergebnisse neu ranken.

---

### Voice & Conversation

Sprachsteuerung und Konversation.

#### `POST /api/v1/voice/chat`

Chat-Kompletierung mit Voice-Context.

#### `GET /api/v1/voice/models`

Verfügbare Voice-Modelle auflisten.

#### `POST /api/v1/voice/speak`

Text-to-Speech ausführen.

---

### Calendar

Kalender-Integration.

#### `GET /api/v1/calendar`

Kalender-Entities auflisten.

#### `GET /api/v1/calendar/events/today`

Heutige Events abrufen.

#### `GET /api/v1/calendar/events/upcoming`

Bevorstehende Events abrufen.

---

### Anomaly Detection

Anomalieerkennung für Sensoren.

#### `GET /api/v1/anomaly/detect`

Anomalien erkennen.

#### `GET /api/v1/anomaly/history`

Anomalie-Historie abrufen.

#### `GET /api/v1/anomaly/sensor/{sensor_id}/health`

Sensor-Gesundheit abrufen.

#### `POST /api/v1/anomaly/train`

Modell trainieren.

---

### User Management

Benutzerverwaltung und Präferenzen.

#### `GET /api/v1/users`

Alle Benutzer auflisten.

#### `GET /api/v1/users/{user_id}/preferences`

Benutzerpräferenzen abrufen.

#### `POST /api/v1/users/{user_id}/preference`

Benutzerpräferenz setzen.

---

### Presence Detection

Anwesenheitserkennung.

#### `GET /api/v1/presence`

Aktuelle Anwesenheitsstatus abrufen.

#### `POST /api/v1/presence/update`

Anwesenheitsstatus aktualisieren.

---

### Media Zones

Medienzonen-Steuerung.

#### `GET /api/v1/media/zones`

Alle Media-Zonen abrufen.

#### `POST /api/v1/media/zones/{zone_name}/orchestrate`

Media-Orchestrierung für Zone ausführen.

---

### Module Control

Modulsteuerung.

#### `GET /api/v1/modules`

Alle Module auflisten.

#### `POST /api/v1/modules/{module_id}/enable`

Modul aktivieren.

#### `POST /api/v1/modules/{module_id}/disable`

Modul deaktivieren.

---

### Blueprint System

Blueprint-Verwaltung.

#### `GET /api/v1/blueprints`

Alle Blueprints auflisten.

#### `POST /api/v1/blueprints`

Neuen Blueprint erstellen.

---

### HomeKit Integration

HomeKit-Integration.

#### `GET /api/v1/homekit/status`

HomeKit-Status abrufen.

#### `POST /api/v1/homekit/sync`

HomeKit-Synchronisation ausführen.

---

### Metrics & Monitoring

Metriken und Monitoring.

#### `GET /api/v1/metrics`

System-Metriken abrufen.

#### `GET /api/v1/metrics/prometheus`

Prometheus-Metriken exportieren.

---

### Reminders

Erinnerungen verwalten.

#### `GET /api/v1/reminders`

Alle Erinnerungen abrufen.

#### `POST /api/v1/reminders`

Neue Erinnerung erstellen.

#### `DELETE /api/v1/reminders/{id}`

Erinnerung löschen.

---

### Search

Erweiterte Suche.

#### `POST /api/v1/search`

Semantische Suche durchführen.

#### `POST /api/v1/search/bm25`

BM25-Suche durchführen.

#### `POST /api/v1/search/enhanced`

Erweiterte Suche mit Hybrid-Scoring.

---

### User Hints

Benutzerhinweise und Vorschläge.

#### `GET /api/v1/hints`

Alle Hinweise abrufen.

#### `POST /api/v1/hints/{hint_id}/accept`

Hinweis akzeptieren.

#### `POST /api/v1/hints/{hint_id}/reject`

Hinweis ablehnen.

---

### Websocket Neuron

Websocket-basierte Neuronen-Kommunikation.

#### `GET /api/v1/neuron`

Neuron-Status abrufen.

#### `POST /api/v1/neuron/fire`

Neuron feuern.

---

### Voice Context

Voice-Context-Verwaltung.

#### `GET /api/v1/voice-context`

Voice-Context abrufen.

#### `POST /api/v1/voice-context`

Voice-Context aktualisieren.

---

### Styx Chat

Styx-Chat-Integration.

#### `POST /api/v1/styx/chat`

Chat-Nachricht an Styx senden.

---

### Dashboard Cards

Dashboard-Cards für die Übersicht.

#### `GET /api/v1/dashboard/cards`

Dashboard-Cards abrufen.

#### `POST /api/v1/dashboard/cards/refresh`

Cards aktualisieren.

---

### Service Control

Service-Steuerung.

#### `GET /api/v1/service/status`

Service-Status abrufen.

#### `POST /api/v1/service/restart`

Service neu starten.

---

## Fehlerbehandlung

### Standard-Fehlerantwort

```json
{
  "status": "error",
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found",
    "details": {
      "resource": "candidate",
      "id": "cand-001"
    }
  }
}
```

### HTTP-Status-Codes

| Code | Bedeutung | Beschreibung |
|------|-----------|--------------|
| 200 | OK | Request erfolgreich |
| 201 | Created | Resource erfolgreich erstellt |
| 204 | No Content | Erfolgreich, kein Content |
| 400 | Bad Request | Ungültige Request-Daten |
| 401 | Unauthorized | Authentifizierung erforderlich |
| 403 | Forbidden | Keine Berechtigung |
| 404 | Not Found | Resource nicht gefunden |
| 429 | Too Many Requests | Rate Limit überschritten |
| 500 | Internal Server Error | Server-Fehler |

---

## Rate Limiting

- **Standard:** 100 Requests/Minute pro API-Key
- **Burst:** 150 Requests in 10 Sekunden
- **Limit-Header:** `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## Versionierung

API-Versionierung wird über den `Accept-Version`-Header unterstützt:

```http
Accept-Version: v1
```

Deprecated-Endpoints enthalten `Deprecation` und `Sunset`-Header in Responses.

---

## Swagger UI

Interaktive API-Dokumentation verfügbar unter:

**URL:** `http://localhost:8909/docs`

Features:
- Try-It-Out für alle Endpoints
- Authentication-Flow integriert
- Example Requests/Responses
- OpenAPI-Spec Download (YAML/JSON)

---

## Support

- **GitHub:** https://github.com/GreenhillEfka/pilotsuite-styx-core
- **Dokumentation:** `/docs` Verzeichnis im Repository
- **Issues:** GitHub Issues Tracker
