# PilotSuite Styx - Handbuch

## Inhaltsverzeichnis

1. [Installation](#installation)
2. [Ersteinrichtung](#ersteinrichtung)
3. [Habitus Zonen](#habitus-zonen)
4. [Entity Tags](#entity-tags)
5. [Auto-Setup](#auto-setup)
6. [Dashboard](#dashboard)
7. [Module](#module)
8. [Mood System](#mood-system)
9. [Brain Graph](#brain-graph)
10. [Troubleshooting](#troubleshooting)

---

## Installation

### Voraussetzungen
- Home Assistant 2024.1.0 oder neuer
- HACS (Home Assistant Community Store) installiert
- PilotSuite Core Add-on installiert (Port 8909)

### HACS Installation
1. HACS > Integrations > Custom Repositories
2. Repository URL: `https://github.com/GreenhillEfka/Home-Assistant-Copilot`
3. Category: Integration
4. Install "PilotSuite - Styx"
5. Home Assistant neu starten

### Core Add-on Installation
1. Settings > Add-ons > Add-on Store
2. PilotSuite Core Add-on installieren
3. Starten und warten bis der Health-Check grün ist

---

## Ersteinrichtung

### Zero Config (empfohlen)
1. Settings > Integrations > Add Integration > "PilotSuite"
2. "Zero Config" wählen
3. Fertig! PilotSuite erkennt automatisch:
   - Deine HA Areas und erstellt Habitus Zonen
   - Alle Entities und taggt sie nach Typ (Licht, Sensor, Media, etc.)
   - Core Add-on Verbindung (Port 8909)
   - Conversation Agent (Styx)

### Quick Start (Wizard)
1. "Quick Start" wählen
2. Discovery: Auto-Discover aktivieren
3. Zonen: Aus erkannten Areas auswählen
4. Entities: Media Player, Lichter, Sensoren konfigurieren
5. Features: Module aktivieren
6. Netzwerk: Host/Port/Token eingeben
7. Review: Zusammenfassung prüfen und bestätigen

### Manual Setup (Experten)
1. "Manual Setup" wählen
2. Host, Port, Token manuell eingeben
3. Entity Profile wählen (core/full)

---

## Habitus Zonen

Habitus Zonen sind kuratierte Raum-Profile, unabhängig von HA Areas. Jede Zone gruppiert Entities nach Funktion.

### Zone erstellen
1. Settings > Integrations > PilotSuite > Configure
2. "Habitus zones" > "Create zone"
3. Areas auswählen (optional, für Auto-Fill)
4. Name vergeben
5. Entities nach Rolle zuweisen:
   - **Motion**: Bewegungssensor (treibt Präsenz-Erkennung)
   - **Lights**: Lichter der Zone
   - **Brightness**: Helligkeitssensoren
   - **Temperature**: Temperatursensoren
   - **Humidity**: Luftfeuchtesensoren
   - **Media**: Media Player
   - **Climate**: Heizung/Klima
   - **Covers**: Rollläden/Jalousien
   - **Cameras**: Kameras

### Zone Vorschläge von Core
1. "Suggest zones from Core" wählen
2. Core analysiert deine Entities und schlägt Zonen vor
3. Gewünschte Zonen adoptieren
4. Entities werden automatisch getaggt

### Bulk Edit
1. "Bulk edit (YAML/JSON)" wählen
2. Zonen als YAML oder JSON einfügen
3. Jede Zone braucht: `id`, `name`, `entity_ids`

---

## Entity Tags

Tags organisieren deine Entities in semantische Gruppen für das Neuron-System und die LLM-Kontext-Anreicherung.

### Tag erstellen
1. Configure > "Entity tags" > "Add tag"
2. Tag ID (Slug, z.B. `licht`)
3. Tag Name (Anzeigename, z.B. `Licht`)
4. Entities zuweisen
5. Farbe wählen (Hex, z.B. `#fbbf24`)

### Auto-Tags
Beim Auto-Setup werden automatisch Tags erstellt:

| Tag | Beschreibung | Farbe |
|-----|-------------|-------|
| Licht | Alle light.* Entities | Gelb (#fbbf24) |
| Bewegung | motion/presence Sensoren | Rot (#f87171) |
| Temperatur | Temperatursensoren | Orange (#f97316) |
| Helligkeit | Illuminance Sensoren | Gold (#eab308) |
| Feuchtigkeit | Humidity Sensoren | Cyan (#06b6d4) |
| Energie | Power/Energy Sensoren | Grün (#22c55e) |
| Media | Media Player | Lila (#a78bfa) |
| Klima | Climate Entities | Türkis (#34d399) |
| Beschattung | Cover/Rollläden | Orange (#fb923c) |
| Schalter | Switch Entities | Indigo (#6366f1) |
| Kamera | Kameras | Pink (#f472b6) |
| Person | Person Entities | Lila (#a78bfa) |
| Tür | Türkontakte | Violett (#8b5cf6) |
| Fenster | Fensterkontakte | Blau (#0ea5e9) |
| Sicherheit | Rauchmelder/Gas | Rot (#ef4444) |
| Batterie | Batterie-Sensoren | Lime (#84cc16) |

### Manual Override
- Tags können jederzeit manuell bearbeitet werden
- Entity-Zuweisungen überschreiben Auto-Tags
- Tags werden mit Core synchronisiert

---

## Auto-Setup

Das Auto-Setup läuft einmalig nach der Ersteinrichtung und konfiguriert PilotSuite automatisch.

### Was passiert automatisch?
1. **Area Discovery**: Alle HA Areas werden erkannt
2. **Zone Creation**: Für jede Area mit Entities wird eine Habitus Zone erstellt
3. **Entity Classification**: Jede Entity wird klassifiziert (4 Signale):
   - Domain (light → Licht)
   - Device Class (motion → Bewegung)
   - Unit of Measurement (lx → Helligkeit)
   - Name Keywords (DE + EN)
4. **Role Assignment**: Entities werden Zonen-Rollen zugewiesen
5. **Tag Creation**: Domain-basierte Tags werden erstellt

### Ergebnis prüfen
Nach dem Auto-Setup zeigt die Onboarding-Notification:
- Anzahl erstellter Zonen
- Anzahl zugewiesener Entities
- Anzahl erstellter Tags

---

## Dashboard

### Sidebar Panel
PilotSuite registriert automatisch einen "PilotSuite" Eintrag in der HA Sidebar. Dieser öffnet das Core-Dashboard mit:
- Brain Graph Visualisierung
- Mood Engine Status
- Neuron Activity
- Automation Candidates
- System Health

### YAML Dashboards
Optional werden Lovelace YAML Dashboards generiert:
- **PilotSuite Dashboard**: Übersicht aller Module und Sensoren
- **Habitus Zones Dashboard**: Zonenspezifische Karten

Aktivierung: Options > Modules > PilotSuite UI > Legacy YAML Dashboards

### Lovelace Cards
Core serviert Custom Lovelace Cards unter `/api/v1/cards/`. Diese werden automatisch als Lovelace Ressource registriert.

---

## Module

### Konfiguration
Settings > Integrations > PilotSuite > Configure > Modules

### Verfügbare Module

| Modul | Tier | Beschreibung |
|-------|------|-------------|
| **Mood System** | T1 | Stimmungserkennung pro Zone (Discrete + Continuous) |
| **Media Players** | T2 | Musik/TV Tracking und Steuerung |
| **Events Forwarder** | T0 | Echtzeit-Event-Weiterleitung an Core |
| **Suggestion Seed** | T1 | Automations-Vorschläge aus Sensor-Daten |
| **User Preferences** | T1 | Per-User Preference Tracking |
| **Waste Reminders** | T3 | Müllabfuhr-Erinnerungen mit TTS |
| **Birthday Reminders** | T3 | Geburtstags-Erinnerungen |
| **Zone Automation** | T1 | Präsenz-basierte Licht-/Klimasteuerung |
| **HA Error Digest** | T3 | Fehler-Analyse und Weiterleitung |
| **Dev Log Push** | T3 | Log-Weiterleitung an Core |
| **Watchdog** | T0 | Verbindungs-Health-Check |
| **PilotSuite UI** | T3 | Entity Profile und Button-Gruppen |

### Module-Tiers
- **T0 (Kernel)**: Immer aktiv, essenziell für Betrieb
- **T1 (Brain)**: Intelligenz-Schicht, aktiv wenn Core erreichbar
- **T2 (Context)**: Umgebungs-Awareness, aktiviert bei relevanten Entities
- **T3 (Extensions)**: Manuell aktivierbar

---

## Mood System

### Diskrete Stimmungen
| Stimmung | Beschreibung | Trigger |
|----------|-------------|---------|
| Away | Niemand zu Hause | Keine Präsenz erkannt |
| Night | Nachtmodus | Spät, wenig Licht |
| Relax | Entspannung | Abend, ruhig, angenehm |
| Focus | Konzentration | Tag, wenig Bewegung |
| Active | Aktivität | Morgen, Bewegung, Musik |
| Neutral | Standard | Default/Übergang |

### Kontinuierliche Dimensionen
| Dimension | Bereich | Einflussfaktoren |
|-----------|---------|-----------------|
| Comfort | 0.0–1.0 | Temperatur, Licht, Geräusch |
| Frugality | 0.0–1.0 | Energieverbrauch |
| Joy | 0.0–1.0 | Media, Events, Präsenz |
| Energy | 0.0–1.0 | Aktivitätslevel, Tagesrhythmus |
| Stress | 0.0–1.0 | Alarme, Benachrichtigungen, Fehler |

### Parameter
| Parameter | Default | Beschreibung |
|-----------|---------|-------------|
| EMA Alpha | 0.3 | Glättung (niedriger = sanfter) |
| Softmax Temperature | 1.0 | Entscheidungsschärfe |
| Dwell Time | 600s | Mindest-Verweildauer in Stimmung |
| History Retention | 30 Tage | Aufbewahrung der Mood-History |

---

## Brain Graph

### Konzept
Der Brain Graph ist ein leichtgewichtiger Wissensgraph (SQLite), der Entity-Beziehungen, Muster und Evidenz speichert.

### Nodes
- Entities (light, sensor, media_player, ...)
- Zones (Habitus Zonen)
- Automations
- Scripts

### Edges
- triggers (Entity A → Entity B)
- controls (Automation → Entity)
- correlated_with (statistische Korrelation)

### Decay
Nodes und Edges verlieren über Zeit an Relevanz:
- Node Half-Life: 24h
- Edge Half-Life: 12h
- Auto-Pruning: alle 60 Minuten

---

## Troubleshooting

### Core nicht erreichbar
1. Prüfe ob das Core Add-on läuft (Settings > Add-ons)
2. Health-Check: `http://homeassistant.local:8909/health`
3. Configure > Connection > Host/Port prüfen

### Keine Entities sichtbar
1. Prüfe ob `async_config_entry_first_refresh` erfolgreich war
2. Log prüfen: `Settings > System > Logs > ai_home_copilot`
3. Entity Profile: "core" zeigt nur essentielle Entities

### Auto-Setup hat keine Zonen erstellt
1. Prüfe ob HA Areas existieren (Settings > Areas & Zones)
2. Areas müssen Entities zugewiesen haben
3. Manuell Zonen erstellen: Configure > Habitus zones > Create zone

### Dashboard nicht in Sidebar
1. Panel wird nur registriert wenn Core erreichbar
2. Log prüfen: `"Failed to register PilotSuite sidebar panel"`
3. Alternative: Supervisor > PilotSuite Core > Ingress öffnen

### Mixed Languages in UI
Ab v10.4.0 ist die UI standardmäßig auf Englisch. Domain-Tags (Licht, Bewegung, etc.) bleiben deutsch als interne Bezeichner.

---

## Kommandos

### Tests ausführen
```bash
# HA Integration
cd pilotsuite-styx-ha
python -m pytest tests/ -v --tb=short -x

# Core Add-on
cd pilotsuite-styx-core
export PYTHONPATH=copilot_core/rootfs/usr/src/app
python -m pytest tests/ -v --tb=short -x
```

### Syntax prüfen
```bash
# HA
python -m py_compile $(find custom_components/ai_home_copilot -name '*.py')
python -c "import json; json.load(open('custom_components/ai_home_copilot/strings.json'))"

# Core
python -m py_compile $(find copilot_core/rootfs/usr/src/app -name '*.py')
```

### Version bumpen
```
HA: manifest.json → "version"
HA: entity.py → VERSION =
Core: config.yaml → version:
```
