# H4 Fix Backlog from H2 Reconciliation

## Zweck
Konkrete Ableitung aus `H2_BLUEPRINT_RECONCILIATION.md`, damit die restliche 168h-Iteration nicht wieder unscharf wird.

## P0 — deterministische Brecher zuerst

### P0-1 NameError / kaputte Modulinitialisierung
- `copilot_core.api.v1.media_ui` — `backend_ui_bp` ist nicht definiert
- Wirkung: deterministischer Importbruch beim Registrieren
- Erfolgssignal: Modul importiert sauber, Blueprint registrierbar, Reconciliation-Eintrag verschwindet

### P0-2 fehlende Runtime-/Bridge-Module in kritischen Registrypfaden
- `copilot_core.api.v1.health`
- `copilot_core.api.v1.version`
- `copilot_core.api.v1.users`
- `copilot_core.api.v1.module_router`
- `copilot_core.api.v1.user_management`
- `copilot_core.api.v1.widget_positions`
- `copilot_core.api.v1.config`
- Wirkung: Config zeigt Endpoints an, Runtime kann sie nicht importieren
- Erfolgssignal: Module existieren oder Config referenziert stattdessen reale Zielmodule

### P0-3 harte Importbrüche durch fehlende Abhängigkeiten
- `copilot_core.api.v1.ha_events` → `copilot_core.homeassistant.websocket_client` fehlt
- `copilot_core.api.v1.learning_viz` → `copilot_core.habitus.habitus_storage` fehlt
- `copilot_core.api.v1.rag` → `NamespaceIndex` Import bricht
- Erfolgssignal: Importpfade wieder auf reale Runtime-Objekte gemappt oder Registry-Eintrag deaktiviert/umgebogen

## P1 — Attribut-Mismatch in blueprints_config

Diese Einträge importieren das Modul, erwarten aber den falschen Blueprint-Namen:
- `action_attribution_bp`
- `candidates_bp`
- `character_bp`
- `conflict_resolution_bp`
- `dashboard_bp`
- `debug_bp`
- `dev_bp`
- `graph_bp`
- `graph_ops_bp`
- `habitus_bp`
- `dashboard_cards_bp`
- `mood_bp`
- `notifications_bp`
- `search_bp`
- `security_bp`
- `swagger_ui_bp`
- `user_preferences_bp`
- `voice_context_bp`
- `weather_bp`
- weitere laut JSON-Artefakt

Erfolgssignal:
- `blueprints_config.py` zeigt nur echte Exportnamen
- H2-Driftzahl sinkt messbar

## P2 — doppelte Registrierungslogik abbauen
- `core_setup.py` enthält weiterhin mehrere manuelle Nachregistrierungsblöcke neben zentraler Config-Registrierung
- aktuell durch `register_once` entschärft, aber noch nicht architektonisch bereinigt
- Erfolgssignal: nur noch bewusst begründete Spät-Init-Blöcke; keine redundante Zweitregistrierung mehr

## Ausführungsreihenfolge
1. P0-1 `media_ui`
2. P0-2 fehlende Modulpfade in Config gegen reale Module abgleichen
3. P0-3 harte Importbrüche auflösen
4. P1 Attribut-Mismatches batchweise korrigieren
5. P2 manuelle Registrierungsreste reduzieren

## Prüfkommandos
- `python3 -m py_compile copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py`
- `python3 -m pytest -q tests/test_h1_truth_map.py tests/test_h2_blueprint_reconcile.py tests/test_api_v1_syntax_contract.py tests/test_core_wiring_contract.py`
- `python3 scripts/h2_blueprint_reconcile.py --repo . --md-out docs/analysis/H2_BLUEPRINT_RECONCILIATION.md --json-out docs/analysis/h2_blueprint_reconciliation.json`
