# PilotSuite Styx Self-Repair (v1)

## Zielbild
Styx soll bei Teil-Ausfaellen (Integritaet `degraded`) nicht nur warnen, sondern reproduzierbar analysieren, priorisieren und sichere Reparaturplaene liefern.

## v1 (jetzt implementiert)
- API: `/api/v1/self-repair/*`
- Integritaets-Snapshot aus `/api/v1/system/overview` (Score + Statusfarbe: green/orange/red)
- Fehleraggregation (letzte N Fehler) aus Dev-Surface + Log-Fallback
- Klassifizierung pro Fehler (`category`, `fixability`, `hint`)
- Manuelle Repair-Jobs mit LLM-gestuetztem Plan (`advisory`), inkl. Modellrouting offline/cloud
- Repo-Kanal-Metadaten (`official` vs `private`) und GitHub-Konfigurationsstatus
- Dashboard-Systemseite mit:
  - Self-Check Button
  - letzte Fehler
  - Repair-Job-Historie
  - Kanalumschaltung official/private

## Sicherheitsgrenzen (absichtlich)
- Kein ungeprueftes Auto-Patching im Runtime-Container
- Kein automatischer Push/PR in v1
- Ergebnisse sind gezielte Handlungsplaene, nicht blindes Schreiben in produktiven Code

## Geplante v2/v3 Erweiterungen
- **v2 Assistive Patcher:**
  - Lokaler Workspace-Clone (`official` + optional `private`)
  - Patch-Erzeugung in Branch `styx-self-repair/*`
  - Tests/Lint als Gate vor Push
- **v3 Full Loop (opt-in):**
  - Push in User-Repo
  - optional Upstream-PR gegen Official Repo
  - Feedback-Loop aus erfolgreich gemergten Fixes
  - Multi-Home-Musterabgleich nur anonymisiert/aggregiert

## API Kurzuebersicht
- `GET /api/v1/self-repair/status`
- `GET /api/v1/self-repair/settings`
- `POST /api/v1/self-repair/settings`
- `POST /api/v1/self-repair/github/test` (PAT + Repo validieren, optional speichern)
- `GET /api/v1/self-repair/errors?limit=10`
- `POST /api/v1/self-repair/self-check`
- `GET /api/v1/self-repair/jobs`
- `POST /api/v1/self-repair/jobs`
- `GET /api/v1/self-repair/jobs/<job_id>`
