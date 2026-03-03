# PilotSuite Styx -- Konsolidierter Masterplan

**Erstellt:** 2026-03-03
**Scope:** pilotsuite-styx-core + pilotsuite-styx-ha (Dual-Repo)
**Aktuelle Version:** v13.0.3
**Baseline-Analyse:** 200+ Markdown-Dateien, gesamter Quellcode, Audits

---

## TEIL 1: VISION

### Mission

> PilotSuite Styx ist ein **privacy-first, lokaler KI-Co-Pilot fuer Home Assistant**, der Haushaltsmuster lernt, Empfehlungen erklaert und niemals ohne Nutzerzustimmung handelt.

### Nicht-verhandelbare Prinzipien

| Prinzip | Bedeutung | Status |
|---------|-----------|--------|
| **Local-First** | Kein Cloud-Call fuer Kernfunktionen. Ollama (qwen3:0.6b) laeuft lokal | AKTIV |
| **Privacy-First** | PII-Redaktion, bounded Storage, opt-in Persistenz | AKTIV |
| **Governance-First** | Vorschlaege vor Aktionen, Human-in-the-Loop | AKTIV |
| **Safe Defaults** | Fail safe unter Unsicherheit, degraded mode statt Crash | AKTIV |
| **Explainability** | Jeder Vorschlag hat traceable Evidence | AKTIV |

### Normativer Loop

```
HA States --> Neuron Context --> Mood/Intent Weighting --> Pattern Mining --> Candidate --> User Decision --> Feedback
```

**Regeln:**
- Kein direkter State-to-Action Shortcut im Default-Modus
- High-Risk-Klassen (Tuerschloesser, Alarmanlagen) bleiben manuell
- Feedback (accept/defer/dismiss) ist Teil des Lernzyklus

### Dual-Repo-Vertrag

| Repository | Verantwortung | Tech Stack |
|------------|---------------|------------|
| **pilotsuite-styx-core** | Backend Runtime, Event Ingest, Brain Graph, Habitus Mining, Candidate Lifecycle, LLM/Memory, Health APIs | Flask/Waitress, SQLite WAL, Ollama, Python 3.11+ |
| **pilotsuite-styx-ha** | HA-Integration, Entities/Cards/Config-Flow, Events Forwarder, Repairs/Governance UX, Decision Sync | Home Assistant Custom Integration, Python, HACS |

**Trennung ist bewusst** fuer HA-Ecosystem-Kompatibilitaet und unabhaengige Release-Zyklen.

---

## TEIL 2: AKTUELLE BESTANDSAUFNAHME (IST-Zustand)

### 2.1 Systemumfang

| Metrik | Wert |
|--------|------|
| Backend-Services | 22+ Kern-Services |
| HA-Runtime-Module | 31 aktive Module |
| API-Endpoints | 130+ |
| Sensoren | 94+ |
| Dashboard Cards | 15+ |
| Tests (gesamt) | 2.526 (98% Pass-Rate) |
| Tests fehlgeschlagen | 20 |
| Tests uebersprungen | 30 |

### 2.2 Phasen-Status

| Phase | Beschreibung | Status | Version |
|-------|-------------|--------|---------|
| Phase 1 | Fundament (Flask, Brain Graph, Habitus, Events) | ABGESCHLOSSEN | v0.1-v0.8 |
| Phase 2 | Stabilisierung (Circuit Breakers, SQLite WAL, Config Validation) | ABGESCHLOSSEN | v1.0-v2.0 |
| Phase 3 | Feature-Ausbau (Neurons, Mood, MUPL, Media, Energy, 32 Module) | ABGESCHLOSSEN | v3.0-v3.7 |
| Phase 4a | Bugfixes (Sichere Datenzugriffe, Resource Leaks) | ABGESCHLOSSEN | v3.8 |
| Phase 4b | Produktionsrelease (hassfest, HACS) | ABGESCHLOSSEN | v3.9.0 |
| Phase 5 | Cross-Home Sharing (Notifications, Sharing, Federated Learning) | ABGESCHLOSSEN | v12.0.0 |
| Phase 6 | Type Hints & Tests (2.526 Tests, 98% Pass-Rate) | ABGESCHLOSSEN | v12.0.0 |
| **Phase 7** | **Production Readiness & Advanced ML** | **GEPLANT** | v13.x+ |

### 2.3 Kommunikationsarchitektur

```
Forward Path (HA --> Core):
  HA Events --> N3 Forwarder Envelope --> POST /api/v1/events --> EventProcessor --> BrainGraph --> Habitus

Return Path (Core --> HA):
  Candidate API --> HA Candidate Poller --> Repairs Issue/Workflow --> User Decision --> PUT /api/v1/candidates/:id

Realtime Path:
  Core Webhook Push --> HA Coordinator Merge --> Entity Refresh
```

---

## TEIL 3: FEHLER, BUGS & INKONSISTENZEN

### 3.1 KRITISCH (P0) -- Sofort beheben

| Nr | Problem | Betroffene Dateien | Impact |
|----|---------|-------------------|--------|
| **B-001** | **Version-Drift**: `manifest.json` zeigt `13.0.0`, `config.yaml` zeigt `13.0.3` | `pilotsuite-styx-core/copilot_core/manifest.json` | HA zeigt Add-on doppelt an |
| **B-002** | **Verlorene Dashboard-Dateien**: Bei Refactoring `ai_home_copilot` --> `copilot_ha` nicht migriert | `pilotsuite_dashboard_v10.5.yaml`, `pilotsuite_3tab_generator.py`, `habitus_zone_dashboard_card.py`, `habitus_control_cards.py` | Haupt-Dashboard fuer End-User fehlt |
| **B-003** | **CHANGELOG-Luecke**: Letzer Eintrag v13.0.0, aktuelle Version v13.0.3 | `CHANGELOG.md` (beide Repos) | Patch-Releases nicht dokumentiert |
| **B-004** | **20 fehlgeschlagene Tests** aus Phase 6 unbehoben | `tests/` (Core) | Blockiert v13.1.0 Release |
| **B-005** | **Release-Pipeline nicht synchronisiert**: HA+Core Versionen driften auseinander | Release-Workflow | Inkonsistente Releases |

### 3.2 HOCH (P1) -- Zeitnah beheben

| Nr | Problem | Betroffene Dateien | Impact |
|----|---------|-------------------|--------|
| **B-006** | **Dashboard-Version veraltet**: Zeigt `12.8.0` statt `13.0.3` | `dashboard/app.py:100`, `dashboard/api/v1/dashboard.py:144` | Falsche Version im UI |
| **B-007** | **OpenAPI-Docs veraltet**: Zeigen v12.5.0 bzw. v12.0.0 | `docs/openapi.yaml`, `docs/openapi-phase5-6.yaml` | API-Doku falsch |
| **B-008** | **Falsche GitHub-URLs**: Referenzieren `github.com/pilotsuite/` statt `github.com/GreenhillEfka/` | `docs/swagger/README.md:186`, `docs/API_COMPLETE.md:1006` | Broken Links |
| **B-009** | **Fehlende Workflow-Dateien**: `.github/workflows/pilotsuite-dev/github-action-shared.yml` referenziert, existiert nicht | 7+ Markdown-Dateien | CI/CD-Referenzen kaputt |
| **B-010** | **Naming-Inkonsistenz**: `ai_home_copilot`, `copilot_ha`, `pilotsuite` parallel verwendet | Dutzende Dateien | Verwirrung bei Installation |
| **B-011** | **DEVELOPMENT_PLAN.md veraltet**: Referenziert noch v7.10.1/v7.11.1 als Baseline | `DEVELOPMENT_PLAN.md` (beide Repos) | Veraltete Planung |

### 3.3 MITTEL (P2) -- Im naechsten Sprint

| Nr | Problem | Impact |
|----|---------|--------|
| **B-012** | **Dokumentations-Bloat**: 200+ MD-Dateien, viele redundant/veraltet | Schwer navigierbar |
| **B-013** | **Veraltete Submodul-Referenzen**: `ha-copilot-repo`, `styx-fork-core` etc. | Verwirrung |
| **B-014** | **Device Persistence fehlt**: `HANotifyAdapter` verliert Devices bei Restart | Geraete muessen neu registriert werden |
| **B-015** | **Scene/Routine Pattern Extraction**: In TODOS als P1 markiert, nicht implementiert | Feature-Gap |
| **B-016** | **Retina-Icon fehlt**: `icon@2x.png` bei Refactoring verloren | Kosmetisch |
| **B-017** | **Historische Audit-Reports**: Dokumentieren geloeste Probleme ohne "RESOLVED" Vermerk | Verwirrend |

### 3.4 Vision-Code-Abgleich (Gaps)

| Vision-Ziel | Status | Gap |
|-------------|--------|-----|
| Zero-Config First Run | IMPLEMENTIERT | Kein Gap |
| Progressive Disclosure UX | TEILWEISE | Dashboard-Dateien verloren, UX-Polishing noetig |
| Mobile-safe Layouts | TEILWEISE | Ingress Dashboard responsive, aber Cards-Optimierung offen |
| Explainable Recommendations | IMPLEMENTIERT | ExplainabilityEngine vorhanden |
| Fast Feedback Loop | TEILWEISE | WebSocket vorhanden, aber UI-Refresh-Latenz nicht gemessen |
| On-Device Inference | NICHT IMPLEMENTIERT | Phase 7 P2 |
| Anomaly Detection | NICHT IMPLEMENTIERT | Phase 7 P2 |
| Zeitreihen-Prognosen | NICHT IMPLEMENTIERT | Phase 7 P2 |
| Energy Load Shifting | NICHT IMPLEMENTIERT | Phase 7 P2 |
| Personalized Automation Timing | NICHT IMPLEMENTIERT | Phase 7 P2 |
| Voice Integration | NICHT IMPLEMENTIERT | Roadmap |
| Smart Calendar | TEILWEISE | CalendarService existiert, Smart Scheduling fehlt |
| Multi-Home Sync | TEILWEISE | Sharing API vorhanden, Multi-Location-UX fehlt |
| Styx Dashboard | TEILWEISE | Dashboard existiert, vereinheitlichtes UI fehlt |

---

## TEIL 4: STRATEGIE

### 4.1 Strategische Saeulen

```
        STABILISIEREN              OPTIMIEREN                ERWEITERN
   +--------------------+    +--------------------+    +--------------------+
   | Bugs fixen          |    | Performance        |    | Advanced ML        |
   | Tests reparieren    |    | Startup-Zeit       |    | Voice Integration  |
   | Docs konsolidieren  |    | Monitoring         |    | Smart Calendar     |
   | Dashboard restore   | -> | API-Dokumentation  | -> | Multi-Home UX      |
   | Version-Sync fixen  |    | Cache-Tuning       |    | Community Features |
   | Naming vereinheitl. |    | VectorStore-Opt.   |    | Plugin-Ecosystem   |
   +--------------------+    +--------------------+    +--------------------+
        Sprint 1-2              Sprint 3-4                Sprint 5-8+
```

### 4.2 Priorisierungsprinzipien

1. **Erst stabilisieren, dann optimieren, dann erweitern**
2. **Dual-Repo-Sync hat immer Vorrang** -- inkonsistente Versionen = kaputtes Produkt
3. **Tests muessen gruen sein** bevor neue Features gebaut werden
4. **Dokumentation ist Teil der Arbeit** -- kein Feature ohne aktuelle Docs
5. **Ein-Entwickler-Realismus** -- lieber wenige Features solide als viele halbfertig

---

## TEIL 5: ENTWICKLUNGSPLAN

### Sprint 1: STABILISIERUNG (Woche 1-2)

**Ziel:** Alle kritischen Bugs fixen, Repos in sauberen Zustand bringen

#### Backend (Core)

| Task-ID | Task | Prio | ETA |
|---------|------|------|-----|
| S1-001 | `manifest.json` Version auf `13.0.3` synchronisieren | P0 | 5min |
| S1-002 | `dashboard/app.py` + `dashboard/api/v1/dashboard.py` Version updaten | P0 | 5min |
| S1-003 | 20 fehlgeschlagene Tests analysieren und beheben | P0 | 2-4h |
| S1-004 | CHANGELOG.md mit v13.0.1-v13.0.3 Eintraegen aktualisieren | P0 | 30min |
| S1-005 | OpenAPI-Docs Version updaten (openapi.yaml, openapi-phase5-6.yaml) | P1 | 10min |
| S1-006 | Falsche GitHub-URLs in docs/ korrigieren | P1 | 10min |
| S1-007 | Release-Pipeline: Auto-Sync-Script fuer HA+Core Versionen | P0 | 1h |

#### Frontend/HA Integration

| Task-ID | Task | Prio | ETA |
|---------|------|------|-----|
| S1-008 | Verlorene Dashboard-Dateien aus v11.0.0 wiederherstellen + migrieren | P0 | 1-2h |
| S1-009 | `pilotsuite_dashboard_v10.5.yaml` an `copilot_ha` Pfade anpassen | P0 | 30min |
| S1-010 | `habitus_zone_dashboard_card.py` + `habitus_control_cards.py` migrieren | P1 | 1h |
| S1-011 | `icon@2x.png` wiederherstellen | P2 | 5min |

#### Dokumentation

| Task-ID | Task | Prio | ETA |
|---------|------|------|-----|
| S1-012 | Naming vereinheitlichen: `copilot_ha` als Standard, alle alten Referenzen updaten | P1 | 2h |
| S1-013 | DEVELOPMENT_PLAN.md auf v13.0.3 Baseline aktualisieren | P1 | 1h |
| S1-014 | Veraltete Submodul-Referenzen entfernen/dokumentieren | P2 | 30min |
| S1-015 | "RESOLVED" Vermerke an historische Audit-Reports anfuegen | P2 | 30min |

**Sprint 1 Deliverables:**
- Alle Version-Dateien synchron
- 0 fehlgeschlagene Tests
- Dashboard-Dateien wiederhergestellt
- Sauberer CHANGELOG
- Release-Pipeline mit Auto-Sync

---

### Sprint 2: DOKUMENTATIONSKONSOLIDIERUNG (Woche 3-4)

**Ziel:** Dokumentation strukturieren, Redundanz beseitigen

| Task-ID | Task | Prio | ETA |
|---------|------|------|-----|
| S2-001 | Dokumentationsstruktur definieren: `docs/` als Single Source of Truth | P1 | 1h |
| S2-002 | Historische Iterationen/Reviews in `archive/` verschieben | P2 | 1h |
| S2-003 | INDEX.md als navigierbares Inhaltsverzeichnis aktualisieren | P1 | 1h |
| S2-004 | API-Referenz vervollstaendigen (alle 130+ Endpoints dokumentiert) | P1 | 4h |
| S2-005 | OpenAPI-Spec fuer alle Endpoints generieren (flask-openapi3) | P1 | 3h |
| S2-006 | User Manual aktualisieren (Installation, Konfiguration, Troubleshooting) | P1 | 2h |
| S2-007 | Quick Start Guide auf v13.x updaten | P1 | 1h |
| S2-008 | Fehlende/kaputte Workflow-Referenzen bereinigen | P1 | 1h |

**Sprint 2 Deliverables:**
- Klare Dokumentationsstruktur
- Vollstaendige API-Referenz
- Aktuelles User Manual
- OpenAPI-Spec

---

### Sprint 3: PERFORMANCE-OPTIMIERUNG (Woche 5-6)

**Ziel:** Production Readiness (Phase 7 P1)

| Task-ID | Task | Prio | ETA |
|---------|------|------|-----|
| S3-001 | Init-Profiling: Startup-Bottlenecks identifizieren | P1 | 2h |
| S3-002 | Lazy Loading fuer selten genutzte Module (`core_setup.py`) | P1 | 3h |
| S3-003 | Cache Tuning: TTL-basiertes Caching fuer Sensor-Daten + RAG | P1 | 3h |
| S3-004 | VectorStore-Optimierung: Indexierung, effizientere Aehnlichkeitssuche | P1 | 4h |
| S3-005 | Connection Pooling Metriken ins Dashboard integrieren | P1 | 2h |
| S3-006 | Cache-Hit-Rate Monitoring implementieren (Ziel: >80%) | P1 | 2h |

**Sprint 3 Deliverables:**
- Startup-Zeit <5s
- Cache-Hit-Rate >80%
- VectorStore skaliert fuer 5000+ Eintraege
- Performance-Dashboard

---

### Sprint 4: MONITORING & SICHERHEIT (Woche 7-8)

**Ziel:** Observability und Security Hardening

| Task-ID | Task | Prio | ETA |
|---------|------|------|-----|
| S4-001 | Prometheus-Metriken fuer alle Phase 5/6 Endpoints | P1 | 4h |
| S4-002 | Health-Check erweitern: CPU, RAM, Pool-Status, Cache-Hit-Rate | P1 | 2h |
| S4-003 | Security Headers (CSP, HSTS, X-Frame-Options) | P1 | 1h |
| S4-004 | CORS Configuration Review + Fix | P1 | 1h |
| S4-005 | API-Rate-Limiting konfigurieren | P1 | 2h |
| S4-006 | Device Persistence fuer HANotifyAdapter | P1 | 3h |
| S4-007 | Scene Pattern Extraction implementieren | P1 | 4h |
| S4-008 | Routine Pattern Extraction implementieren | P1 | 4h |

**Sprint 4 Deliverables:**
- Prometheus-Metriken aktiv
- Erweiterter Health-Endpoint
- Security Headers
- Device Persistence
- Pattern Extraction Features

---

### Sprint 5-6: DASHBOARD & UX (Woche 9-12)

**Ziel:** Vereinheitlichtes Styx Dashboard

| Task-ID | Task | Prio | ETA |
|---------|------|------|-----|
| S5-001 | Styx Dashboard v1.0: Brain Graph + Chat + Historie vereint | P1 | 8h |
| S5-002 | Neuron-Aktivitaet und Mood-Verlauf Visualisierung | P1 | 4h |
| S5-003 | Echtzeit-Updates ueber WebSocket (Dashboard) | P1 | 4h |
| S5-004 | Responsives Design: Tablet-Wandmontage + Mobile | P1 | 4h |
| S5-005 | RAG Search Frontend (TypeScript) | P1 | 3h |
| S5-006 | Zone Editor TypeScript Frontend | P1 | 3h |
| S5-007 | OpenAPI-Spec UI (Swagger/Redoc) | P1 | 3h |
| S5-008 | Dark Mode Support | P2 | 2h |
| S5-009 | Loading-Skeletons fuer API-Calls | P2 | 2h |
| S5-010 | Micro-Interactions fuer Buttons | P2 | 2h |

**Sprint 5-6 Deliverables:**
- Vereinheitlichtes Styx Dashboard
- Realtime-Updates
- Responsive/Mobile-ready
- RAG Search UI
- Zone Editor UI

---

### Sprint 7-8: ADVANCED ML (Woche 13-16)

**Ziel:** Phase 7 P2 -- Machine Learning Features

| Task-ID | Task | Prio | ETA |
|---------|------|------|-----|
| S7-001 | On-Device Inference: TFLite/ONNX Runtime (Ziel: <100ms) | P2 | 8h |
| S7-002 | Anomaly Detection: Isolation Forest MVP (Ziel: >85% Precision) | P2 | 6h |
| S7-003 | Zeitreihen-Prognosen: LSTM fuer Temperatur/Energie/Anwesenheit | P2 | 8h |
| S7-004 | Energy Load Shifting: PV-Prognosen + dynamische Tarife | P2 | 6h |
| S7-005 | Personalized Automation Timing | P2 | 4h |
| S7-006 | Model-Performance-Monitoring | P2 | 3h |
| S7-007 | Model-Drift Detection | P2 | 3h |

**Sprint 7-8 Deliverables:**
- On-Device Inference funktional
- Anomaly Detection aktiv
- Zeitreihen-Prognosen (1-24h)
- Energy Load Shifting (-20% Kosten)

---

### Sprint 9+: ZUKUNFTSFEATURES (Woche 17+)

| Feature | Beschreibung | Prioritaet |
|---------|-------------|------------|
| **Voice Integration** | HA Voice Assistant Anbindung, kontextbewusst | P2 |
| **Smart Calendar** | Stimmungsbewusstes Scheduling, Beleuchtungsanpassung | P2 |
| **Multi-Home UX** | Einheitliche Steuerung mehrerer Wohnorte | P2 |
| **MCP Phase 2** | Erweiterte Skills fuer AI-Clients | P2 |
| **Plugin Ecosystem** | Community-Plugins fuer Erweiterungen | P3 |
| **Federated Learning v2** | Verbesserte Cross-Home Aggregation | P3 |

---

## TEIL 6: ARBEITSPLAN (Wochenplan)

### Sofort-Massnahmen (Tag 1)

```
[ ] B-001: manifest.json Version 13.0.0 --> 13.0.3 (Core)
[ ] B-003: CHANGELOG.md aktualisieren (beide Repos)
[ ] B-006: Dashboard-Version 12.8.0 --> 13.0.3
[ ] B-007: OpenAPI-Docs Version updaten
[ ] B-008: GitHub-URLs korrigieren
[ ] B-002: Dashboard-Dateien wiederherstellen (git show v11.0.0:...)
```

### Woche 1 (Stabilisierung Core)

```
Mo: S1-001 bis S1-004 (Version-Sync, CHANGELOG)
Di: S1-003 (20 Tests fixen -- Hauptaufwand)
Mi: S1-007 (Release-Pipeline Auto-Sync)
Do: S1-008 bis S1-010 (Dashboard-Recovery)
Fr: S1-012, S1-013 (Naming + Dev Plan Update)
```

### Woche 2 (Stabilisierung HA)

```
Mo: S1-005, S1-006, S1-011 (Docs + Icons)
Di: S1-014, S1-015 (Submodule + Historische Reports)
Mi-Fr: Regressionstests, E2E-Validierung, Release v13.1.0
```

### Woche 3-4 (Dokumentation)

```
S2-001 bis S2-008 parallel abarbeiten
Fokus: API-Referenz, OpenAPI-Spec, User Manual
```

### Woche 5-8 (Performance + Security)

```
Sprint 3 + Sprint 4 Tasks
Performance-Profiling --> Lazy Loading --> Cache --> VectorStore
Security Headers --> Rate Limiting --> Device Persistence
```

### Woche 9-12 (Dashboard & UX)

```
Sprint 5-6 Tasks
Styx Dashboard v1.0 --> Realtime --> Mobile --> RAG Search UI
```

### Woche 13-16 (Advanced ML)

```
Sprint 7-8 Tasks
On-Device Inference --> Anomaly Detection --> Zeitreihen --> Energy
```

---

## TEIL 7: RELEASE-PLAN

| Version | Inhalt | Geplant |
|---------|--------|---------|
| **v13.1.0** | Bugfixes (Version-Sync, Dashboard-Recovery, Test-Fixes) | Sprint 1-2 |
| **v13.2.0** | Dokumentationskonsolidierung, OpenAPI-Spec | Sprint 2 |
| **v14.0.0** | Performance-Optimierung, Monitoring, Security | Sprint 3-4 |
| **v14.1.0** | Pattern Extraction, Device Persistence | Sprint 4 |
| **v15.0.0** | Styx Dashboard v1.0, RAG Search UI | Sprint 5-6 |
| **v16.0.0** | Advanced ML (On-Device, Anomaly, Zeitreihen) | Sprint 7-8 |
| **v17.0.0** | Voice, Calendar, Multi-Home | Sprint 9+ |

### Release-Gate (gilt fuer alle Releases)

Ein Release ist production-ready **nur wenn**:
1. Alle lokalen Tests gruen (0 failures)
2. Main CI gruen (GitHub Actions)
3. Production-Guard Workflow gruen (15min Cron)
4. Versionen/Changelogs/Docs synchron (beide Repos)
5. Kein Version-Drift zwischen config.yaml und manifest.json

---

## TEIL 8: METRIKEN & ZIELE

### Performance-Ziele

| Metrik | Aktuell | Ziel | Sprint |
|--------|---------|------|--------|
| Startup-Zeit | TBD | <5s | Sprint 3 |
| Request-Latency (P95) | TBD | <200ms | Sprint 3 |
| Cache-Hit-Rate | 0% | >80% | Sprint 3 |
| Connection-Pool-Effizienz | begrenzt | >90% | Sprint 3 |
| Test-Pass-Rate | 98% | 100% | Sprint 1 |

### ML-Ziele

| Feature | Ziel-Latenz | Ziel-Genauigkeit | Sprint |
|---------|-------------|------------------|--------|
| On-Device Inference | <100ms | >90% | Sprint 7 |
| Anomaly Detection | <1s | >85% Precision | Sprint 7 |
| Zeitreihen-Prognose | <500ms | <10% MAPE | Sprint 7-8 |
| Energy Load Shifting | <100ms | -20% Kosten | Sprint 8 |

### Qualitaetsziele

| Metrik | Ziel | Sprint |
|--------|------|--------|
| Test-Abdeckung | >85% | Sprint 4 |
| API-Dokumentation | 100% Endpoints dokumentiert | Sprint 2 |
| Markdown-Dateien (bereinigt) | <80 relevante Dateien | Sprint 2 |
| Naming-Konsistenz | 100% `copilot_ha` | Sprint 1 |

---

## TEIL 9: RISIKEN & MITIGATIONEN

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|---------------------|--------|------------|
| Version-Drift bei Releases | HOCH | HOCH | Auto-Sync-Script (S1-007) |
| Dokumentation veraltet erneut | MITTEL | MITTEL | Docs-als-Teil-der-Definition-of-Done |
| ML-Features zu ressourcenintensiv | MITTEL | HOCH | Profiling auf Pi 4, Fallback-Modelle |
| Dashboard-Regression nach Migration | NIEDRIG | HOCH | E2E-Tests fuer Dashboard (Playwright) |
| Ein-Entwickler-Bottleneck | HOCH | MITTEL | Klare Priorisierung, keine Feature-Ueberladung |
| Breaking Changes bei HA-Updates | MITTEL | HOCH | hassfest-Validierung im CI, HA-Versionsmatrix |

---

## TEIL 10: ARCHITEKTURELLE EMPFEHLUNGEN

### 10.1 Kurzfristig (Sprint 1-2)

1. **Version-Sync-Script erstellen**: Ein einziges Script, das alle VERSION-Dateien in beiden Repos synchron haelt
2. **Pre-Commit Hook**: Verhindert Commits mit Version-Drift
3. **Naming-Konvention durchsetzen**: `copilot_ha` fuer HA-Integration, `copilot_core` fuer Backend

### 10.2 Mittelfristig (Sprint 3-6)

1. **Monorepo-Evaluation**: Pruefen ob ein Monorepo die Sync-Probleme loest (Trade-off: HACS-Kompatibilitaet)
2. **OpenAPI-first Development**: API-Aenderungen erst in Spec definieren, dann implementieren
3. **Feature Flags**: Neue Features hinter Flags, schrittweises Rollout

### 10.3 Langfristig (Sprint 7+)

1. **Plugin-API v2**: Klare Extension Points fuer Community-Plugins
2. **Event-Driven Architecture**: Event Bus zwischen Modulen statt direkte Aufrufe
3. **ML-Model-Registry**: Versionierung und Deployment von ML-Modellen

---

## ANHANG A: DATEISTRUKTUR-EMPFEHLUNG

### Bereinigte Dokumentationsstruktur (Ziel)

```
docs/
  ARCHITECTURE.md          -- Technische Architektur
  API_REFERENCE.md         -- Vollstaendige API-Referenz
  ROADMAP.md               -- Aktive Roadmap
  USER_MANUAL.md           -- Benutzerhandbuch
  QUICK_START_GUIDE.md     -- Schnelleinstieg
  SECURITY.md              -- Sicherheitsrichtlinien
  RELEASE_PROCESS.md       -- Release-Workflow
  openapi.yaml             -- OpenAPI Spec
  api/                     -- API-Detaildokumente
  swagger/                 -- Swagger UI

archive/                   -- Historische Berichte
  iterations/              -- Iterationsberichte
  reviews/                 -- Historische Reviews
  releases/                -- Alte Release-Notes

VISION.md                  -- Vision (aktiv)
CHANGELOG.md               -- Aktiver Changelog
README.md                  -- Einstiegspunkt
DEVELOPMENT_PLAN.md        -- Aktiver Entwicklungsplan
PROJECT_STATUS.md          -- Aktueller Status
TODOS.md                   -- Aktive Tasks
CLAUDE.md                  -- Agent-Konfiguration
```

### Zu archivierende/entfernende Dateien (Beispiele)

- 50+ `iterations/iteration-*.md` --> `archive/iterations/`
- 40+ `reviews/groky-*.md` --> `archive/reviews/`
- `PHASE5_TODO.md`, `PHASE6_TODO.md` --> Referenz in CHANGELOG
- `CORE_AUDIT_REPORT_*.md` --> `archive/audits/`
- Alle `whatsapp_summary_*.md` --> `archive/`
- Alle `dev_summary_*.md` --> `archive/`
- Alle `cowdya_report_*.md` --> `archive/`

---

## ANHANG B: DUAL-REPO SYNC-CHECKLIST

### Vor jedem Release pruefen:

```
[ ] VERSION (Root) -- beide Repos
[ ] copilot_core/VERSION
[ ] copilot_core/rootfs/usr/src/app/VERSION
[ ] copilot_core/config.yaml (version)
[ ] copilot_core/manifest.json (version)
[ ] custom_components/copilot_ha/manifest.json (version)
[ ] CHANGELOG.md -- beide Repos, gleicher Eintrag
[ ] RELEASE_NOTES.md -- beide Repos
[ ] hacs.json (HA-Repo)
[ ] repository.json (Core-Repo)
[ ] Dashboard version strings (app.py, dashboard.py)
[ ] OpenAPI version strings
```

---

## ANHANG C: ZUSAMMENFASSUNG DER OFFENEN TASKS (ALLE QUEUES)

### Backend (@cowdya)
- P0-101: HA-Core Sync sicherstellen
- P0-102: Release-Pipeline fixen
- P1-024: Connection Pooling Metriken
- P1-025: Cache-Hit-Rate Monitoring
- P1-026: RAG Search Endpoints
- P1-027: Startup-Optimierung

### Frontend (@codexa)
- P0-201: Version-Sync im Dashboard
- P0-202: Dashboard zeigt aktuelle Version
- P1-090: RAG Search Frontend
- P1-091: Zone Editor Frontend
- P1-092: Dashboard-Erweiterung Styx v1.0
- P1-093: OpenAPI-Spec UI

### Infra (@toolix)
- P0-301: Auto-Sync HA+Core vor Release
- P0-302: HA Version synchronisieren
- P0-303: GitHub Actions parallel testen
- P1-046: Security Headers
- P1-047: CORS Review
- P1-048: Rate-Limiting
- P1-049: CI/CD Sync-Check

### ML (@cogita)
- P0-401: ML-Features Sync
- P0-402: Model-Versioning
- P1-013: On-Device Inference
- P1-014: Anomaly Detection
- P1-015: Zeitreihen-Prognosen
- P1-016: Energy Load Shifting
- P1-017: Automation Timing

---

**Dieses Dokument ist die konsolidierte Wahrheit fuer das PilotSuite Styx Projekt.**
**Es ersetzt alle vorherigen Teilplaene und sollte als primaere Referenz dienen.**

*Erstellt: 2026-03-03 | Basierend auf: pilotsuite-styx-core v13.0.3 + pilotsuite-styx-ha v13.0.3*
