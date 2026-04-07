# Zone Dashboard API & Frontend

## Übersicht

Das Zone Dashboard bietet eine Echtzeit-Übersicht aller Habitus-Zonen mit Status, Mood-Scores und Quick-Actions.

**Autor:** Clawdya (via Codex)  
**Version:** 1.0.0  
**Datum:** 2026-03-01

---

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                     Zone Dashboard                          │
├─────────────────────────────────────────────────────────────┤
│  Frontend (zone_dashboard.js)                               │
│  - Lit Web Component                                        │
│  - Grid-Layout mit Zone-Cards                               │
│  - Auto-Refresh (30s)                                       │
│  - Quick-Actions                                            │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│  Backend API (zone_dashboard.py)                            │
│  - /api/v1/zone/dashboard                                   │
│  - /api/v1/zone/dashboard/summary                           │
│  - /api/v1/zone/dashboard/mood                              │
│  - /api/v1/zone/dashboard/quick-action                      │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│  Habitus Zones (habitus_zones.py)                           │
│  - Zonendaten aus HA                                        │
│  - Entity-Zuordnungen                                       │
│  - Metadata                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## API Endpunkte

### GET `/api/v1/zone/dashboard`

Komplette Dashboard-Daten aller Zonen.

**Query Parameters:**
- `include_entities` (bool, default: true) - Entity-Details einschließen
- `include_mood` (bool, default: true) - Mood-Scores einschließen
- `include_actions` (bool, default: true) - Quick-Actions einschließen

**Response:**
```json
{
  "ok": true,
  "zones": [
    {
      "zone_id": "zone:wohnzimmer",
      "name": "Wohnzimmer",
      "zone_type": "room",
      "status": "active",
      "person_count": 0,
      "entity_count": 4,
      "entity_counts_by_domain": {
        "light": 2,
        "sensor": 1,
        "binary_sensor": 1
      },
      "mood": {
        "comfort": 0.7,
        "joy": 0.6,
        "frugality": 0.8,
        "updated_at": "2026-03-01T12:00:00Z"
      },
      "quick_actions": [
        {
          "action_id": "zone:wohnzimmer_lights_on",
          "name": "Licht an",
          "icon": "mdi:lightbulb",
          "service": "light.turn_on",
          "target": {"entity_id": "all_lights_in_zone"}
        }
      ]
    }
  ],
  "count": 1,
  "generated_at": "2026-03-01T12:00:00Z"
}
```

---

### GET `/api/v1/zone/dashboard/summary`

Leichte Zusammenfassung ohne Details.

**Response:**
```json
{
  "ok": true,
  "summary": {
    "total_zones": 3,
    "active_zones": 1,
    "idle_zones": 2,
    "total_entities": 12,
    "total_persons": 0,
    "zone_types": {
      "room": 3
    }
  },
  "generated_at": "2026-03-01T12:00:00Z"
}
```

---

### GET `/api/v1/zone/dashboard/mood`

Mood-Daten aller Zonen.

**Response:**
```json
{
  "ok": true,
  "mood": {
    "zone:wohnzimmer": {
      "comfort": 0.7,
      "joy": 0.6,
      "frugality": 0.8
    },
    "zone:kuche": {
      "comfort": 0.8,
      "joy": 0.5,
      "frugality": 0.9
    }
  },
  "count": 2
}
```

---

### PUT `/api/v1/zone/dashboard/mood/<zone_id>`

Mood für eine Zone setzen (für Testing/Demo).

**Payload:**
```json
{
  "comfort": 0.9,
  "joy": 0.7,
  "frugality": 0.6
}
```

---

### POST `/api/v1/zone/dashboard/quick-action`

Quick-Action ausführen.

**Payload:**
```json
{
  "zone_id": "zone:wohnzimmer",
  "action_id": "zone:wohnzimmer_lights_on",
  "service": "light.turn_on",
  "target": {"entity_id": "light.wohnzimmer"},
  "data": {}
}
```

---

### GET `/api/v1/zone/dashboard/<zone_id>`

Detail-Daten einer einzelnen Zone.

---

## Frontend Component

### Usage

```html
<zone-dashboard></zone-dashboard>
```

### Features

- **Grid-Layout**: Automatische Anpassung an Bildschirmgröße
- **Status-Anzeige**: Aktiv (grün), Idle (grau), Disabled (rot)
- **Mood-Visualisierung**: Balken für Komfort, Freude, Sparsamkeit
- **Entity-Stats**: Count nach Domain gruppiert
- **Quick-Actions**: Direkt ausführbare Aktionen pro Zone
- **Auto-Refresh**: Alle 30 Sekunden
- **Integration**: Link zum Zone Editor für Vollbearbeitung

### Styling

- Lit Web Component mit Shadow DOM
- Responsive Design (Mobile-first)
- Material Design-inspired
- Barrierefrei (ARIA-Labels)

---

## Tests

**28 Tests** in `tests/test_zone_dashboard.py`:

- API-Endpunkte (Dashboard, Summary, Mood, Quick-Actions)
- Entity-Counting und Status-Berechnung
- Query-Parameter-Filterung
- Edge Cases (leere Zonen, fehlende Metadata)
- Mock-Mood-Persistence

**Ausführen:**
```bash
cd /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app
python3 -m pytest tests/test_zone_dashboard.py -v
```

---

## Integration

### Backend Registrierung

In `copilot_core/core_setup.py`:

```python
from copilot_core.api.v1.zone_dashboard import zone_dashboard_bp, init_zone_dashboard_api

init_zone_dashboard_api()
app.register_blueprint(zone_dashboard_bp)
```

### Frontend Einbindung

```html
<script type="module" src="/static/zone_dashboard.js"></script>
<zone-dashboard></zone-dashboard>
```

---

## Erweiterungen (TODO)

- [ ] Echte HA Entity-State-Integration
- [ ] WebSocket für Echtzeit-Updates
- [ ] Mood-Berechnung aus Sensor-Daten
- [ ] Personen-Erkennung via device_tracker
- [ ] Custom Quick-Actions definieren
- [ ] Dashboard-Export (PDF, PNG)
- [ ] Historie / Trends

---

## Changelog

### 1.0.0 (2026-03-01)

- Initiale Version
- API: Dashboard, Summary, Mood, Quick-Actions
- Frontend: Lit Web Component
- Tests: 28 Tests
- Dokumentation: README.md
