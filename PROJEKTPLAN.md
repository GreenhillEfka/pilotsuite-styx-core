# PilotSuite Styx - Projektplan

## Release v10.4.0 — Consolidation & Auto-Setup

### Ziele
1. **Setup Flow** verbessern — Zero-Config mit Auto-Zone-Erstellung und Auto-Tagging
2. **Dashboard** konsolidieren — einheitliches Sidebar-Panel
3. **Zonen & Auto-Tagging** — ML-basierte Entity-Klassifikation und Zone-Vorschläge
4. **Core Backend** erweitern — neue API-Endpoints für Auto-Setup
5. **Dokumentation** erstellen — Vision, Projektplan, Handbuch

---

## Phase 1: Setup Flow (HA Integration)

### Änderungen
| Datei | Beschreibung |
|-------|-------------|
| `auto_setup.py` (neu) | Auto-Setup nach Config-Entry-Erstellung: Areas discovern, Zonen erstellen, Entities taggen |
| `__init__.py` | Auto-Setup eingehängt, verbessertes Onboarding-Notification mit Schritt-für-Schritt-Anleitung |
| `strings.json` | Mixed DE/EN normalisiert auf Englisch (wizard_entities, generate_dashboard) |

### Auto-Setup Ablauf
```
Config Entry erstellt
  → async_run_auto_setup(hass, entry)
    → area_registry.async_get(hass) → alle HA Areas
    → entity_registry.async_get(hass) → alle Entities
    → Entities nach Area gruppieren
    → Device-Class-basierte Rollen-Zuweisung
    → Habitus Zones aus Areas erstellen
    → Entity Tags nach Domain erstellen
    → Zusammenfassung loggen
```

### Regeln
- Nur beim ersten Start (Flag `_auto_setup_done`)
- NON-BLOCKING — bei Fehler läuft die Integration trotzdem
- Bestehende Zonen werden nicht überschrieben

---

## Phase 2: Dashboard (HA Integration)

### Änderungen
| Datei | Beschreibung |
|-------|-------------|
| `panel_setup.py` (neu) | Sidebar-Panel-Registrierung (iframe → Core Ingress) |
| `__init__.py` | Panel-Setup in `async_setup_entry`, Panel-Removal in `async_unload_entry` |

### Panel-Strategie
1. **Supervisor Ingress** (bevorzugt) — authentifiziert über HA, beste UX
2. **Direkte Core URL** (Fallback) — wenn kein Supervisor verfügbar
3. Panel-Name: `pilotsuite`, Icon: `mdi:robot-outline`

---

## Phase 3: Zonen & Auto-Tagging (HA Integration)

### Änderungen
| Datei | Beschreibung |
|-------|-------------|
| `entity_classifier.py` (neu) | ML-basierte Entity-Klassifikation mit 4 Signalen |
| `core/modules/entity_discovery.py` | `async_classify_entities()` Methode eingehängt |

### Klassifikations-Pipeline
```
Signal 1: Domain → Basis-Rolle (confidence 0.6)
Signal 2: Device Class → Override (confidence 0.9)
Signal 3: Unit of Measurement → Verfeinerung (confidence 0.8)
Signal 4: Keyword Matching DE+EN → Ergänzung (confidence 0.75)
```

### Rollen-Kategorien (14)
lights, presence, brightness, temperature, humidity, co2, noise, media, climate, covers, energy, cameras, doors, windows

### Auto-Tag Kategorien
| Tag ID | Name | Farbe | Trigger |
|--------|------|-------|---------|
| licht | Licht | #fbbf24 | domain=light |
| bewegung | Bewegung | #f87171 | device_class=motion |
| temperatur | Temperatur | #f97316 | device_class=temperature |
| feuchtigkeit | Feuchtigkeit | #06b6d4 | device_class=humidity |
| helligkeit | Helligkeit | #eab308 | device_class=illuminance |
| energie | Energie | #22c55e | device_class=energy/power |
| media | Media | #a78bfa | domain=media_player |
| klima | Klima | #34d399 | domain=climate |
| beschattung | Beschattung | #fb923c | domain=cover |
| kamera | Kamera | #f472b6 | domain=camera |
| tuer | Tür | #8b5cf6 | device_class=door |
| fenster | Fenster | #0ea5e9 | device_class=window |
| sicherheit | Sicherheit | #ef4444 | device_class=smoke |
| batterie | Batterie | #84cc16 | device_class=battery |

---

## Phase 4: Core Backend (Core Add-on)

### Neue Endpoints
| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/v1/auto-setup/suggest-zones` | POST | Zone-Vorschläge aus HA Area/Entity-Daten |
| `/api/v1/auto-setup/auto-tag` | POST | Auto-Tagging nach Domain/Device-Class |
| `/api/v1/auto-setup/status` | GET | Auto-Setup History und Status |

### Integration
- Blueprint: `auto_setup_bp` in `copilot_core/api/v1/auto_setup.py`
- Registrierung: `blueprint.py` und `core_setup.py`
- Verbindung: `tag_service` für persistente Tag-Erstellung

---

## Qualitätssicherung (3 Iterationen)

### Iteration 1: Funktionstest
- [ ] `python -m py_compile` für alle neuen/geänderten Dateien
- [ ] `python -c "import json; json.load(open('strings.json'))"` — JSON valide
- [ ] `python -m pytest tests/ -v --tb=short -x` — bestehende Tests bestehen
- [ ] Neue Module importierbar ohne Fehler

### Iteration 2: Strukturintegrität
- [ ] Keine zirkulären Imports
- [ ] Alle Imports resolven korrekt
- [ ] Auto-Setup idempotent (2x ausführen = gleicher State)
- [ ] Panel-Setup funktioniert ohne Supervisor (Fallback)
- [ ] Entity Classifier: deterministisch, keine Zufallselemente

### Iteration 3: Edge Cases & Polish
- [ ] Auto-Setup mit 0 Areas → kein Fehler
- [ ] Auto-Setup mit 50+ Areas → performant
- [ ] Classifier mit unbekanntem Domain → graceful fallback
- [ ] Panel-Setup ohne Core-Verbindung → Warning, kein Fehler
- [ ] strings.json vollständig Englisch (außer Domain-Tags)

---

## Versionierung

| Repository | Datei | Alt | Neu |
|------------|-------|-----|-----|
| pilotsuite-styx-ha | manifest.json | 10.3.0 | 10.4.0 |
| pilotsuite-styx-ha | entity.py | 10.3.0 | 10.4.0 |
| pilotsuite-styx-core | config.yaml | 10.3.0 | 10.4.0 |

---

## Release-Checkliste

- [ ] Alle 3 Iterationen durchlaufen
- [ ] Beide Repos auf Branch `claude/consolidate-repos-overview-bnGGO`
- [ ] Commit mit aussagekräftiger Message
- [ ] Push auf Branch
- [ ] PR erstellen (beide Repos)
- [ ] vision.md, projektplan.md, handbuch.md committed
