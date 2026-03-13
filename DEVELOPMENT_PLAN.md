# PilotSuite Styx -- Entwicklungsplan & Vision

**Erstellt:** 2026-02-24
**Aktualisiert:** 2026-03-03
**Status:** Aktiver Entwicklungsplan fuer PilotSuite Styx
**Aktuelle Version:** v13.9.0

---

## Vision

**PilotSuite Styx** ist ein privacy-first, lokaler KI-Assistent fuer Home Assistant, der:
- Die Muster deines Zuhauses lernt (Habitus)
- Die Stimmung und den Kontext bewertet (Mood)
- Intelligente Automatisierungsvorschlaege macht
- **Nur mit deiner Zustimmung** handelt (Governance-first)

### Non-negotiable Principles

| Prinzip | Bedeutung |
|---------|-----------|
| **Local-first** | Alles lokal, kein Cloud-API-Call fuer Kernfunktionen |
| **Privacy-first** | PII-Redaktion, bounded Storage, opt-in |
| **Governance-first** | Vorschlaege vor Aktionen, Human-in-the-Loop |
| **Safe Defaults** | Fail safe unter Unsicherheit, degraded mode |
| **Explainability** | Jeder Vorschlag hat traceable Evidence |

---

## Dual-Repos-System

| Repo | Funktion | Version |
|------|----------|---------|
| `pilotsuite-styx-core` | Backend Runtime, LLM, Brain Graph, Habitus, Candidates, 130+ API Endpoints | v13.0.4 |
| `pilotsuite-styx-ha` | HACS Integration, 94+ Sensoren, Dashboard Cards, 31 Module | v13.0.4 |

**Release-Baseline:** v13.0.4 (2026-03-03)

---

## Architektur

```
Home Assistant
+-- HACS Integration (copilot_ha)             <-- 94+ Sensoren, 31 Module, Dashboard
|     HTTP REST API (Token-Auth)
|     v
+-- Core Add-on (copilot_core) Port 8909     <-- Brain Graph, Habitus, Mood, LLM
      + Ollama (bundled, qwen3:0.6b default)
      + optional Cloud Fallback
```

### 22+ Backend-Services (pilotsuite-styx-core)

| Service | Funktion |
|---------|----------|
| BrainGraphStore | State-Graph mit Nodes + Edges, Decay, Snapshots |
| HabitusMiner | Association Rule Mining, Zone-basiert |
| MoodService | 3D-Scoring (Comfort/Joy/Frugality), SQLite-Persistenz |
| CandidateStore | Vorschlaege mit Governance-Workflow |
| NeuronManager | 14 Bewertungs-Neuronen |
| EventStore | Event-Persistenz und -Abfrage |
| VectorStore | Bag-of-Words Embedding, Similarity Search |
| KnowledgeGraph | Entity-Beziehungen |
| TagRegistry | Entity-Tagging |
| NotificationService | Push-System (9 Endpoints) |
| SharingService | Cross-Home Sharing (7 Endpoints) |
| CollectiveIntelligence | Federated Learning (15 Endpoints) |
| ConnectionPoolManager | HA + Ollama Connection Pooling |
| HybridCache | Redis + Local LRU Cache |
| SystemHealthService | Health Checks (Zigbee, Z-Wave, Recorder) |
| MediaZoneManager | Media-Zonen Verwaltung |
| MCPServer | Skills fuer externe AI-Clients |
| TelegramBot | Telegram Integration mit Tool-Calling |
| ModuleRegistry | Dynamic Module Discovery + Lifecycle |
| EnergyService | Energie-Monitoring |
| WeatherService | Wetter-Integration |
| CalendarService | Kalender-Integration |

---

## Abgeschlossene Phasen

| Phase | Beschreibung | Version |
|-------|-------------|---------|
| Phase 1 | Fundament (Flask, Brain Graph, Habitus, Events) | v0.1-v0.8 |
| Phase 2 | Stabilisierung (Circuit Breakers, SQLite WAL) | v1.0-v2.0 |
| Phase 3 | Feature-Ausbau (Neurons, Mood, MUPL, 32 Module) | v3.0-v3.7 |
| Phase 4 | Bugfixes + Produktionsrelease (hassfest, HACS) | v3.8-v3.9 |
| Phase 5 | Cross-Home Sharing (31 Endpoints, Federated Learning) | v12.0.0 |
| Phase 6 | Type Hints & Tests (2.526 Tests, 98% Pass-Rate) | v12.0.0 |

---

## Aktuelle Phase: Phase 7 -- Production Readiness & Advanced ML

### Sprint 1-2: Stabilisierung (AKTIV)

| Task | Status | Details |
|------|--------|---------|
| Version-Sync HA+Core | ERLEDIGT | Alle Dateien auf v13.0.4 synchronisiert |
| OpenAPI Version-Fix | ERLEDIGT | 12.5.0/12.8.0 auf 13.0.4 korrigiert |
| GitHub-URL-Fix | ERLEDIGT | pilotsuite/ auf GreenhillEfka/ korrigiert |
| CHANGELOG-Luecken | ERLEDIGT | v13.0.3 + v13.0.4 Eintraege ergaenzt |
| Test-Failures beheben | IN ARBEIT | 20+ fehlgeschlagene Tests aus Phase 6 |
| Masterplan erstellt | ERLEDIGT | Konsolidierter Projektplan mit Vision |

### Sprint 3-4: Performance & Security (Geplant)

| Task | Status | Details |
|------|--------|---------|
| Connection Pooling | ERLEDIGT | 28.5x Speedup, 100% Pool-Effizienz |
| Hybrid Cache | ERLEDIGT | Redis + Local LRU, TTL-basiert |
| Prometheus-Metriken | GEPLANT | Phase 5/6 Endpoint-Monitoring |
| Security Headers | GEPLANT | CSP, HSTS, X-Frame-Options |
| Device Persistence | GEPLANT | HANotifyAdapter behaelt Devices bei Restart |

### Sprint 5-6: Dashboard & UX (Geplant)

| Task | Status | Details |
|------|--------|---------|
| Styx Dashboard v1.0 | GEPLANT | Brain Graph + Chat + Historie vereint |
| RAG Search Frontend | GEPLANT | TypeScript Frontend |
| Zone Editor Frontend | GEPLANT | TypeScript Frontend |
| Mobile-Responsive | GEPLANT | Tablet-Wandmontage + Mobile |

### Sprint 7-8: Advanced ML (Geplant)

| Task | Status | Details |
|------|--------|---------|
| On-Device Inference | GEPLANT | TFLite/ONNX Runtime, Ziel: <100ms |
| Anomaly Detection | GEPLANT | Isolation Forest MVP |
| Zeitreihen-Prognosen | GEPLANT | LSTM fuer Temperatur/Energie |
| Energy Load Shifting | GEPLANT | PV-Prognosen + dynamische Tarife |

---

## Release-Plan

| Version | Inhalt | Status |
|---------|--------|--------|
| v13.0.4 | Version-Sync, Docs-Fixes, Masterplan | AKTUELL |
| v13.1.0 | Test-Fixes, Dashboard-Recovery | NAECHSTES |
| v14.0.0 | Performance, Monitoring, Security | GEPLANT |
| v15.0.0 | Styx Dashboard v1.0 | GEPLANT |
| v16.0.0 | Advanced ML Features | GEPLANT |

---

## Release-Gate

Ein Release ist production-ready **nur wenn**:
1. Alle lokalen Tests gruen (0 failures)
2. Main CI gruen (GitHub Actions)
3. Production-Guard Workflow gruen (15min Cron)
4. Versionen/Changelogs/Docs synchron (beide Repos)
5. Kein Version-Drift zwischen config.yaml und manifest.json

---

## Dokumentation

| Dokument | Inhalt |
|----------|--------|
| [PILOTSUITE_MASTERPLAN_2026-03-03.md](PILOTSUITE_MASTERPLAN_2026-03-03.md) | Konsolidierter Masterplan |
| [README.md](README.md) | Installation, Features, API Overview |
| [VISION.md](VISION.md) | Mission, Principles, Architecture |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Production Audit, Module Status |
| [CHANGELOG.md](CHANGELOG.md) | Release History |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Services, Data Flow, Persistence |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phase 5-7, Future Plans |

---

**Letzte Aktualisierung:** 2026-03-03
**Basiert auf:** pilotsuite-styx-core v13.0.4 + pilotsuite-styx-ha v13.0.4
