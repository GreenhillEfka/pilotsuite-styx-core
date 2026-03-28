# Core State-of-the-Art Restrukturierung (Autonomes Vorgehen ab 2026-03-28)

> Status: In Arbeit — **Scope auf Core-only** aktiviert (keine neue Feature-Entwicklung im HA/HACS-Repo)

## Zielbild
- Gesamtfunktionen aus bisherigen HA+Core-Läufen vollständig in Core verdichten.
- Neue Kern-Nutzung für Habituszonen:
  - Reiter **Zonenkonfiguration**: Zonen anlegen, Entitäten via HA-Discovery zuordnen, Persistenz/Schema
  - Reiter **Habituszonen**: bestehende/aktive Zonen visualisieren und Module als Inputs pro Zone konsumierbar machen
- Vertragstreue: Core bleibt Truth-Layer, HA nur Token-basierte Datenquelle/Contract-Layer.

## Durchlauf (autonom, ohne manuelle Zwischenfragen)

### Phase A — Architektur-/Vertrags-Freeze
1. HA-Herstellerwechsel auf `core-only`: keine neuen Feature-PRs im HA/HACS-Repo.
2. Verträge validieren: `homeassistant`-Tokenschnittstellen (`/api/v1/ha/areas`, `/api/v1/ha/entities`) bleiben einziges Importfenster.
3. Zonen-Single-Source auf Core bestätigen (`habitus_zones` + Zone-Editor/Sync APIs).

### Phase B — Datenmodell & Konnektoren konsolidieren
1. Zone- und Raummodell (Core) als `core_truth` finalisieren.
2. Mapping-Pfade klar trennen:
   - Discovery aus HA in Zone-Engine
   - Tagging/zuordnung in Core-Zonenstruktur
   - Modulzugriff ausschließlich über Zonen-Contract.
3. Bestehende Legacy-Funktionen auf Kompatibilität prüfen (`zone_editor`, `habitus_zones`, `zone_dashboard`).

### Phase C — UI/UX (Core Dashboard)
1. Reiter **Zonenkonfiguration**:
   - create/update/delete zone
   - Entitätsauswahl aus `/api/v1/ha/entities`
   - Tag-basierte Klassifikation/Filter
2. Reiter **Habituszonen**:
   - Live-Ansicht bestehender Zonen inkl. Entitäten, Modulinhalte, Health/Status.
3. API-Konsistenz zwischen Dashboard-Calls und Core-Services absichern.

### Phase D — Stabilität und Release-Readiness (paired only)
1. Unit-/Integration-Tests für Zone-Editor + Dashboard-Readmodel + Tags/HA-Discovery.
2. Paired-Release-Claim nur nach Verifizierungs-Paket:
   - Laufzeitbeleg aus Core/API
   - keine offenen Merge-Drifts auf HA-Featureseite.
3. Handover-Artifact inkl. Repo-Status, Endpoint-Tabelle, Runtime-Checkliste.

## Nächste harte Kriterien (DoD für Phase B/C)
- `/api/v1/zone-editor/*` liefert konsistente Zonenobjekte mit Quellen-/Persistenzbezug.
- `/api/v1/ha/entities` liefert mindestens den Entitätspool für Konfiguration.
- Core Dashboard zeigt beide neuen Reiter und kann mindestens lesen/schreiben.
- Kein neues HA/HACS-Feature außerhalb Contract/Runtime-Fix auf dem Tisch.