# CORE_ARCH_RESTRUCTURE_PLAN_2026-03-28

## Binding product decision

Ab diesem Stand gilt für PilotSuite:

- **Keine weitere Produktentwicklung in HA/HACS als eigene Feature-Lane**
- **Home Assistant ist nur noch Sensorium / Datenquelle / Ausführungsumfeld**
- **PilotSuite Core besitzt die fachliche Wahrheit, Konfiguration, UI, Zuordnung, Policy, Visualisierung und neuronale Nutzung**

Das bedeutet: Zonen, Entity-Zuordnung, Tags, Modul-Konfiguration, Neuronen-Eingänge, Read-Models und Dashboard-Sichten werden **im Core** definiert und verwaltet.

---

## 1. Zielarchitektur

```text
Home Assistant
  └─ liefert via Token + Core-HA-Modul:
     - Areas
     - Entities
     - States
     - Devices / Registry-Metadaten
     - Services / Capabilities

PilotSuite Core
  ├─ HA Input Layer
  │  ├─ /api/v1/ha/connect
  │  ├─ /api/v1/ha/status
  │  ├─ /api/v1/ha/areas
  │  └─ /api/v1/ha/entities
  │
  ├─ Canonical Zone Configuration Layer
  │  ├─ zone metadata
  │  ├─ entity assignments
  │  ├─ tag bindings
  │  ├─ enabled modules
  │  └─ neuron input declarations
  │
  ├─ Runtime / Truth Layer
  │  ├─ HabitusZoneEngine
  │  ├─ ZoneAutomationController
  │  ├─ TagZoneIntegration
  │  └─ module + neuron orchestration
  │
  ├─ Read Models
  │  ├─ zonenkonfiguration view model
  │  ├─ habituszonen detail view model
  │  ├─ neuron/module graph view model
  │  └─ dashboard summary view model
  │
  └─ Core UI
     ├─ Zonenkonfiguration
     ├─ Habituszonen
     ├─ Module
     ├─ Neuronen/Synapsen
     └─ System / HA connection status
```

---

## 2. Truth boundaries

### Home Assistant responsibilities
Nur noch:
- Authentifizierte Quelle für Entities, Areas, States und Runtime-Signale
- Technische Ausführungsebene für Geräte/Services
- Optionaler Rückkanal für Actions/Webhooks

### Core responsibilities
Verbindlich im Core:
- Habituszonen anlegen/ändern/löschen
- Zuordnung von Entities zu Zonen
- Tag-basierte Semantik (`aicp.place.*`, `aicp.kind.*`, `aicp.role.*`, `aicp.state.*`)
- Modul-Aktivierung pro Zone
- Zuordnung von Entities zu Neuronen-Inputs
- Abgeleitete Read-Models und Visualisierung
- Governance, Policy, Actionability

### Anti-goal
Nicht mehr Ziel:
- Feature-Ownership in HACS/UI der HA-Integration
- doppelte Konfigurationswahrheit zwischen HA und Core
- zone/business logic in HA-spezifischen Flows verteilen

---

## 3. Bestehende Bausteine, die weiterverwendet werden

### Bereits vorhanden
- `copilot_core/homeassistant/api.py`
  - Token-basierte Verbindung zu HA
  - Areas / Entities / Status abrufbar
- `copilot_core/api/v1/tag_system.py`
  - Tag-Registry + Assignment Store
- `copilot_core/tagging/zone_integration.py`
  - place-tags erzeugen Zonenkontext
- `copilot_core/api/v1/zone_editor.py`
  - CRUD-nahe Zone-Editor-Oberfläche auf `HabitusZoneEngine`
- `copilot_core/api/v1/zone_automation.py`
  - Runtime-/Config-/Entity-Endpoints für Zonen
- `copilot_core/hub/zone_automation.py`
  - ZoneAutomationConfig + Entities + Runtime State
- `copilot_core/hub/habitus_zones.py`
  - HabitusZone truth engine
- `dashboard/*` und `api/v1/dashboard*`
  - aktuelle UI/Visualisierungsbasis, teils statisch/legacy

### Architektonischer Befund
Das Repo hat bereits fast alle richtigen Bauteile, aber sie liegen noch in **mehreren parallelen Schnittbildern**:
- `zone_editor` → Zone-CRUD / topology-orientiert
- `zone_automation` → Runtime-/Config-Sicht
- `tag_system` → Semantik / Zuordnung
- `dashboard` → Visualisierung, teils noch statisch

Die Restrukturierung soll diese vier Stränge unter einem **Core-owned Zonenkonfigurationsmodell** zusammenziehen.

---

## 4. Kanonisches Datenmodell

## 4.1 ZoneDefinition (authoritative)
```json
{
  "zone_id": "wohnzimmer",
  "zone_name": "Wohnzimmer",
  "zone_type": "living",
  "enabled": true,
  "enabled_modules": ["light", "presence", "climate", "media"],
  "entity_assignments": [
    {
      "entity_id": "light.wohnzimmer_decke",
      "role": "lights",
      "tags": ["aicp.place.wohnzimmer", "aicp.kind.light"],
      "source": "core_manual"
    }
  ],
  "neuron_inputs": [
    {
      "neuron_id": "presence.primary",
      "entity_ids": ["binary_sensor.wohnzimmer_presence"]
    }
  ],
  "governance": {
    "requires_confirmation": true,
    "safety_critical_entities": []
  }
}
```

## 4.2 EntityAssignment
Pflichtfelder:
- `entity_id`
- `zone_id`
- `role`
- `tags[]`
- `source`

Optional:
- `display_name`
- `capabilities`
- `neuron_bindings[]`
- `module_bindings[]`

## 4.3 Tag binding model
- Entity bleibt Primärsubjekt im Tag-System
- Zone-Mitgliedschaft wird semantisch über `aicp.place.<zone>` beschrieben
- Core erzeugt/verwaltet diese Bindung aus der Zonenkonfiguration heraus
- `TagZoneIntegration` materialisiert daraus Zonenkontext

## 4.4 Neuron feed declaration
Jede Zone braucht deklarative Eingänge:
- `presence.primary`
- `presence.secondary`
- `ambient.light`
- `ambient.temperature`
- `ambient.humidity`
- `media.activity`
- `manual.override`

Nicht jede Zone muss alle Inputs besitzen, aber die UI muss sichtbar machen:
- vorhanden
- optional
- fehlt
- aus Tags ableitbar

## 4.5 Read models
Abgeleitete Modelle statt UI-Direktzugriff auf Rohstrukturen:
- `ZoneConfigurationReadModel`
- `HabitusZoneDetailReadModel`
- `ZoneNeuronMapReadModel`
- `ZoneModuleStatusReadModel`
- `SystemHAConnectionReadModel`

---

## 5. API-Konsolidierung: Ist → Soll

## 5.1 HA input layer (bleibt, aber nur als Input)
Bestehend:
- `GET /api/v1/ha/status`
- `GET /api/v1/ha/areas`
- `GET /api/v1/ha/entities`

Ziel:
- Beibehalten, aber nur als **Source APIs** behandeln
- Keine produktlogische Zonenkonfiguration mehr in HA-Flows

## 5.2 Zone configuration layer (neue Primär-API)
Ziel-Endpunkte:
- `GET /api/v1/zones/config`
- `POST /api/v1/zones/config`
- `GET /api/v1/zones/config/<zone_id>`
- `PUT /api/v1/zones/config/<zone_id>`
- `DELETE /api/v1/zones/config/<zone_id>`
- `POST /api/v1/zones/config/<zone_id>/entities`
- `DELETE /api/v1/zones/config/<zone_id>/entities/<entity_id>`
- `POST /api/v1/zones/config/<zone_id>/tags/sync`
- `POST /api/v1/zones/config/<zone_id>/neurons/bind`

Kurzfristig kann `zone_automation` diese Rolle teilweise übernehmen; mittelfristig soll eine klar benannte Config-API entstehen.

## 5.3 Runtime layer
Bestehend:
- `GET /api/v1/zone-automation/dashboard`
- `GET /api/v1/zone-automation/zones/<zone_id>`
- `POST /api/v1/zone-automation/zones/<zone_id>/config`
- `POST /api/v1/zone-automation/sync`
- `POST /api/v1/zone-automation/sync-definitions`

Ziel:
- Runtime bleibt separat von CRUD
- `zone_automation` wird zur Runtime-/execution-view der zonalen Wahrheit
- keine langfristige Vermischung von CRUD und Runtime außerhalb eines klaren Contracts

## 5.4 Legacy/transition
- `zone_editor` bleibt Übergangslayer für vorhandene Dashboard-Funktionen
- `dashboard/api/v1/dashboard.py` mit statischer Default-Zonenbasis wird **auslaufend** behandelt
- Legacy-Routen werden dokumentiert, aber nicht weiter ausgebaut

---

## 6. Sofort nutzbare Restrukturierungsrichtung im bestehenden Code

## 6.1 Kurzfristig (safe scaffolding)
Direkt anschlussfähig:
- `zone_automation` für Core-owned Zonenliste + Zonenerstellung erweitern
- `set_zone_config()` für `zone_type`, `enabled_modules`, `ha_entities` erweitern
- HA-Entity-Liste in Zonenkonfiguration konsumieren statt in statischen Dashboards
- Tag-System als kanonische Semantik an Zone-Assignment koppeln

## 6.2 Mittelfristig
- dedizierten `zone_config` service einführen
- ZoneDefinition persistent speichern
- Read-model builder für Zonenkonfiguration + Habituszonen-Detail extrahieren
- UI nicht mehr auf `DEFAULT_ZONES_CONFIG` oder statische Mock-Strukturen stützen

## 6.3 Langfristig
- neuron/module topology direkt aus ZoneDefinition ableiten
- module dashboards vollständig aus read models speisen
- HA nur noch als Adapter und event ingress behandeln

---

## 7. Phasenplan

## Phase 1 — Truth reset (jetzt)
Ziel:
- Core-only Richtungsentscheidung im Code und in Docs widerspiegeln
- minimale CRUD-Scaffolds für Core-owned zones schaffen

Akzeptanzkriterien:
- Core kann Zone-Configs selbst anlegen/listen
- Zone-Config kann `zone_name`, `zone_type`, `enabled_modules`, `ha_entities` tragen
- Architektur- und UI-Plan dokumentiert

## Phase 2 — Canonical zone configuration
Ziel:
- ZoneDefinition als persistente, eindeutige Wahrheit einführen
- `zone_editor`, `zone_automation`, `tag_system` auf dieselbe Quelle ausrichten

Akzeptanzkriterien:
- ein persistentes ZoneDefinition-Store-Modell
- jede UI-Aktion schreibt in dieselbe Konfigurationswahrheit
- place-tags werden aus ZoneAssignments synchronisiert

## Phase 3 — Entity + tag + neuron binding
Ziel:
- HA-Entities im Core browsen, taggen und Zonen/Neuronen zuordnen

Akzeptanzkriterien:
- verfügbare HA-Entities in Core sichtbar
- pro Zone Entity-Zuordnung bearbeitbar
- neuron input bindings sichtbar und speicherbar
- TagZoneIntegration aktualisiert die Zone-Mitgliedschaft deterministisch

## Phase 4 — Core UI migration
Ziel:
- neue Tabs `Zonenkonfiguration` und `Habituszonen`
- statische Dashboard-Surfaces zurückdrängen

Akzeptanzkriterien:
- keine produktive Abhängigkeit mehr von `DEFAULT_ZONES_CONFIG`
- Habituszonen-Ansicht basiert auf Read-Models
- Modul-/Neuronstatus pro Zone sichtbar

## Phase 5 — Consolidation + deprecation
Ziel:
- HA/HACS Feature-Lane offiziell stilllegen
- Legacy API/Views nur noch als Compatibility Surface halten

Akzeptanzkriterien:
- Deprecation-Hinweise in Docs
- keine neue Business-Logik mehr in HA-Integration
- Core owns the product surface end-to-end

---

## 8. Deprecation note: HA/HACS feature lane

Ab dieser Restrukturierung gilt:
- **Neue Funktionen werden nicht mehr in der HA/HACS Integration entwickelt**
- HA-seitige Arbeit beschränkt sich auf Stabilität, Datenbereitstellung und Ausführung
- Fachliche Weiterentwicklung, UX, Zonenmodell, Tag-/Neuron-Zuordnung und Visualisierung entstehen ausschließlich im Core

---

## 9. Recommended next code steps

1. `zone_automation` als Übergangs-CRUD für Core-owned zone creation/listing stabilisieren
2. dediziertes `zone_config_store` Modul ergänzen
3. `tag_system` um Zone-Workflow-Helfer erweitern (Entity → place-tag → zone membership)
4. `dashboard` von statischen Zonenkonstanten auf Read-Models umstellen
5. neue Core-UI-Reiter auf denselben Contracts aufbauen
