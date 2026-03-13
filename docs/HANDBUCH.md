# PilotSuite Styx — Benutzerhandbuch

**Version:** 13.9.0
**Datum:** 2026-03-11
**Sprache:** Deutsch

---

## 1. Was ist PilotSuite?

PilotSuite ist eine **lokale KI-Plattform fuer Smart Homes**, die auf Home Assistant aufsetzt. Sie besteht aus zwei Komponenten:

- **PilotSuite Core** (Add-on): Das Backend mit KI-Gehirn, neuronaler Pipeline, LLM-Chat und Automatisierungslogik
- **PilotSuite HA** (HACS-Integration): Sensoren, Dashboard, Services und UI-Elemente fuer Home Assistant

### Kernprinzipien

| Prinzip | Bedeutung |
|---------|-----------|
| **Local-first** | Alle Daten und KI-Modelle laufen lokal — keine Cloud |
| **Privacy-first** | Keine PII-Speicherung, opt-in fuer alle Features |
| **Governance-first** | Vorschlaege statt automatischer Aktionen (Human-in-the-Loop) |

---

## 2. Dashboard-Uebersicht

Das PilotSuite Dashboard hat 6+ Tabs:

### Tab 1: Styx (KI / Brain)
- **Neuronales Netzwerk**: Visualisierung des Brain Graphs als interaktives Diagramm
- **Stimmung**: Aktuelle Hausstimmung (z.B. "entspannt", "energisch")
- **KI-Vorschlaege**: Automatische Empfehlungen basierend auf Verhaltensmustern
- **Automatisierungen**: Status der praediktiven Automatisierung

### Tab 2: Haushalt
- **Praesenz**: Wer ist zu Hause? Welche Zonen sind belegt?
- **Habitus-Zonen**: Uebersicht aller konfigurierten Raeume
- **Aktive Modi**: Sondermodi wie Kino, Party, Nachtruhe
- **Licht-Intelligenz**: Status der automatischen Lichtsteuerung

### Tab 3: Energie
- **Verbrauch/Erzeugung**: Tageswerte als Gauge-Anzeigen
- **Geraete-Zeitplan**: Optimaler Betriebsplan fuer Grossverbraucher
- **Energiefluss (Sankey)**: Visualisierung der Energiefluesse
- **Anomalie-Warnung**: Erkennung ungewoehnlicher Verbrauchsmuster

### Tab 4: Praesenz
- **Zonen-Praesenz**: Pro-Raum Anwesenheitsanzeige
- **Automatisierungs-Modi**: Statistiken zu belegten Zonen, Lichtern, Musik

### Tab 5: Musik / Musikwolke
- **Musikwolke-Status**: Follow-Modus und aktive Gruppen
- **Sonos-Uebersicht**: Alle Speaker und deren Status
- **Steuerung**: Play/Pause/Dissolve Buttons, Follow Start/Stop
- **Zonen-Automatisierung**: Modi pro Zone (off/learning/autonomy)

### Tab 6+: Zonen-Tabs
- Dynamisch generierte Tabs fuer jede Habitus-Zone
- Praesenz, Beleuchtung, Klima, Medien, Rollladen pro Zone

---

## 3. Musikwolke

Die **Musikwolke** ist PilotSuites Sonos-Multiroom-System:

### Funktionen
- **Gruppen**: Mehrere Zonen spielen synchron die gleiche Musik
- **Follow-Modus**: Musik folgt Ihnen automatisch von Raum zu Raum
- **Lautstaerke**: Pro-Zone-Lautstaerke (0-100%)
- **Auto-Play**: Musik startet automatisch bei Betreten einer Zone (optional)

### Steuerung

**Per Dashboard:**
- Play/Pause/Dissolve Buttons im Musik-Tab
- Follow Start/Stop Buttons

**Per HA Automation:**
```yaml
service: copilot_ha.musikwolke_start_follow
data:
  person_id: person.alice
  source_zone: wohnzimmer
```

**Per Sprachbefehl (Styx Chat):**
- "Spiele Musik im Wohnzimmer"
- "Stoppe die Musik ueberall"
- "Musik leiser im Schlafzimmer"

### Verfuegbare Services

| Service | Funktion |
|---------|----------|
| `copilot_ha.musikwolke_create` | Gruppe erstellen |
| `copilot_ha.musikwolke_dissolve` | Gruppe aufloesen |
| `copilot_ha.musikwolke_play` | Zone abspielen |
| `copilot_ha.musikwolke_pause` | Zone pausieren |
| `copilot_ha.musikwolke_volume` | Lautstaerke setzen |
| `copilot_ha.musikwolke_start_follow` | Follow starten |
| `copilot_ha.musikwolke_stop_follow` | Follow stoppen |

---

## 4. Zone Automation

Jede Habitus-Zone kann in einem von drei Modi betrieben werden:

| Modus | Verhalten |
|-------|-----------|
| **off** | Nur Zustandserfassung, keine automatischen Aktionen |
| **learning** | Zustand + Mustererkennung (KI lernt Ihre Gewohnheiten) |
| **autonomy** | Volle Automatisierung (Licht, Musik, Klima reagieren automatisch) |

### Lichtsteuerung (im Autonomy-Modus)
- Automatisches Ein-/Ausschalten bei Praesenz/Abwesenheit
- Konfigurierbare Verzoegerungen (Presence Delay, Absence Delay)
- Hysterese gegen Flackern bei Wolkendurchzug
- Aussen-Lux-Kompensation

### Musiksteuerung (im Autonomy-Modus)
- Auto-Play bei Zonenbetreten
- Follow-Modus zwischen Zonen
- Konfigurierbare Standard-Lautstaerke
- Automatisches Pausieren bei Abwesenheit

---

## 5. Styx Chat (KI-Assistent)

PilotSuite enthaelt einen lokalen KI-Assistenten (LLM):

- **Modell:** qwen3:0.6b (lokal via Ollama)
- **Sprache:** Deutsch (primaer) + Englisch
- **Integration:** HA Conversation Agent ("Styx Assist")
- **Zugriff:** Dashboard, Styx Chat Tab, HA Assist

### Beispielbefehle
- "Wie ist die Stimmung im Haus?"
- "Schalte das Licht im Bad aus"
- "Zeige mir den Energieverbrauch"
- "Aktiviere den Kino-Modus"

---

## 6. Tag-System

Tags kategorisieren und gruppieren Entities zonenuebergreifend:

- **Zone-Tags**: `area:wohnzimmer`, `area:kueche`
- **Rollen-Tags**: `aicp.role.licht`, `aicp.role.media`, `aicp.role.klima`
- **Funktions-Tags**: `type:ambient`, `type:main_light`
- **Bidirektionale Sync**: Tags werden zwischen HA und Core synchronisiert

---

## 7. Neuronales System

### Brain Graph
- Gerichteter Graph mit 500+ Knoten und 1500+ Kanten
- Bildet Beziehungen zwischen Entities, Events und Zustaenden ab
- Exponentielles Decay fuer Aktualitaet

### Mood Engine
- 6 diskrete Stimmungen (z.B. entspannt, energisch, fokussiert)
- 5 kontinuierliche Dimensionen
- Argmax-Selektion (bewusste Design-Entscheidung)

### Habitus Miner
- Association Rule Mining aus Verhaltensmustern
- Wilson-Confidence fuer robuste Regelauswahl
- Vorschlaege mit Governance-Lifecycle (pending -> offered -> accepted/dismissed)

---

## 8. Energie-Management

- **Verbrauchsanalyse**: Tagesverbrauch, Erzeugung, Netto-Bilanz
- **Geraete-Zeitplan**: Optimierung nach PV-Ertrag und Stromtarif
- **Anomalie-Erkennung**: Automatische Warnung bei ungewoehnlichem Verbrauch
- **Sankey-Diagramm**: Visualisierung der Energiefluesse

---

## 9. Privacy & Sicherheit

- **Kein Cloud-Upload**: Alle Daten bleiben lokal
- **PII-Redaktion**: Persoenliche Informationen werden nicht gespeichert
- **Token-Authentifizierung**: Alle API-Aufrufe erfordern Auth-Token
- **GDPR-konform**: Datenexport und -loeschung per Service
- **Retention-Policies**: Automatisches Loeschen alter Daten

---

## 10. Fehlerbehebung

### Core Add-on nicht erreichbar
1. Status pruefen: `Settings -> Add-ons -> PilotSuite Core`
2. Logs pruefen: Add-on Logs ansehen
3. Port pruefen: `http://homeassistant.local:8909/health`

### Dashboard leer
1. YAML-Pfad pruefen in `configuration.yaml`
2. HA neu starten
3. Cache leeren (Browser)

### Musikwolke reagiert nicht
1. Sonos-Speaker eingeschaltet und im Netzwerk?
2. node-sonos-http-api (jishi) laeuft auf Port 5005?
3. Zone-Speaker-Mapping korrekt konfiguriert?

### Debug-Modus
```yaml
service: copilot_ha.enable_debug
data:
  log_level: "DEBUG"
```

---

**PilotSuite Styx** -- Ihr lokaler KI-Copilot fuer das Smart Home.
