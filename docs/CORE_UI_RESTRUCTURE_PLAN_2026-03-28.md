# CORE_UI_RESTRUCTURE_PLAN_2026-03-28

## Produktentscheid
Die Core-Oberfläche wird zur einzigen produktiven Bedienoberfläche für:
- Habituszonen
- Zonenkonfiguration
- Entity-Zuordnung
- Tagging
- Modul- und Neuronen-Verknüpfung
- Visualisierung des Systemzustands

Home Assistant ist in der UI nur noch als **angeschlossene Quelle** sichtbar, nicht mehr als primäre Konfigurationsoberfläche.

---

## 1. Ziel-Informationsarchitektur

## Hauptnavigation
1. **Übersicht**
2. **Zonenkonfiguration**
3. **Habituszonen**
4. **Module**
5. **Neuronen & Synapsen**
6. **Home Assistant Quelle**
7. **System / Diagnose**

---

## 2. Reiter: Zonenkonfiguration

Dieser Reiter ist die neue Arbeitsoberfläche für das Bauen der Core-Wahrheit.

## 2.1 Layout
Linke Spalte:
- Zonenliste
- Filter nach Typ, aktiv/inaktiv, Modulstatus, Vollständigkeit
- Button **„Neue Habituszone“**

Mitte:
- Zone-Formular
- Basisdaten (`zone_name`, `zone_id`, `zone_type`, Aktivstatus)
- aktivierte Module
- Governance / Sicherheitsregeln

Rechte Spalte:
- verfügbare HA-Entities
- Suchfeld
- Filter nach Domain, Area, Gerät, Tag, Status
- Vorschläge für Tagging und Rollen

Unterer Bereich:
- Zuordnungsboard
- Zugeordnete Entities nach Rollen gruppiert
- Neuron-Eingänge
- Modul-Bindings

## 2.2 Primäre Aktionen
- Zone erstellen
- Zone duplizieren
- Zone archivieren/löschen
- HA-Entities suchen/importieren
- Entity per Klick/Drag einer Zone zuordnen
- Tags vergeben/entfernen
- Entity als Neuron-Eingang markieren
- Modul-Set pro Zone aktivieren

---

## 3. Reiter: Habituszonen

Dieser Reiter ist **nicht** für Konfiguration, sondern für Darstellung und Verstehen des laufenden Systems.

## 3.1 Karten/Listenansicht
Pro Zone sichtbar:
- Name, Typ, Icon
- Modulstatus
- Anzahl zugeordneter Entities
- belegte Neuron-Eingänge
- aktuelle Aktivität / State
- kritische Warnungen / Lücken

## 3.2 Detailansicht einer Zone
Sektionen:
1. **Zusammenfassung**
   - Zone-Typ
   - Aktivstatus
   - letzte Änderungen
2. **Entity-Landkarte**
   - Lichter
   - Sensoren
   - Präsenzquellen
   - Medien
   - Klima
3. **Neuronen-Eingänge**
   - welche Entities speisen welche Inputs
   - fehlende Inputs klar markieren
4. **Module**
   - aktivierte Module
   - relevante Konfigurationswerte
5. **Runtime / Read Model**
   - Occupancy
   - Lichtstatus
   - Medienstatus
   - Stimmungen / Mood / Automationszustand
6. **Aktionen / Vorschläge**
   - Inkonsistenzen beheben
   - Tags synchronisieren
   - fehlende Zuordnung ergänzen

---

## 4. UX-Flows

## 4.1 Flow: Neue Habituszone anlegen
1. Nutzer klickt **„Neue Habituszone“**
2. Dialog fragt:
   - Anzeigename
   - Zone-Typ
   - optionale Vorlagenbasis
3. Core generiert `zone_id`
4. Zone erscheint sofort in Zonenliste
5. UI springt in Bearbeitungsmodus der neuen Zone

Erfolgskriterium:
- keine HA-seitige Vorbedingung nötig
- Zone entsteht vollständig im Core

## 4.2 Flow: Verfügbare HA-Entities holen
1. Nutzer öffnet Zone oder globale Entity-Seitenleiste
2. Core lädt Entities über das HA-Modul (`/api/v1/ha/entities`)
3. UI zeigt Domains, Areas, Friendly Names, verfügbare Attribute
4. Core schlägt Tags / Rollen vor

Erfolgskriterium:
- HA ist in der UX als Quelle sichtbar, nicht als Owner

## 4.3 Flow: Entities einer Zone zuordnen
1. Nutzer filtert verfügbare Entities
2. Nutzer fügt Entity einer Zone hinzu
3. UI verlangt oder schlägt vor:
   - Rolle
   - Tags
   - Modulbindung
   - optional neuron input binding
4. Speichern aktualisiert:
   - ZoneDefinition
   - EntityAssignments
   - place-tags / zone semantics
   - Read-Models

## 4.4 Flow: Tags vergeben / Zonenkontext synchronisieren
1. Nutzer öffnet Entity-Detail
2. UI zeigt bestehende Tags
3. Nutzer ergänzt z. B.:
   - `aicp.place.wohnzimmer`
   - `aicp.kind.light`
   - `aicp.role.primary`
4. Core synchronisiert Tag-System und Zonenmitgliedschaft
5. Habituszonen-Ansicht aktualisiert sich ohne Kontextbruch

## 4.5 Flow: Entity zu Neuron / Modul binden
1. UI zeigt für eine Entity „als Input verwenden“
2. Nutzer wählt:
   - Präsenz
   - Lux
   - Temperatur
   - Medienaktivität
   - manueller Override
3. UI zeigt, welchem Neuron/Modul die Entity nun dient
4. Fehlende Pflichtinputs bleiben sichtbar

## 4.6 Flow: Habituszone betrachten
1. Nutzer wechselt in Reiter **Habituszonen**
2. Wählt Zone
3. Sieht laufende Read-Models, Module, Neuron-Einspeisung, offene Lücken
4. Kann gezielt zurück in die Zonenkonfiguration springen

---

## 5. Mapping bestehender Oberflächen → Zielbild

## 5.1 Aktuelles `dashboard/api/v1/dashboard.py`
Aktueller Zustand:
- stark statische `DEFAULT_ZONES_CONFIG`
- demo-/placeholder-lastig
- nicht kanonische Zonenquelle

Ziel:
- nur noch Übergangsschicht
- durch read-model-basierte Zonenkonfiguration und Habituszonen-Sichten ersetzen

## 5.2 `zone_editor`
Aktueller Zustand:
- brauchbare CRUD-nahe Zone-API
- eng am HabitusZoneEngine-Modell

Ziel:
- fachlich in `Zonenkonfiguration` absorbieren
- UI-seitig Basis für Zone-Liste, Detail und CRUD

## 5.3 `zone_automation`
Aktueller Zustand:
- Runtime- und Config-Mischung
- gute Basis für Entity-Zuordnung und Zonenzustand

Ziel:
- Runtime-Sicht beibehalten
- kurzfristig für Zone-Scaffold nutzbar
- mittelfristig klar von Config-CRUD trennen

## 5.4 `tag_system`
Aktueller Zustand:
- gute semantische Grundlage
- Assignments + Registry vorhanden

Ziel:
- in der UI als Tagging-Panel und Automationslogik sichtbar machen
- place-tags deterministisch aus Zonenkonfiguration erzeugen/synchronisieren

## 5.5 `homeassistant/api.py`
Aktueller Zustand:
- Connect / Areas / Entities / Status vorhanden

Ziel:
- dedizierte Quelle im Reiter **Home Assistant Quelle**
- dort: Verbindung, Pull-Status, letzte Synchronisation, importierbare Entities

---

## 6. Screen-Struktur im Detail

## 6.1 Übersicht
Kompakte Startseite mit:
- Anzahl Zonen
- Anzahl angebundener HA-Entities
- unzugeordnete Entities
- fehlende Neuron-Inputs
- Modul-/Verbindungsstatus

## 6.2 Zonenkonfiguration – Hauptscreen
Tabs im Detailpanel:
- **Allgemein**
- **Entities**
- **Tags**
- **Neuronen**
- **Module**
- **Governance**

## 6.3 Habituszonen – Detailscreen
Untertabs:
- **Status**
- **Entity-Landkarte**
- **Neuronenfluss**
- **Module**
- **Historie / Ereignisse**

## 6.4 Home Assistant Quelle
Anzeigen:
- verbunden / nicht verbunden
- Basis-URL
- letzte erfolgreiche Aktualisierung
- Anzahl Areas
- Anzahl Entities
- Filterbare Entity-Liste
- Import-/Refresh-Action

---

## 7. Design-Prinzipien

1. **Core first**
   - jeder Screen repräsentiert Core-Wahrheit, nicht HA-Schattenkonfiguration
2. **Konfiguration getrennt von Runtime**
   - Bearbeiten in `Zonenkonfiguration`
   - Beobachten in `Habituszonen`
3. **Semantik sichtbar machen**
   - Tags, Rollen, Modulbindung, Neuronenbindung nicht verstecken
4. **Lücken sichtbar machen**
   - ungebundene Entities, fehlende Inputs, inkonsistente Tags markieren
5. **Read-model driven UI**
   - Screens konsumieren verdichtete Modelle, nicht rohe Einzelspeicher

---

## 8. Migrationsnotizen

## Schritt 1 — statische Dashboard-Annahmen entkoppeln
- `DEFAULT_ZONES_CONFIG` nicht weiter ausbauen
- neue Screens nicht auf statischen Zonendefinitionen aufbauen

## Schritt 2 — Zonenkonfigurations-Read-Model einführen
- Zonenliste, Zone-Detail und Entity-Zuordnung aus kanonischer Quelle erzeugen

## Schritt 3 — HA-Entity-Browser integrieren
- importierbare Entities aus Core-HA-Modul
- kein UI-Umweg mehr über HA-Konfiguration

## Schritt 4 — Tagging- und Neuron-Panel anschließen
- Tag-Assignments sichtbar und editierbar
- neuronale Nutzung der Entities transparent

## Schritt 5 — Habituszonen-Ansicht auf Read Models umstellen
- Runtime-/Status-Screen entkoppelt von Mock-/Legacy-Strukturen

---

## 9. Rollout-Reihenfolge

### Wave A — Foundations
- Zone create/list/edit im Core stabil
- HA-Entities im Core abrufbar
- erste `Zonenkonfiguration`-Ansicht

### Wave B — Semantic assignment
- Entity assignment panel
- Tagging panel
- place-tag Synchronisation
- Modul- und Neuron-Bindings

### Wave C — Visualization
- Habituszonen-Detailansicht
- Neuronen-/Modulübersicht pro Zone
- State/Read-Model-Karten

### Wave D — Cleanup
- statische Dashboard-Surfaces zurückbauen
- Legacy-Views als Compatibility markieren

---

## 10. Definition of done für die UI-Restrukturierung

Die Restrukturierung gilt erst als abgeschlossen, wenn:
- Zonen vollständig im Core angelegt und gepflegt werden können
- verfügbare HA-Entities im Core sichtbar und zuordenbar sind
- Tags, Rollen, Module und Neuronen-Bindings pro Entity editierbar sind
- Habituszonen als Ergebnis dieser Konfiguration separat visualisiert werden
- keine produktiv notwendige Konfiguration mehr in der HA/HACS-Lane stattfindet
