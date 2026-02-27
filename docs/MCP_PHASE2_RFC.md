# MCP Phase 2 RFC — Erweiterte Skills für AI-Clients

> **Status**: Phase 1 abgeschlossen, Phase 2 teilweise umgesetzt
> **Baseline**: v10.4.0
> **Urspruenglich geplant fuer**: v7.27.0 (ueberholt durch Architektur-Ueberarbeitung v9.0+)

---

## Aktueller Stand (Phase 1)

Styx MCP Server bietet bereits **10 Tools** an:

| Tool | Beschreibung |
|------|-------------|
| `pilotsuite.get_mood` | Mood Scores (Comfort/Joy/Frugality) pro Zone |
| `pilotsuite.get_brain_graph` | Entity-Beziehungen, Co-Occurrence Patterns |
| `pilotsuite.get_habitus_patterns` | A->B Verhaltensregeln (Support/Confidence/Lift) |
| `pilotsuite.get_neuron_summary` | Neural Pipeline Summary (Mood/Energy/Weather/Presence) |
| `pilotsuite.get_preferences` | Gelernte User-Preferences (Lifelong Learning) |
| `pilotsuite.get_household` | Haushaltsprofil (Mitglieder/Rollen/Präferenzen) |
| `pilotsuite.search_memory` | Suche in Konversationsgedächtnis |
| `pilotsuite.get_energy_stats` | Energiestatistik (Verbrauch/Solar/Batterie) |
| `pilotsuite.search_web` | Web-Suche via SearXNG |
| `pilotsuite.notify` | Push-Notification versenden |

---

## Phase 2 — geplante Erweiterungen

> **Hinweis (2026-02-27):** Durch die Architektur-Ueberarbeitung in v9.0-v10.4 wurden einige Phase-2-Konzepte
> in andere Module integriert. Scene Automation ist teilweise durch zone_automation und auto_setup abgedeckt.
> Multi-Zone Audio ist durch media_zones implementiert. Dieses RFC dient als Referenz fuer verbleibende
> Erweiterungen.

### 1. **Scene Automation Skills** (HIGH PRIORITY)
AI-Clients sollen Szenen nicht nur abfragen, sondern auch erstellen/bearbeiten können — basierend auf Nutzerverhalten.

| Tool | Beschreibung | Input |
|------|-------------|-------|
| `pilotsuite.create_scene_from_behavior` | Erstelle Szene aus wiederholtem Verhalten (z.B. "Licht an + TV an um 20:00") | `name`, `entities`, `trigger_time`, `condition` |
| `pilotsuite.update_scene` | Bestehende Szene anpassen | `scene_id`, `updates` |
| `pilotsuite.delete_scene` | Szene entfernen | `scene_id` |
| `pilotsuite.list_scenes` | Alle Szenen auflisten | `limit`, `filter_by` |

**Use Case**:  
> "Erstelle eine Szene 'Movie Night' mit dimmed lights + TV an + Sonos Volume 30"

---

### 2. **Multi-Zone Audio Control** (MEDIUM PRIORITY)
AI-Clients sollen Medienzonen steuern können — ideal für "Kinderzimmer-Mode", "Party-Mode", etc.

| Tool | Beschreibung | Input |
|------|-------------|-------|
| `pilotsuite.play_media_in_zone` | Medien in Zone abspielen | `zone_id`, `media_url`, `media_type`, `title` |
| `pilotsuite.group_zones` | Mehrere Zonen gruppieren | `zone_ids`, `master_zone_id` |
| `pilotsuite.ungroup_zones` | Gruppierung auflösen | `zone_ids` |
| `pilotsuite.set_volume_for_zone` | Volume pro Zone anpassen | `zone_id`, `volume` (0-1) |

**Use Case**:  
> "Stelle alle Zonen auf 'Schlafen' und setze Kinderschlafzimmer auf 'aus'"

---

### 3. **Security & Access Control** (HIGH PRIORITY)
Keine Automatik ohne explizite Genehmigung — AI-Clients können Sicherheits-Entitäten abfragen und manuell steuern.

| Tool | Beschreibung | Input |
|------|-------------|-------|
| `pilotsuite.get_door_status` | Türstatus (offen/geschlossen/verriegelt) | `entity_id` |
| `pilotsuite.lock_door` | Tür verriegeln | `entity_id` |
| `pilotsuite.unlock_door` | Tür entriegeln | `entity_id` |
| `pilotsuite.get_camera_status` | Kameras status | `entity_id` |
| `pilotsuite.record_camera` | Kamera-Aufnahme starten | `entity_id`, `duration` |

**Use Case**:  
> "Prüfe alle Türen und verriegele die Haustür, wenn offen"

---

### 4. **Maintenance & Diagnostics** (MEDIUM PRIORITY)
Systemüberwachung, Log-Abfragen, Fehleranalyse — für Self-Healing und Troubleshooting.

| Tool | Beschreibung | Input |
|------|-------------|-------|
| `pilotsuite.get_system_health` | System-Health-Check (Zigbee/Z-Wave/Recorder) | `include_details` |
| `pilotsuite.get_error_log` | Fehler-Log abfragen | `since`, `limit`, `filter` |
| `pilotsuite.restart_service` | Service neu starten | `service_name` |
| `pilotsuite.diagnose_network` | Netzwerk-Diagnose (Ping, Latency) | `target`, `count` |

**Use Case**:  
> "Warum läuft mein Sensor nicht mehr? Prüfe Zigbee-Status und Firmware"

---

### 5. **Calendar & Scheduling** (LOW PRIORITY)
Termine abfragen, intelligente Zeitplanung basierend auf Stimmung.

| Tool | Beschreibung | Input |
|------|-------------|-------|
| `pilotsuite.get_upcoming_events` | Kommtende Termine (nächste 24h) | `hours`, `limit` |
| `pilotsuite.get_today_schedule` | Heutiger Tagesplan | `start`, `end` |
| `pilotsuite.suggest_optimal_time` | Intelligentes Zeitvorschlag (basierend auf Mood) | `event_type`, `duration` |

**Use Case**:  
> "Ich habe morgen einen vollen Tag — schlage eine optimale Aufstehzeit vor"

---

### 6. **Weather-Based Automation** (MEDIUM PRIORITY)
Wettervorhersage integrieren, um automatisch zu reagieren — aber immer mit Human-in-the-Loop.

| Tool | Beschreibung | Input |
|------|-------------|-------|
| `pilotsuite.get_weather_forecast` | Wettervorhersage (nächste 24h) | `hours`, `include_warnings` |
| `pilotsuite.check_weather_trigger` | Prüfen, ob Wetter-Automatik greift | `entity_id`, `trigger_condition` |
| `pilotsuite.suggest_weather_action` | Vorschlag basierend auf Wetter | `weather_condition`, `entity_type` |

**Use Case**:  
> "Es regnet bald — schlage vor, Fenster zu schließen"

---

## Priorisierung & Release-Ziel

| Feature | Priority | Geschätzt | Release |
|---------|----------|-----------|---------|
| Scene Automation Skills | HIGH | 1-2h | v7.27.0 |
| Multi-Zone Audio Control | MEDIUM | 1h | v7.27.0 |
| Security & Access Control | HIGH | 1h | v7.27.0 |
| Maintenance & Diagnostics | MEDIUM | 1h | v7.27.0 |
| Calendar & Scheduling | LOW | 0.5h | v7.28.0 |
| Weather-Based Automation | MEDIUM | 1h | v7.28.0 |

**Total Estimate**: ~6h Entwicklungszeit  
**Release-Ziel**: v7.27.0 (Phase 2 Core), v7.28.0 (Phase 2 Extended)

---

## Implementierungs-Checklist

### Phase 2 Core (v7.27.0)
- [ ] `pilotsuite.create_scene_from_behavior`
- [ ] `pilotsuite.list_scenes`
- [ ] `pilotsuite.play_media_in_zone`
- [ ] `pilotsuite.get_door_status`
- [ ] `pilotsuite.get_system_health`
- [ ] Tests für alle 5 Tools
- [ ] Dokumentation aktualisieren

### Phase 2 Extended (v7.28.0)
- [ ] `pilotsuite.get_upcoming_events`
- [ ] `pilotsuite.get_weather_forecast`
- [ ] `pilotsuite.suggest_weather_action`
- [ ] Integrationstests für neue Features

---

## Notes

- **Safety**: Keine Automatik bei Sicherheits-Entitäten (Türen, Kameras) — AI-Clients müssen explizite `*_door` Aufrufe machen
- **Consistency**: Alle Tools folgen demselben Muster (inputSchema, required fields, error handling)
- **Testing**: Jedes Tool bekommt Unit-Test (`test_mcp_server.py` erweitern)
- **Documentation**: OpenAPI-Spec aktualisieren (`docs/integrations/onyx_styx_actions.openapi.yaml`)

---

**Next Step**: Implementierung der 5 Core Tools starten → `copilot_core/mcp_tools.py` erweitern
