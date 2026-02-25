# PilotSuite Roadmap

> Zuletzt aktualisiert: Februar 2026

PilotSuite ist ein Ein-Entwickler-Projekt mit ambitionierten Zielen. Diese Roadmap beschreibt den bisherigen Weg, die aktuelle Entwicklung und die geplante Zukunft. Alle Zeitangaben sind Richtwerte -- Prioritaeten koennen sich je nach Community-Feedback und technischer Machbarkeit verschieben.

---

## Bisherige Releases

### Phase 1 -- Fundament (v0.1 - v0.8)

Die ersten Versionen legten das Fundament fuer das gesamte System:

- **Flask-Backend** als zentrale API-Schicht mit Waitress als Production-Server
- **Brain Graph** zur Modellierung von Zusammenhaengen zwischen Sensoren, Raeumen und Automatisierungen
- **Habitus-System** fuer die Erfassung von Gewohnheiten und Tagesrhythmen
- **Event Pipeline** fuer die Verarbeitung von Home-Assistant-Ereignissen in Echtzeit

Diese Phase definierte die Kernarchitektur: lokal, modular, privacy-first.

### Phase 2 -- Stabilisierung (v1.0 - v2.0)

Der Fokus verschob sich von Features auf Zuverlaessigkeit:

- **Circuit Breakers** fuer HA-Supervisor- und Ollama-Verbindungen (automatische Fehlerisolierung)
- **SQLite WAL-Modus** mit `busy_timeout` fuer zuverlaessigen konkurrierenden Zugriff
- **Config Validation** mit `vol.Range`-Grenzen und sicheren Typ-Konvertierungen (`_safe_int`, `_safe_float`)
- **Request Timing** mit X-Request-ID-Korrelation und Slow-Request-Logging (>2s)

Das System wurde produktionsreif.

### Phase 3 -- Feature-Ausbau (v3.0 - v3.7)

Die grosse Erweiterungsphase brachte die intelligenten Module:

- **Neurons** -- lernfaehige Muster-Erkennung fuer Automatisierungen
- **Mood Engine** -- Stimmungserkennung basierend auf Sensorik, Wetter und Tageszeit
- **MUPL (Multi-User Preference Learning)** -- individuelle Praeferenzen pro Haushaltsmitglied
- **Media Zones** -- raumuebergreifende Mediensteuerung mit Kontext
- **Energy Module** -- Energieverbrauchsanalyse und Optimierungsvorschlaege
- **Waste/Birthday** -- Muellkalender-Integration und Geburtstagserinnerungen

Insgesamt wuchs das System auf 32 Module, 94+ Sensoren und 130+ API-Endpunkte.

### Phase 4a -- Bugfixes (v3.8)

Qualitaetssicherung und Stabilitaet:

- **Sichere Datenzugriffe** -- defensive Programmierung gegen fehlende oder unerwartete Werte
- **Resource Leak Fixes** -- Behebung von Speicher- und Verbindungslecks
- **Prune Logic Fix** -- korrigierte Bereinigung veralteter Daten

### Phase 4b -- Produktionsrelease (v3.9.0)

Der Schritt zur offiziellen Veroeffentlichung:

- **hassfest-Kompatibilitaet** -- Einhaltung aller Home-Assistant-Validierungsregeln
- **Dokumentations-Ueberarbeitung** -- vollstaendige Neufassung der Projektdokumentation
- **Valides HACS-Release** -- korrekte Release-Tags fuer die Home Assistant Community Store Integration

---

## Phase 5 -- Cross-Home Sharing (COMPLETE ✅)

> Status: **Vollständig implementiert** (v7.26.0)

### Implemented Features

**Federated Learning & Collective Intelligence**
- Anonymisierte Muster zwischen Haushalten teilen
- Kein zentraler Server -- dezentraler Ansatz
- Lokale Modelle werden mit aggregierten Erkenntnissen verbessert, ohne Rohdaten zu versenden
- 15 API-Endpoints unter `/api/v1/federated/*`

**Sharing & Discovery**
- 7 API-Endpoints unter `/api/v1/sharing/*`
- Peer Discovery, Entity Management, Sync Management
- Konfliktlösung und Status-Abfragen

**Push Notifications**
- 9 API-Endpoints unter `/api/v1/notifications/*`
- Device-Registrierung, Push-Versand, Mark-as-Read, Clear
- Telegram-Integration für Mobile-Push

**API Integration Status**
- `Phase 5 API Integration` Tag: `v5.1.0-phase5-2026-02-23`
- Commits: `4fc8aef`, `531af5b`

### Architecture
- Neues `sharing/`-Modul im Core Add-on
- Peer Discovery über mDNS oder optionalen Rendezvous-Server
- Ende-zu-Ende-verschluesselter Transport zwischen Peers
- Lokaler Aggregator fasst eingehende Muster zusammen, bevor sie ins Modell fliessen

### Testing
- Integrationstests für alle 31 Endpoints verfügbar
- Full-flow: `GET /api/v1/sharing/status` → `POST /api/v1/notifications/send` → `POST /api/v1/federated/register`

### Notes
- Phase 5 ist stabil und produktionsreif
- Optional: Cross-Home Sharing muss in der Konfiguration explizit aktiviert werden
- `SEARXNG_ENABLED` (optional für Web-Search)

---

## Phase 6 -- Advanced ML (geplant)

> Status: Recherche / Proof-of-Concept

### On-Device Inference

- **TFLite / ONNX Runtime** fuer leichtgewichtige ML-Modelle direkt auf dem Home-Assistant-Host
- Ziel: Inferenz unter 100ms auf Raspberry Pi 4 / Intel NUC
- Modelle werden vortrainiert ausgeliefert und lokal feingetunt

### Anomaly Detection

- **Isolation Forest** zur Erkennung ungewoehnlicher Sensormuster
- Anwendungsfaelle: ploetzlicher Energieanstieg, unerwartete Tueraktivitaet, Wasserverbrauch ausserhalb der Norm
- Benachrichtigungen mit Erklaerung ("Energieverbrauch 3x hoeher als ueblich fuer Dienstag 14 Uhr")

### Zeitreihen-Prognosen

- **LSTM / Transformer-basierte Modelle** fuer Vorhersagen
- Temperaturverlauf der naechsten Stunden (Heizungsoptimierung)
- Erwarteter Energieverbrauch nach Wochentag und Wetter
- Wahrscheinlichkeit von Anwesenheit pro Raum und Zeitfenster

### Energy Load Shifting

- Automatische Optimierung: wann laufen Waschmaschine, Geschirrspueler, Wallbox?
- Berücksichtigung von PV-Ertragsprognosen und dynamischen Stromtarifen
- Ziel: Eigenverbrauchsquote maximieren, Kosten minimieren
- Integration mit bestehenden Energy-Modul-Daten

### Personalized Automation Timing

- Feinabstimmung von Automatisierungszeitpunkten basierend auf individuellem Verhalten
- "Licht im Flur geht 2 Minuten vor der ueblichen Ankunftszeit an" statt fixer Zeitpunkt
- Saisonale und wetterabhaengige Anpassungen
- Zusammenspiel mit MUPL fuer Mehrpersonenhaushalte

### Herausforderungen

- Ressourcenbeschraenkung: nicht jeder Host hat GPU oder viel RAM
- Modellgroesse vs. Genauigkeit: kompakte Modelle muessen genuegen
- Trainingszeit: inkrementelles Lernen statt vollstaendigem Neutraining

---

## Naechste Prioritaeten (kurz- bis mittelfristig)

Diese Punkte stehen auf der naechsten Arbeitsliste, unabhaengig von den grossen Phasen:

### Dashboard: Styx

- Einheitliches Dashboard, das Brain Graph, Chat und Historie zusammenfuehrt
- Visualisierung der Neuron-Aktivitaet und Mood-Verlauf
- Echtzeit-Updates ueber WebSocket
- Responsives Design fuer Tablet-Wandmontage und Mobile

### Voice Integration

- Tiefere Anbindung an den Home-Assistant Voice Assistant
- Kontextbewusste Antworten (Stimmung, Tageszeit, Raum)
- Proaktive Sprachhinweise bei wichtigen Erkenntnissen
- Unterstuetzung fuer Mehrsprachigkeit (DE/EN als Minimum)

### Kalender: Smart Scheduling

- Intelligente Terminplanung mit Stimmungsbewusstsein
- "Du hast morgen einen vollen Tag -- soll ich den Wecker 15 Minuten frueher stellen?"
- Automatische Anpassung von Beleuchtungsszenen an den Tagesablauf
- Integration mit bestehenden Kalender-Modulen und Mood Engine

### Multi-Home

- Sichere Synchronisation zwischen mehreren Wohnorten (Hauptwohnung, Ferienhaus, Buero)
- Einheitliche Steuerung ueber eine Oberflaeche
- Standortabhaengige Automatisierungen ("Ferienhaus vorheizen, wenn Anreise in 2 Stunden")
- Verschluesselte Kommunikation zwischen den Instanzen

### Performance-Optimierung

- **Connection Pooling** fuer HA-Supervisor- und Ollama-Verbindungen
- **Cache Tuning** fuer haeufig abgefragte Sensordaten und RAG-Ergebnisse
- **VectorStore-Optimierung** -- effizientere Aehnlichkeitssuche bei wachsender Datenbasis
- **Startup-Zeit** reduzieren durch lazy Loading von selten genutzten Modulen

---

## Designprinzipien fuer die Zukunft

Diese Prinzipien gelten fuer alle zukuenftigen Entwicklungen und werden nicht verhandelt:

### Local-First bleibt

PilotSuite laeuft vollstaendig lokal. Keine Cloud-Abhaengigkeit, kein externer Server fuer Kernfunktionen. Das LLM (standardmaessig `qwen3:0.6b`, optional `qwen3:4b` via Ollama) laeuft auf dem gleichen Geraet. Optionale Netzwerkfunktionen (Cross-Home Sharing, Web Search) sind immer opt-in und nie fuer den Basisbetrieb erforderlich.

### Privacy bleibt

Alle Datenverarbeitung findet auf dem Geraet statt. Keine Telemetrie, kein Tracking, keine Daten an Dritte. Wenn kuenftige Features Daten uebertragen (z.B. Federated Learning), dann nur anonymisiert, verschluesselt und mit ausdruecklicher Zustimmung. Der Nutzer behalt immer die volle Kontrolle ueber seine Daten.

### Governance bleibt

PilotSuite schlaegt vor, handelt aber nicht eigenmaechtg. Das 3-Tier-Autonomie-System (active / learning / off) gibt dem Nutzer die Wahl, wie viel Automatisierung erwuenscht ist. Auch im "active"-Modus werden sicherheitsrelevante Aktionen (Tuerschloesser, Alarmanlagen) nie ohne Bestaetigung ausgefuehrt.

### Backward Compatibility

Upgrades sollen reibungslos verlaufen. Datenbank-Migrationen werden automatisch ausgefuehrt. Konfigurationsaenderungen sind abwaertskompatibel. Veraltete APIs erhalten eine Deprecation-Phase, bevor sie entfernt werden. Ziel: `docker pull` und fertig, keine manuellen Schritte noetig.

---

## Mitmachen

PilotSuite ist ein Ein-Entwickler-Projekt, aber Feedback und Ideen aus der Community sind willkommen. Feature Requests und Bug Reports ueber GitHub Issues sind der beste Weg, die Richtung mitzugestalten.

> "Ein Smart Home soll sich anfuehlen wie ein aufmerksamer Mitbewohner -- nicht wie ein IT-Projekt."
