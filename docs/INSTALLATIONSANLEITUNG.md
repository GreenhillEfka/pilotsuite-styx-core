# PilotSuite Styx — Installationsanleitung

**Version:** 13.7.0
**Datum:** 2026-03-11
**Zielgruppe:** Endanwender und Integratoren

---

## Voraussetzungen

| Komponente | Mindestanforderung |
|------------|-------------------|
| Home Assistant | Version 2024.1.0 oder neuer |
| Hardware | 2 GB RAM, 2 CPU Cores (empfohlen: 4 GB RAM) |
| Netzwerk | Lokales Netzwerk, kein Internet erforderlich |
| Optional: Sonos | node-sonos-http-api (jishi) auf Port 5005 |

---

## Schritt 1: PilotSuite Core Add-on installieren

### 1.1 Repository hinzufuegen

1. Home Assistant oeffnen
2. `Settings` -> `Add-ons` -> `Add-on Store` (unten rechts: drei Punkte)
3. `Repositories` -> Repository-URL hinzufuegen:
   ```
   https://github.com/GreenhillEfka/pilotsuite-styx-core
   ```
4. `Add` klicken

### 1.2 Add-on installieren

1. In der Add-on-Liste: `PilotSuite Core` suchen
2. `Install` klicken
3. Warten bis die Installation abgeschlossen ist

### 1.3 Add-on konfigurieren

Unter `Configuration`:

```yaml
log_level: info
auth_token: ""                              # Optional: Sicherheitstoken
conversation_ollama_model: "qwen3:0.6b"     # LLM-Modell (Standard)
conversation_enabled: true
searxng_enabled: false                      # Nur wenn SearXNG verfuegbar
```

### 1.4 Add-on starten

1. `Start` klicken
2. Warten bis der Status `running` zeigt (kann beim ersten Start 2-5 Minuten dauern wegen Ollama Model-Download)
3. Health-Check: `http://homeassistant.local:8909/health` muss `{"ok": true}` zeigen

---

## Schritt 2: PilotSuite HA Integration installieren

### 2.1 HACS Repository hinzufuegen

1. `HACS` -> `Integrations` -> drei Punkte -> `Custom Repositories`
2. Repository-URL:
   ```
   https://github.com/GreenhillEfka/pilotsuite-styx-ha
   ```
3. Kategorie: `Integration`
4. `Add` klicken

### 2.2 Integration installieren

1. `HACS` -> `Integrations` -> `PilotSuite` suchen
2. `Download` klicken
3. Home Assistant neu starten

### 2.3 Integration konfigurieren

1. `Settings` -> `Devices & Services` -> `Add Integration`
2. `PilotSuite` suchen und auswaehlen
3. Config-Wizard durchlaufen:
   - **Discovery**: Core Add-on wird automatisch erkannt
   - **Zones**: Habitus-Zonen anlegen (z.B. Wohnzimmer, Kueche, Schlafzimmer)
   - **Entities**: Entities den Zonen zuweisen
   - **Features**: Gewuenschte Features aktivieren
   - **Network**: Verbindungseinstellungen pruefen
   - **Review**: Zusammenfassung und Bestaetigung

---

## Schritt 3: Dashboard einrichten

### 3.1 Dashboard-YAML in configuration.yaml

```yaml
lovelace:
  dashboards:
    copilot-pilotsuite:
      mode: yaml
      title: "PilotSuite - Styx"
      icon: mdi:robot-outline
      show_in_sidebar: true
      filename: "pilotsuite-styx/pilotsuite_dashboard_latest.yaml"
    copilot-habitus-zones:
      mode: yaml
      title: "PilotSuite - Habitus Zones"
      icon: mdi:layers-outline
      show_in_sidebar: true
      filename: "pilotsuite-styx/habitus_zones_dashboard_latest.yaml"
```

### 3.2 Home Assistant neu starten

Nach dem Neustart erscheinen die PilotSuite-Dashboards in der Sidebar.

---

## Schritt 4: Musikwolke einrichten (optional)

### 4.1 Voraussetzung: node-sonos-http-api

Die Musikwolke benoetigt den [node-sonos-http-api](https://github.com/jishi/node-sonos-http-api) Service:

```bash
# Docker:
docker run -d --name sonos-api --network=host jishi/node-sonos-http-api

# Oder als npm-Paket:
npm install -g sonos-http-api
sonos-http-api
```

Pruefung: `http://homeassistant.local:5005/zones` muss Sonos-Zonen zeigen.

### 4.2 Zone-Speaker-Mapping

Die Musikwolke ordnet PilotSuite-Zonen automatisch Sonos-Raeumen zu. Bei Bedarf manuell anpassen ueber:

```yaml
service: copilot_ha.media_context_v2_suggest_zone_mapping
data:
  entry_id: <config_entry_id>
```

---

## Schritt 5: Verifizierung

### 5.1 Smoke-Test Checkliste

- [ ] Core Add-on Status: `running`
- [ ] Health-Check: `http://homeassistant.local:8909/health` -> `{"ok": true}`
- [ ] Integration geladen: `Settings -> Devices & Services -> PilotSuite` zeigt Geraete
- [ ] Dashboard sichtbar: Styx-Tab in der Sidebar
- [ ] Sensoren aktiv: `sensor.copilot_ha_mood` hat einen Wert
- [ ] Chat funktioniert: Testnachricht im Styx-Chat senden

### 5.2 Ops Runbook

```yaml
# Automatischer Smoke-Test
service: copilot_ha.ops_runbook_smoke_test
```

---

## Fehlerbehebung

### Core Add-on startet nicht

1. Logs pruefen: `Settings -> Add-ons -> PilotSuite Core -> Log`
2. Port-Konflikt? Port 8909 muss frei sein
3. RAM? Mindestens 2 GB frei

### Integration findet Core nicht

1. Core Add-on laeuft?
2. Host-Erkennung pruefen: `homeassistant.local`, `localhost`, `host.docker.internal`
3. Token-Konfiguration stimmt? (Beide Seiten muessen gleichen Token verwenden)

### Dashboard zeigt "unavailable"

1. Core API erreichbar? `http://homeassistant.local:8909/health`
2. HA neu starten
3. Integration reload: `Settings -> Devices & Services -> PilotSuite -> ... -> Reload`

### Musikwolke funktioniert nicht

1. node-sonos-http-api laeuft? `http://homeassistant.local:5005/zones`
2. Sonos-Speaker im gleichen Netzwerk?
3. Zone-Mapping korrekt? `copilot_ha.media_context_v2_suggest_zone_mapping` ausfuehren

---

## Aktualisierung

### HACS-Update (empfohlen)

1. `HACS` -> `Integrations` -> `PilotSuite` -> `Update`
2. Home Assistant neu starten

### Core Add-on Update

1. `Settings` -> `Add-ons` -> `PilotSuite Core` -> `Update`
2. Add-on neu starten

### Versionsabgleich

**Wichtig:** Core und HA muessen immer die gleiche Version haben!

Aktuelle Version pruefen:
- HA: `Settings -> Devices & Services -> PilotSuite` (Version in Info)
- Core: `http://homeassistant.local:8909/version`

---

## Kontakt & Support

- **Issues:** https://github.com/GreenhillEfka/pilotsuite-styx-ha/issues
- **Core Issues:** https://github.com/GreenhillEfka/pilotsuite-styx-core/issues

---

**PilotSuite Styx** -- Ihr lokaler KI-Copilot fuer das Smart Home.
