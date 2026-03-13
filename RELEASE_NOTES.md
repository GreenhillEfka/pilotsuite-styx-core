# Release v13.9.0 — Offizielles Release mit allen Beitraegen

**Datum:** 2026-03-13
**Branch:** main
**Tag:** `v13.9.0`
**HA hassfest:** compliant
**Paired Release:** Core v13.9.0 <-> HA v13.9.0

---

## Ueberblick

PilotSuite v13.9.0 ist das konsolidierte offizielle Release, das **alle Entwicklungen seit v13.5.8** zusammenfasst. Es umfasst 6 Major-Feature-Bereiche, umfangreiche Code-Qualitaet-Verbesserungen und kritische Bugfixes.

---

## Highlights

### 1. RAG Hybrid Search & Wetter-Integration
- **Reciprocal Rank Fusion (RRF)**: BM25 + Semantic Search kombiniert fuer praezisere Chat-Antworten
- **Open-Meteo Wetter**: Echtzeit-Wetterdaten direkt im Chat abrufbar
- **Wecker-Modul**: Neues Hub-Modul fuer Alarm- und Weckfunktionalitaet

### 2. Zone Dashboard v3 (11 Hub-Engines)
- Zonenzentriertes Dashboard mit vollstaendiger Modulintegration
- Controls, Musik, Playlists, Notifications, Birthdays, Todos pro Zone
- Refactored fuer Effizienz und Failsafety
- Styx Dashboard SPA mit 9 Tabs und Keyboard Shortcuts

### 3. 5 PilotSuite Smart Home Module
| Modul | Beschreibung |
|-------|-------------|
| `licht_module.py` | Lichtsteuerung mit Szenen und Dimming |
| `helligkeit_module.py` | Helligkeitssensor-Auswertung und Lux-Management |
| `heiz_module.py` | Heizungssteuerung mit Zieltemperatur und Zeitplaenen |
| `bewegung_module.py` | Bewegungsmelder-Aggregation und Raumaktivitaet |
| `praesenz_module.py` | Praesenz-Tracking und Aufenthaltsanalyse |

### 4. Musikwolke Bridge — End-to-End Sonos-Integration
- MusikwolkeBridge verbindet ZoneAutomationController mit SonosCloudClient
- Zone-Speaker-Mapping (automatisch und manuell)
- Follow-Mode: Musik folgt dem Nutzer zwischen Raeumen
- 8 REST-Endpoints unter `/api/v1/musikwolke/`
- Sonos jishi API Integration (Port 5005)

### 5. Zone Automation Controller
- Praesenzabhaengige Licht- und Musiksteuerung
- 3-Stufen-Modus pro Zone (off/learning/autonomy)
- Entity-Management mit Auto-Rollenerkennung (11 Rollen, 13 Tags)
- 16 API-Endpoints unter `/api/v1/zone-automation/`
- Hysterese/Daempfung gegen Flackern bei Wolkendurchzug

### 6. Code-Qualitaet & Hardening
- Thread-Safety Verbesserungen (Double-Checked Locking)
- Resource Leaks geschlossen
- Silent `except: pass` Bloecke durch Debug-Logging ersetzt
- App Factory verbessert mit Shared Brightness Filter
- Automation Hardening mit From-State Guards

---

## API-Endpunkte (neu seit v13.5.8)

| API Pfad | Beschreibung |
|----------|-------------|
| `POST /api/v1/musikwolke/create` | Musikwolke-Gruppe erstellen |
| `POST /api/v1/musikwolke/dissolve` | Musikwolke-Gruppe aufloesen |
| `POST /api/v1/musikwolke/volume/<zone_id>` | Lautstaerke setzen |
| `POST /api/v1/media/zones/<id>/play` | Wiedergabe starten |
| `POST /api/v1/media/zones/<id>/pause` | Wiedergabe pausieren |
| `POST /api/v1/media/musikwolke/start` | Follow-Session starten |
| `POST /api/v1/media/musikwolke/<id>/stop` | Follow-Session beenden |
| `GET/POST /api/v1/zone-automation/zones/<id>/mode` | Automation-Modus |
| `GET/POST /api/v1/zone-automation/zones/<id>/config` | Zone Config |
| `GET/POST/DELETE /api/v1/zone-automation/zones/<id>/entities` | Entity CRUD |
| `POST /api/v1/zone-automation/zones/<id>/presence` | Praesenz-Event |
| `POST /api/v1/zone-automation/zones/<id>/brightness` | Helligkeit-Update |
| `GET /api/v1/zone-automation/dashboard` | Automation Dashboard |
| `POST /api/v1/tag-system/tags/sync` | Tag-Synchronisierung |
| `GET /api/v1/suggestions` | KI-Vorschlaege |
| `GET /api/v1/modules/dashboard` | Aggregiertes Modul-Dashboard |

---

## Kritische Bug Fixes

- `async init_services()` ohne `await` aufgerufen
- Voice zone aliases Bug
- Deprecated asyncio event loop patterns in 11 Dateien
- Illumination ratio negative Werte
- Fehlende Engine-Referenzen und async init
- Musikwolke Pipeline Error handling

---

## Upgrade-Hinweise

- **Breaking Changes:** Keine
- **Migration:** `ha addons update pilotsuite_core`
- **Neue Dependencies:** Keine
- **Mindestversion Core:** v13.9.0

---

## Statistiken

| Metrik | Wert |
|--------|------|
| Commits seit v13.5.8 | 30+ |
| Neue Dateien | 25+ |
| Tests | 3720+ passed, 0 failed |
| API-Endpoints (gesamt) | 130+ |
| Hub-Engines | 17+ |
| Smart Home Module | 5 |

---

**PilotSuite v13.9.0** — Local-first, Privacy-first, Governance-first.
