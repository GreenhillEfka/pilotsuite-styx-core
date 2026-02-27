# PilotSuite Roadmap

> Zuletzt aktualisiert: Februar 2026 -- v10.4.0

PilotSuite ist ein Ein-Entwickler-Projekt mit ambitionierten Zielen. Diese Roadmap beschreibt den bisherigen Weg, die aktuelle Entwicklung und die geplante Zukunft. Alle Zeitangaben sind Richtwerte -- Prioritaeten koennen sich je nach Community-Feedback und technischer Machbarkeit verschieben.

**Aktueller Stand:** v10.4.0 -- 36 Module, 586+ Core-Tests, 579+ HA-Tests, 55+ API-Endpunkte

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

## Phase 5 -- Cross-Home Sharing (COMPLETE)

> Status: **Vollstaendig implementiert** (v7.26.0)

### Implemented Features

**Federated Learning & Collective Intelligence**
- Anonymisierte Muster zwischen Haushalten teilen
- Kein zentraler Server -- dezentraler Ansatz
- Lokale Modelle werden mit aggregierten Erkenntnissen verbessert, ohne Rohdaten zu versenden
- 15 API-Endpoints unter `/api/v1/federated/*`

**Sharing & Discovery**
- 7 API-Endpoints unter `/api/v1/sharing/*`
- Peer Discovery, Entity Management, Sync Management
- Konfliktloesung und Status-Abfragen

**Push Notifications**
- 9 API-Endpoints unter `/api/v1/notifications/*`
- Device-Registrierung, Push-Versand, Mark-as-Read, Clear
- Telegram-Integration fuer Mobile-Push

**API Integration Status**
- `Phase 5 API Integration` Tag: `v5.1.0-phase5-2026-02-23`
- Commits: `4fc8aef`, `531af5b`

### Architecture
- Neues `sharing/`-Modul im Core Add-on
- Peer Discovery ueber mDNS oder optionalen Rendezvous-Server
- Ende-zu-Ende-verschluesselter Transport zwischen Peers
- Lokaler Aggregator fasst eingehende Muster zusammen, bevor sie ins Modell fliessen

### Testing
- Integrationstests fuer alle 31 Endpoints verfuegbar
- Full-flow: `GET /api/v1/sharing/status` -> `POST /api/v1/notifications/send` -> `POST /api/v1/federated/register`

### Notes
- Phase 5 ist stabil und produktionsreif
- Optional: Cross-Home Sharing muss in der Konfiguration explizit aktiviert werden
- `SEARXNG_ENABLED` (optional fuer Web-Search)

---

## Phase 6 -- Conversation & RAG (COMPLETE)

> Status: **Vollstaendig implementiert** (v8.x)

### Implemented Features

**OpenAI-kompatibles Chat-Interface**
- Vollstaendige Chat-API mit Streaming-Support
- Conversation Memory mit konfigurierbarer Tiefe
- Kontextbewusste Antworten basierend auf Haushaltsdaten

**RAG Pipeline**
- VectorStore mit EmbeddingEngine fuer semantische Suche
- Dokument-Ingestion und Chunking fuer Haushaltswissen
- Relevanz-Ranking und Kontext-Injection in LLM-Prompts

**Tool Calling & MCP Server**
- Function-Calling-Interface fuer LLM-gesteuerte Aktionen
- MCP (Model Context Protocol) Server fuer externe Tool-Integration
- Strukturierte Ausgabe und Validierung von Tool-Aufrufen

**LLM Integration**
- Ollama-Backend (Standard: `qwen3:0.6b`, optional `qwen3:4b`)
- Cloud-Fallback fuer leistungsstaerkere Modelle
- Circuit Breaker fuer robuste LLM-Verbindungen

---

## Phase 7 -- Architecture Overhaul (COMPLETE)

> Status: **Vollstaendig implementiert** (v9.0 - v9.2)

### Implemented Features

**EventBus**
- Zentraler Event-Bus fuer entkoppelte Kommunikation zwischen Modulen
- Publish/Subscribe-Muster mit Deduplication und Idempotency
- Ersetzt direkte Modul-zu-Modul-Aufrufe

**4-Tier Module Classification**
- Formale Klassifizierung aller Module in 4 Stufen (Core, Standard, Extended, Experimental)
- Klare Abhaengigkeitsregeln zwischen den Tiers
- Grundlage fuer kontrolliertes Wachstum der Modullandschaft

**NeuronTagResolver & Tags v2**
- Automatische Tag-Aufloesung fuer Neuron-Bewertungen
- Tags v2 mit hierarchischem Namespace und Vererbung
- Verbesserte Entity-Klassifizierung ueber Tags

**Entity Search v2**
- Erweiterte Suchfunktionalitaet ueber alle Entities
- Fuzzy-Matching und semantische Suche
- Filterung nach Tags, Zonen, Typen und Zustand

**Bidirectional Zone Sync**
- Zwei-Wege-Synchronisation zwischen Core und HA-Integration
- Automatische Zonen-Erkennung und -Zuordnung
- Konsistente Zonen-Daten ueber beide Systeme hinweg

---

## Phase 8 -- Consolidation & Auto-Setup (COMPLETE)

> Status: **Vollstaendig implementiert** (v10.0 - v10.4)

### Implemented Features

**Zone Automation Controller**
- Zonenbasierte Automatisierungssteuerung mit Governance-Workflow
- Regelbasierte und ML-gestuetzte Entscheidungen pro Zone
- Integration mit Mood Engine und Neurons fuer kontextbewusste Automatisierung

**Mood Engine v3.0**
- 6 diskrete Zustaende: relax, focus, active, night, away, neutral (Softmax + EMA Hysterese)
- 5 kontinuierliche Dimensionen: comfort, frugality, joy, energy, stress (je 0.0-1.0)
- Entity Dependencies mit formaler Rollenzuordnung (motion, illuminance, media, climate, presence, energy_meter)
- Sigmoid-Aktivierungsfunktionen und Gaussian Comfort Curves
- SQLite WAL-Mode Persistenz mit 30-Tage Rolling Window

**Blueprint Consolidation**
- Zusammenfuehrung und Bereinigung der Flask-Blueprint-Struktur
- Einheitliche Registrierung ueber `api/v1/blueprint.py` und `core_setup.register_blueprints()`
- 45+ Blueprints sauber organisiert

**Auto-Setup**
- Automatische Ersterkennung und Konfiguration von Entities
- Intelligente Defaults basierend auf Entity-Typ und Kontext
- Reduzierter manueller Aufwand bei Erstinstallation

**ML Entity Classifier**
- Maschinelles Lernen zur automatischen Klassifizierung neuer Entities
- Erkennung von Entity-Typ, Funktion und optimaler Zonenzuordnung
- Lernfaehig: verbessert sich mit Nutzerfeedback

**Sidebar Dashboard Panel**
- Integriertes Dashboard-Panel in der Home-Assistant-Sidebar
- Schnellzugriff auf PilotSuite-Status, Neuron-Aktivitaet und Mood-Verlauf
- Neuronenlayer-Visualisierung mit 3-Ring-Darstellung

### Stats (v10.4.0)
- 36 Module
- 586+ Core-Tests, 579+ HA-Tests
- 55+ API-Endpunkte (45+ Flask Blueprints)
- 24+ Services via `init_services()`, alle mit Error Boundary
- 17 PilotSuite Hub Engines mit granularer Fehler-Isolation

---

## Phase 9 -- Advanced ML (geplant)

> Status: **Teilweise begonnen** -- einzelne Bausteine existieren bereits

### Anomaly Detection -- TEILWEISE IMPLEMENTIERT

- **Isolation Forest** zur Erkennung ungewoehnlicher Sensormuster
- v10.1.6 brachte Anomaly Detection ins Zone Management Dashboard
- Anwendungsfaelle: ploetzlicher Energieanstieg, unerwartete Tueraktivitaet, Wasserverbrauch ausserhalb der Norm
- Benachrichtigungen mit Erklaerung ("Energieverbrauch 3x hoeher als ueblich fuer Dienstag 14 Uhr")
- Geplant: Erweiterung auf weitere Sensorkategorien und verbesserte Modellgenauigkeit

### Energy Load Shifting -- IN ARBEIT

- Energy-Modul existiert bereits mit Shifting-Empfehlungen
- Automatische Optimierung: wann laufen Waschmaschine, Geschirrspueler, Wallbox?
- Beruecksichtigung von PV-Ertragsprognosen und dynamischen Stromtarifen
- Ziel: Eigenverbrauchsquote maximieren, Kosten minimieren
- Geplant: Vollstaendige Automatisierung mit Governance-Workflow

### On-Device Inference -- GEPLANT

- **TFLite / ONNX Runtime** fuer leichtgewichtige ML-Modelle direkt auf dem Home-Assistant-Host
- Ziel: Inferenz unter 100ms auf Raspberry Pi 4 / Intel NUC
- Modelle werden vortrainiert ausgeliefert und lokal feingetunt

### Zeitreihen-Prognosen -- GEPLANT

- **LSTM / Transformer-basierte Modelle** fuer Vorhersagen
- Temperaturverlauf der naechsten Stunden (Heizungsoptimierung)
- Erwarteter Energieverbrauch nach Wochentag und Wetter
- Wahrscheinlichkeit von Anwesenheit pro Raum und Zeitfenster

### Personalized Automation Timing -- GEPLANT

- Feinabstimmung von Automatisierungszeitpunkten basierend auf individuellem Verhalten
- "Licht im Flur geht 2 Minuten vor der ueblichen Ankunftszeit an" statt fixer Zeitpunkt
- Saisonale und wetterabhaengige Anpassungen
- Zusammenspiel mit MUPL fuer Mehrpersonenhaushalte

### Herausforderungen

- Ressourcenbeschraenkung: nicht jeder Host hat GPU oder viel RAM
- Modellgroesse vs. Genauigkeit: kompakte Modelle muessen genuegen
- Trainingszeit: inkrementelles Lernen statt vollstaendigem Neutraining

---

## Phase 10 -- Enhanced Intelligence (geplant)

> Status: **Geplant** -- aufbauend auf Phase 6-9

### Multi-Turn Conversations mit persistentem Gedaechtnis

- Erweiterung der Conversation Memory ueber Sessions hinweg
- Langzeitgedaechtnis fuer wiederkehrende Themen und Praeferenzen
- Kontexttransfer zwischen Gespraechen ("Letzte Woche hast du nach dem Energieverbrauch gefragt...")

### Voice-First Interaction Patterns

- Sprachgesteuerte Interaktion als primaerer Zugangskanal
- Proaktive Sprachhinweise bei wichtigen Erkenntnissen
- Natuerliche Dialogfuehrung mit Rueckfragen und Bestaetigung
- Unterstuetzung fuer Mehrsprachigkeit (DE/EN als Minimum)

### Deeper RAG mit Haushaltswissen

- Erweiterung der RAG Pipeline um tieferes Haushaltswissen
- Automatische Dokumentation von Geraetehistorie und Wartungszyklen
- Kontextanreicherung mit Langzeittrends und saisonalen Mustern

### Cross-Home Pattern Sharing Activation

- Aufbauend auf Phase 5 Infrastruktur: aktive Nutzung der Sharing-Mechanismen
- Anonymisierte Mustererkennung ueber Haushaltsgrenzen hinweg
- Opt-in Teilnahme an Collective-Intelligence-Netzwerk

### Policy Controls per Risk Class

- Feingranulare Steuerung von Automatisierungen nach Risikoklasse
- Differenzierung: Beleuchtung (niedrig) vs. Tuerschloesser (hoch) vs. Heizung (mittel)
- Nutzer definiert Autonomie-Level pro Risikoklasse
- Audit-Trail fuer alle autonomen Aktionen

### Large-Home Scalability (100+ Entities)

- Performance-Optimierung fuer grosse Installationen mit 100+ Entities
- Effizientes Graph-Management bei hoher Entity-Dichte
- Lazy Loading und partielle Updates fuer schnelle Reaktionszeiten
- Skalierbare Event-Verarbeitung ohne Latenzanstieg

---

## Naechste Prioritaeten (kurz- bis mittelfristig)

Diese Punkte stehen auf der naechsten Arbeitsliste, unabhaengig von den grossen Phasen:

### Dashboard: Styx -- TEILWEISE UMGESETZT

- Sidebar Dashboard Panel existiert mit Neuron-Aktivitaet und Status-Uebersicht
- Brain Graph Visualisierung mit vis.js-Export vorhanden
- Neuronenlayer-Darstellung mit 3-Ring-Visualisierung implementiert
- **Offen:** Einheitliches Dashboard, das Brain Graph, Chat und Historie zusammenfuehrt
- **Offen:** Echtzeit-Updates ueber WebSocket
- **Offen:** Responsives Design fuer Tablet-Wandmontage und Mobile

### Voice Integration -- GEPLANT

- Tiefere Anbindung an den Home-Assistant Voice Assistant
- Kontextbewusste Antworten (Stimmung, Tageszeit, Raum)
- Proaktive Sprachhinweise bei wichtigen Erkenntnissen
- Unterstuetzung fuer Mehrsprachigkeit (DE/EN als Minimum)

### Kalender: Smart Scheduling -- GEPLANT

- Intelligente Terminplanung mit Stimmungsbewusstsein
- "Du hast morgen einen vollen Tag -- soll ich den Wecker 15 Minuten frueher stellen?"
- Automatische Anpassung von Beleuchtungsszenen an den Tagesablauf
- Integration mit bestehenden Kalender-Modulen und Mood Engine

### Multi-Home -- INFRASTRUKTUR VORHANDEN

- Phase 5 liefert die technische Basis (Sharing, Peer Discovery, Federated Learning)
- **Offen:** Sichere Synchronisation zwischen mehreren Wohnorten (Hauptwohnung, Ferienhaus, Buero)
- **Offen:** Einheitliche Steuerung ueber eine Oberflaeche
- **Offen:** Standortabhaengige Automatisierungen ("Ferienhaus vorheizen, wenn Anreise in 2 Stunden")
- **Offen:** Verschluesselte Kommunikation zwischen den Instanzen

### Performance-Optimierung -- LAUFEND

- **Connection Pooling** -- UMGESETZT fuer HA-Supervisor- und Ollama-Verbindungen
- **Cache Tuning** -- LAUFEND fuer haeufig abgefragte Sensordaten und RAG-Ergebnisse
- **VectorStore-Optimierung** -- effizientere Aehnlichkeitssuche bei wachsender Datenbasis
- **Startup-Zeit** reduzieren durch lazy Loading von selten genutzten Modulen

---

## Designprinzipien fuer die Zukunft

Diese Prinzipien gelten fuer alle zukuenftigen Entwicklungen und werden nicht verhandelt:

### Local-First bleibt

PilotSuite laeuft vollstaendig lokal. Keine Cloud-Abhaengigkeit, kein externer Server fuer Kernfunktionen. Das LLM (standardmaessig `qwen3:0.6b`, optional `qwen3:4b` via Ollama) laeuft auf dem gleichen Geraet. Optionale Netzwerkfunktionen (Cross-Home Sharing, Web Search) sind immer opt-in und nie fuer den Basisbetrieb erforderlich.

### Privacy bleibt

Alle Datenverarbeitung findet auf dem Geraet statt. Keine Telemetrie, kein Tracking, keine Daten an Dritte. Wenn kuenftige Features Daten uebertragen (z.B. Federated Learning), dann nur anonymisiert, verschluesselt und mit ausdruecklicher Zustimmung. Der Nutzer behaelt immer die volle Kontrolle ueber seine Daten.

### Governance bleibt

PilotSuite schlaegt vor, handelt aber nicht eigenmaechtig. Das 3-Tier-Autonomie-System (active / learning / off) gibt dem Nutzer die Wahl, wie viel Automatisierung erwuenscht ist. Auch im "active"-Modus werden sicherheitsrelevante Aktionen (Tuerschloesser, Alarmanlagen) nie ohne Bestaetigung ausgefuehrt.

### Backward Compatibility

Upgrades sollen reibungslos verlaufen. Datenbank-Migrationen werden automatisch ausgefuehrt. Konfigurationsaenderungen sind abwaertskompatibel. Veraltete APIs erhalten eine Deprecation-Phase, bevor sie entfernt werden. Ziel: `docker pull` und fertig, keine manuellen Schritte noetig.

---

## Mitmachen

PilotSuite ist ein Ein-Entwickler-Projekt, aber Feedback und Ideen aus der Community sind willkommen. Feature Requests und Bug Reports ueber GitHub Issues sind der beste Weg, die Richtung mitzugestalten.

> "Ein Smart Home soll sich anfuehlen wie ein aufmerksamer Mitbewohner -- nicht wie ein IT-Projekt."
