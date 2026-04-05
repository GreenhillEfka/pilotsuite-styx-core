# Backend-UI Design: Zone-Override States & Flows

**Status:** Finalized (2026-04-05)
**Owner:** DesignClaw
**Core-Worktree:** pilotsuite-styx-core-current

## 1. Kanonische State-Repräsentation
Jede Zone/Modul-Kombination wird im Backend-UI (Read-Model) über genau vier Felder repräsentiert, die aus der `ModuleRegistry` abgeleitet werden.

| Feld | Typ | Beschreibung |
| :--- | :--- | :--- |
| `state` | `string` | Der aktuell effektive Zustand (`active`, `learning`, `off`). |
| `global_state` | `string` | Der systemweite Standardwert (globaler Modus). |
| `override_state` | `string|null` | Der explizit für diese Zone gesetzte Override-Wert. |
| `has_override` | `boolean` | Flag, ob ein manueller Eingriff vorliegt. |

## 2. UX-Zustandsmatrix

### Fall A: Erbt Global (Default)
- **Daten:** `has_override: false`, `override_state: null`, `state == global_state`.
- **UI:** Neutrale Anzeige des Zustands.
- **CTA:** „Manuell ändern“ (öffnet Auswahl für `active`, `learning`, `off`).

### Fall B: Aktiver Override (Abweichung)
- **Daten:** `has_override: true`, `override_state != global_state`.
- **UI:** Visuelles Badge/Tag am Zustand (z.B. „Manual Override“).
- **CTA:** „Zurück auf Global“ (setzt `state` wieder auf `global_state`).

### Fall C: Explizite Übereinstimmung (Normalisierung)
- **Daten:** `has_override: true`, `override_state == global_state`.
- **UI:** Wie Fall A, ggf. mit dezentem Hinweis auf explizite Fixierung.
- **CTA:** „Override löschen“ (setzt `has_override` auf `false`).

## 3. API-Flows (Backend-UI to Core)

### Override setzen / ändern
- **Endpoint:** `POST /api/v1/backend/zones/<zone_id>/modules`
- **Payload:** `{"module_id": "...", "state": "active|learning|off"}`
- **Logik:** Wenn `state != global_state`, wird ein persistenter Override in der Registry erzeugt.

### Zurück auf Global (Reset)
- **Endpoint:** `POST /api/v1/backend/zones/<zone_id>/modules`
- **Payload:** `{"module_id": "...", "state": "<global_state_value>"}`
- **Logik:** Die Core-Registry erkennt die Übereinstimmung mit dem globalen State und löscht den Zone-Override automatisch (deterministisches Reset-Verhalten).

## 4. Abgrenzung
- **Automation-Flags:** `light_enabled`, `music_enabled` etc. aus `zone_automation.py` sind **binäre Funktionsschalter** und keine Modus-Overrides. Sie werden separat im UI als einfache Toggles dargestellt.
- **Read-Only Status:** Felder wie `any_override` (Licht) dienen nur der aggregierten Anzeige in der Zonenliste, steuern aber nicht den Override-Flow selbst.

## 5. Success Signal für Implementierung (Slice 125)
- Das Backend-UI konsumiert das 4er-State-Modell.
- Der Reset-Flow („Back to Global“) nutzt den POST-Weg mit dem globalen Wert.
- Keine redundante Logik für "Override löschen" nötig.
