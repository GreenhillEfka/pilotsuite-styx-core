# PS-REL-002 — Changelog-Konvention v13+

Status: Draft zur Übernahme in beide Repos (`pilotsuite-styx-core`, `pilotsuite-styx-ha`)
Scope: Releases ab v13.x (inkl. Patch- und Hotfix-Releases)

## Ziele

- Einheitliche, auditierbare Release-Historie über beide Repos
- Klare Trennung zwischen user-sichtbaren Änderungen und internen Refactors
- Deterministische Grundlage für Release Notes, Upgrade-Kommunikation und Rollback-Entscheidungen

## Datei-Orte (verbindlich)

Pro Repo:

- **Pflicht:** `CHANGELOG.md` im Repo-Root
- **Pflicht:** `docs/release/CHANGELOG_CONVENTION_v13_PLUS.md` (diese Konvention, als Copy)
- **Optional:** `docs/releases/<version>.md` (ausführliche technische Notes / Incident-Postmortems)

## Versionsschema

- SemVer: `MAJOR.MINOR.PATCH`
- Tag-Format: `v<MAJOR>.<MINOR>.<PATCH>` (z. B. `v13.2.1`)
- Keine „silent releases“ ohne Tag + Changelog-Eintrag

## Changelog-Format (Keep-a-Changelog-inspiriert)

Oben im `CHANGELOG.md` steht immer:

```md
## [Unreleased]
```

Jede Release-Sektion verwendet:

```md
## [<MAJOR>.<MINOR>.<PATCH>] - YYYY-MM-DD
```

### Sektionen je Version

Nur Sektionen aufnehmen, die Inhalt haben:

- `Added`
- `Changed`
- `Fixed`
- `Security`
- `Deprecated`
- `Removed`
- `Ops`

Zusatzfelder je Version (als eigene Sub-Section oder Bullet-Block, aber konsistent pro Repo):

- `Compatibility` (z. B. „Core v13.2.1 ↔ HA v13.2.1“)
- `Migration required` (`yes|no`, bei `yes` Link auf Migrationsanleitung)

## Eintragsregeln (verbindlich)

1. **User-Impact zuerst:** Jeder Bullet beschreibt sichtbare Wirkung; Technik-Detail optional danach.
2. **Ein Bullet = eine Aussage:** Keine Multi-Paragraph-Absätze in `CHANGELOG.md`.
3. **Referenzen:** Format `PS-...` (optional PR/Commit in Klammern).
4. **Security nie verstecken:** Security-relevante Fixes immer zusätzlich unter `Security`.
5. **Breaking Changes:** In `Changed` mit Prefix `BREAKING:` markieren und Migration verlinken.
6. **Noisy Commits bündeln:** Interne Refactors zusammenfassen statt Commit-Log dumpen.
7. **Dual-Repo-Konsistenz:** Bei gekoppelten Änderungen *in beiden Repos* Eintrag + Gegenreferenz.

## Dual-Repo Release-Block (Pflicht bei gekoppelten Releases)

Jede gekoppelte Version enthält einen kurzen Block (bevor die Sektionen starten):

- `Core version:`
- `HA version:`
- `Protocol/API contract:` (z. B. „event schema v3“, „X-Auth-Token only“)
- `Test gate:` Verweis auf Smoke-/Contract-Gate

## Link-Konvention (empfohlen)

Wenn die Repo-Plattform Compare-Links unterstützt, sollen am Ende des Changelogs Link-Referenzen stehen (wie bei Keep a Changelog):

- `[Unreleased]: <compare-url>`
- `[13.2.1]: <compare-url>`

Die konkreten URLs sind repo-spezifisch; wichtig ist die **Konsistenz innerhalb eines Repos**.

## Release-Template (Kurzform)

```md
## [13.2.1] - 2026-03-06
### Compatibility
- Core v13.2.1 ↔ HA v13.2.1
- Migration required: no

### Fixed
- Webhook retries classify transient failures correctly under load (PS-P0-012).

### Security
- Auth token validation remains fail-closed on missing token paths (PS-P0-001).

### Ops
- Added queue delivery stats in runtime telemetry (PS-P0-011).
```

## Governance / Gate-Verankerung

- Changelog ist Release-Gate-Artefakt (Pflicht für Go/No-Go; siehe `PS-REL-001`)
- Ohne aktualisierten `CHANGELOG.md` kein Release-Tag
- Review-Verantwortung: Release/Ops (Hermes) + jeweiliger Repo-Owner

## Rollout-Schritte (für PS-REL-002)

1. Konvention in beiden Repos als `docs/release/CHANGELOG_CONVENTION_v13_PLUS.md` ablegen.
2. Bestehende `CHANGELOG.md` auf neues Format mappen (mind. letzte 3 Releases).
3. CI-Gate ergänzen: Tag nur erlaubt, wenn `CHANGELOG.md` im Release-Commit geändert wurde.
4. In `PS-REL-001` Release-Checklist als MUSS-Punkt verankern (Verweis auf diese Konvention).

## Akzeptanzkriterien (Definition of Done)

- In **beiden** Repos:
  - `docs/release/CHANGELOG_CONVENTION_v13_PLUS.md` vorhanden
  - `CHANGELOG.md` enthält `Unreleased` + mindestens 3 Releases im neuen Format
- `PS-REL-001` verweist auf PS-REL-002 (besteht bereits) und Gate C ist damit operationalisierbar
