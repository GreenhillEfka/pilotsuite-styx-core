# Changelog

## [v15.3.43] - 2026-04-02

### 🧩 Slice 31 — Zone-Scoped Proposal Lifecycle Context Surface

- `copilot_core.core.proposal_lifecycle_read_model` fuehrt jetzt einen kanonischen `ProposalLifecycleContextBlockV1` ein, der dieselbe Proposal-/Action-/Closure-/Settlement-Wahrheit zonenscharf als Kontextblock mit Delta-Cursor und kompakten Context-Lines materialisiert.
- `copilot_core.api.v1.zone_dashboard` bettet Proposal-Lifecycle jetzt direkt in Zone-Liste, Zone-Detail und den globalen Dashboard-Kontext ein: jede Zone bekommt eine eigene `proposal_lifecycle`-Surface, waehrend `global.proposal_lifecycle.zone_contexts` geaenderte Zonen fuer Poller dedupliziert aus derselben Lifecycle-Logik ausleitet.
- Dashboard-Poller koennen Proposal-Deltas jetzt explizit ueber `proposal_lifecycle_since` fuer Listen- und Detail-Surfaces abfragen, ohne eine zweite zonenspezifische Proposal-Aggregation aufzubauen.
- Contract-Coverage prueft den neuen Kontextblock, globale Zone-Feeds sowie Delta-Verhalten auf Zone-Detail-/Dashboard-Surfaces; die Dashboard-Testhilfe setzt zusaetzlich den Follow-up-Dispatch-Store pro Lauf zurueck, damit Proposal-Revisionen nicht durch fremde Worker-Revisionen verdeckt werden.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`, `copilot_core/rootfs/usr/src/app/copilot_core/VERSION`) auf `15.3.43` harmonisiert.
- Validiert mit: `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py tests/test_proposal_lifecycle_status_contract.py tests/test_proposal_lifecycle_api.py` → `46 passed`.

## [v15.3.42] - 2026-04-02

### 🧩 Slice 30 — Proposal Lifecycle Status Surface

- `copilot_core.core.proposal_lifecycle_read_model` materialisiert jetzt eine kanonische `ProposalLifecycleStatusV1`-/`ProposalLifecycleStatusSummaryV1`-Surface direkt aus bestehender Proposal-/Action-/Closure-/Follow-up-Truth, ohne eine separate Timeline-Tabelle einzufuehren.
- `copilot_core.api.v1.proposals` exponiert mit `GET /api/v1/proposals/status` und `GET /api/v1/proposals/<proposal_id>/status` revisionsscharfe Worker-/Dashboard-faehige Lifecycle-Staende (`suggested`, `accepted`, `executed`, `failed`, `follow_up_open`, `settled`) und korrigiert zugleich die Proposal-Routen auf den kanonischen `/api/v1/proposals`-Prefix.
- Dashboard-Global-Kontext (`copilot_core.api.v1.zone_dashboard._build_global_context`) und `ChatHandler._build_home_context()` spiegeln dieselbe Proposal-Lifecycle-Wahrheit jetzt als kompakte Summary zurueck statt aus parallelen Hilfslogiken.
- Contract-Coverage deckt die Status-Ableitung ueber Suggestion-, Closure-, Receipt-/Claim- und Settlement-Zustaende sowie die Rueckspiegelung in Proposal-API, Dashboard und Chat ab.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`, `copilot_core/rootfs/usr/src/app/copilot_core/VERSION`) auf `15.3.42` harmonisiert.
- Validiert mit: `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py tests/test_proposal_lifecycle_status_contract.py tests/test_proposal_lifecycle_api.py` → `41 passed`.

## [v15.3.41] - 2026-04-02

### 🧩 Slice 29 — Closure Follow-Up Claim Settlement / Release Surface

- `copilot_core.api.v1.notifications` materialisiert jetzt explizite Worker-Lease-Abschluesse aus derselben Claim-/Receipt-Wahrheit: `POST /notifications/action-closures/dispatch/settle` kanonisiert `released`, `abandoned` und `settled` fuer bestehende Claims, optional mit atomarem Receipt-/Retry-/Escalation-Update statt einer zweiten Queue-Historie.
- `GET /notifications/action-closures/settlements` liefert eine truth-backed `ActionClosureFollowUpSettlementSummaryV1` mit monotone `settlement_revision`, Worker-/Delivery-Breakdowns, Receipt-Outcomes und Delta-Sicht ueber Claim-Abschluesse.
- `ActionClosureFollowUpClaimV1` traegt jetzt eine explizite `settlement`-Struktur; Lease-State unterscheidet aktive, released und settled Claims sauber, sodass Reassignability und Receipt-Anbindung aus derselben Claim-Surface gelesen werden.
- `ActionClosureFollowUpDispatchV1`, `ActionClosureFollowUpReceiptSummaryV1`, Notification-Digest, Dashboard-Global-/Zonen-Kontext und `ChatHandler._build_home_context()` spiegeln dieselbe Settlement-/Release-Wahrheit zurueck und beschreiben abgeschlossene bzw. abgebrochene Follow-ups ohne Parallel-Aggregation.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`, `copilot_core/rootfs/usr/src/app/copilot_core/VERSION`) auf `15.3.41` harmonisiert.
- Validiert mit: `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `35 passed`.

## [v15.3.40] - 2026-04-02

### 🧩 Slice 28 — Closure Follow-Up Claim / Lease Surface

- `copilot_core.api.v1.notifications` materialisiert jetzt eine kanonische Claim-/Lease-Surface fuer Closure-Follow-up-Worker: `POST /notifications/action-closures/dispatch/claim` vergibt revisionsscharfe `ActionClosureFollowUpClaimV1`-Claims mit Lease-Ablauf, Konfliktantworten und optionalem `force_reassign` auf derselben Dispatch-Wahrheit.
- `GET /notifications/action-closures/claims` liefert eine truth-backed `ActionClosureFollowUpClaimSummaryV1` mit monotone `claim_revision`-Delta, Worker-/Delivery-Breakdowns sowie expliziten Counts fuer aktive, abgelaufene und neu zuweisbare Claims.
- `ActionClosureFollowUpDispatchV1` und einzelne Dispatch-Kandidaten betten den aktuellen Claim-/Lease-Stand direkt ein; konkurrierende Worker sehen damit dieselbe Lock-/Reassign-Sicht statt eine zweite Queue-Schattenlogik.
- `ActionClosureFollowUpReceiptSummaryV1` fuehrt Claim-, Lease- und Reassign-Zustand in dieselbe Receipt-/Digest-/Dashboard-/Chat-Surface zurueck, sodass Lease-Ablauf und eskalationsrelevante Problemfaelle ueberall konsistent beschrieben werden.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`, `copilot_core/rootfs/usr/src/app/copilot_core/VERSION`) auf `15.3.40` harmonisiert.
- Validiert mit: `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `32 passed`.

## [v15.3.39] - 2026-04-02

### 🧩 Slice 27 — Closure Follow-Up Delivery SLA Surface

- `copilot_core.api.v1.notifications` leitet jetzt eine kanonische Delivery-SLA-/Staleness-Surface aus derselben Closure-/Dispatch-/Receipt-Wahrheit ab: `GET /notifications/action-closures/sla` materialisiert ueberfaellige offene Follow-ups, veraltete Retries und faellige Eskalationen zonen-, worker- und delivery-mode-scharf.
- `ActionClosureFollowUpReceiptSummaryV1` bettet die neue `ActionClosureFollowUpSLASummaryV1` direkt ein; Receipt- und Digest-Surfaces behalten damit eine einzige Follow-up-Truth, statt eine zweite Notification-Schattenlogik aufzubauen.
- Worker-Scopes (`worker=`) und Retry-/Escalation-SLA werden jetzt aus Closure-`updated_at`, Receipt-Status und optionalen `next_retry_at`-Zeitpunkten abgeleitet, sodass ein frisch geschriebenes Receipt veraltete Follow-ups nicht mehr kuenstlich „gesund“ aussehen laesst.
- Chat-/Dashboard-Kontexte lesen ueber dieselbe Receipt-Summary jetzt auch veraltete Retries/ueberfaellige Follow-ups mit, und die Contract-Surface deckt explizit Worker-Scopes sowie SLA-Kategorien ab.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`) auf `15.3.39` harmonisiert.
- Validiert mit: `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `29 passed`.

## [v15.3.37] - 2026-04-02

### 🧩 Slice 26 — Closure Follow-Up Receipt Surface

- `copilot_core.api.v1.notifications` fuehrt jetzt eine kanonische Receipt-Surface fuer Closure-Follow-up-Worker ein: `POST /notifications/action-closures/dispatch/receipt` materialisiert Delivery-/Queue-/Retry-/Escalation-Ergebnisse pro Dispatch-Kandidat, waehrend `GET /notifications/action-closures/receipts` dieselbe Wahrheit als `ActionClosureFollowUpReceiptSummaryV1` mit monotone `receipt_revision`-Delta ausleitet.
- Dispatch-Acks bleiben nicht mehr isoliert im Worker-Layer: `ActionClosureFollowUpDispatchStore` fuehrt Ack-, Receipt-, Retry- und Escalation-State pro dedupliziertem Closure-Stand zusammen, sodass Notification-Jobs und Reminder-Queues dieselbe Rueckkanal-Wahrheit lesen.
- `ActionClosureNotificationDigestV1` und `ActionClosureFollowUpDispatchV1` betten die neue Receipt-Summary direkt ein; Dashboard-Global-/Zonen-Kontext sowie `ChatHandler._build_home_context()` spiegeln Follow-up-Zustellung, offene Retries und Eskalationen damit ohne zweite Aggregationslogik zurueck.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`) auf `15.3.37` harmonisiert.
- Validiert mit: `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `27 passed`.

## [v15.3.36] - 2026-04-02

### 🧩 Slice 25 — Closure Follow-Up Dispatch Worker

- `copilot_core.api.v1.notifications` exponiert jetzt eine deduplizierte Worker-Surface unter `GET /notifications/action-closures/dispatch`, die dieselbe kanonische `ActionClosureNotificationDigestV1`-Wahrheit fuer `notification_job` und `reminder_queue` in delivery-faehige Dispatch-Kandidaten uebersetzt.
- Neue `ActionClosureFollowUpDispatchV1`- und `ActionClosureFollowUpDispatchCandidateV1`-Payloads liefern `delivery_mode`, `cursor`, `counts`, `dedupe_key`, `closure_revision` und queue-spezifische Delivery-Metadaten, ohne eine zweite Closure-Aggregationslogik aufzubauen.
- `POST /notifications/action-closures/dispatch/ack` bestaetigt versendete Kandidaten jetzt revisionsscharf; bestaetigte Follow-ups bleiben fuer denselben Closure-Stand unterdrueckt und tauchen erst nach einer echten Closure-Aenderung wieder auf.
- `copilot_core.core.action_closure_read_model` fuehrt die Closure-Revision jetzt bis in kompakte Recent-Closure-Eintraege durch, damit Notification-/Worker-Surfaces denselben monotonen Cursor fuer Dedup/Ack nutzen koennen.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`) auf `15.3.36` harmonisiert.
- Validiert mit: `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `27 passed`.

## [v15.3.35] - 2026-04-01

### 🧩 Slice 24 — Closure-Aware Notification Digest

- `copilot_core.api.v1.notifications` kann Digest- und Pending-Surfaces jetzt optional mit kanonischen `ActionClosure`-Follow-ups anreichern (`include_action_closures=true`), inklusive `zone_id`-Scope, `action_closure_since`-Cursor und denselben Delta-Informationen aus der Closure-Truth.
- Neue `ActionClosureNotificationDigestV1`-Payloads exponieren `revision`, `latest_change_at`, Outcome-Counts und konkrete Follow-up-Eintraege fuer offene bzw. problematische Closures, damit Notification-/Digest-Worker keine eigene Closure-Aggregation mehr bauen muessen.
- `copilot_core.api.security.get_auth_token()` priorisiert jetzt den aktuellen `COPILOT_AUTH_TOKEN` strikt vor dem 60s-Cache, damit Test- und Worker-Kontexte mit frischen Env-Tokens nicht gegen stale Cache-Werte laufen.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`) auf `15.3.35` harmonisiert.
- Validiert mit: `pytest -q tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `24 passed`.

## [v15.3.34] - 2026-04-01

### 🧩 Slice 23 — Action Closure Delta Surface

- `copilot_core.action_closure` fuehrt jetzt eine monotone Closure-Revision pro Accept-/Feedback-/Execution-Aenderung, sodass Summary-, Context- und Listen-Surfaces inkrementell gegen denselben kanonischen Cursor pollen koennen.
- `copilot_core.core.action_closure_read_model` erweitert `ActionClosureSummaryV1` und `ActionClosureContextBlockV1` um `revision`, `latest_change_at` und einen eingebetteten `ActionClosureDeltaV1`-Block mit `since_revision`, `changed`, `changed_count` und delta-spezifischen Recent-Closures.
- `/api/v1/action-closures`, `/summary` und `/context` akzeptieren jetzt `?since=<revision>`; Dashboard-/Zone-Detail-Surfaces akzeptieren `?action_closure_since=<revision>` und leiten zonenspezifische Delta-Zustaende fuer inkrementelle Poller durch.
- Die globale Dashboard-Action-Closure-Surface exponiert jetzt `revision`, `freshness` und `delta`; systemweite `zone_contexts` werden bei Delta-Abfragen auf wirklich geaenderte Closure-Zonen reduziert statt alle Zonen erneut auszuleiten.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`) auf `15.3.34` harmonisiert.
- Validiert mit: `pytest -q tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `22 passed`.

## [v15.3.33] - 2026-04-01

### 🧩 Slice 22 — Zone-Scoped Closure Feed for Dashboard/System Context

- `copilot_core.api.v1.zone_dashboard` speist die kanonische `ActionClosureContextBlockV1`-Surface jetzt direkt in Dashboard-Zonenlisten und Zone-Detailantworten ein, sodass Dashboard-Consumer dieselbe Closure-Wahrheit zonenspezifisch lesen koennen statt nur globale Zaehler.
- Der globale Dashboard-Kontext exponiert neben der bestehenden Gesamtzusammenfassung jetzt `zone_contexts` und `zones_with_closures`, also eine systemweite, zonenspezifische Closure-Ausleitung aus derselben kanonischen Read-Model-Schicht.
- `copilot_core.core.action_closure_read_model` exportiert `resolve_zone_name` oeffentlich, damit Dashboard-/System-Kontext dieselbe Friendly-Name-Aufloesung nutzt wie Chat und Voice statt eigene Slug-Heuristiken zu duplizieren.
- Contract-Tests decken jetzt sowohl die systemweite Zone-Context-Ausleitung als auch die zonenspezifische Dashboard-/Detail-Surface fuer echte Truth-Zonen ab.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`) auf `15.3.33` harmonisiert.
- Validiert mit: `pytest -q tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py` → gruen.

## [v15.3.32] - 2026-04-01

### 🧩 Slice 21 — Zone-Scoped Closure Context for Voice/Chat

- `build_action_closure_context_block` akzeptiert jetzt einen expliziten `zone_name`-Parameter sowie einen optionalen `zone_id`-Filter, um Closure-Zusammenfassungen zonenspezifisch auszuleiten statt nur global.
- `_resolve_zone_name` leitet aus einem `zone_id`-Slug (z.B. `zone:living`) automatisch einen menschenlesbaren Zonennamen ab, sodass Chat/Voice auch ohne expliziten `zone_name` einen friendly Context-label erhalten.
- `_check_action_followups` in `ProactiveVoiceHints` leitet den `VoiceContext.zone_name` direkt an `build_action_closure_context_block` weiter, damit proaktive Voice-Hinweise zonenspezifisch auf dieselbe kanonische Closure-Wahrheit zugreifen.
- `ChatHandler._build_home_context` nimmt jetzt einen `zone_name`-Parameter entgegen und führt ihn an `build_action_closure_context_block` durch, sodass Chat-Closure-Zeilen zonenspezifisch aufgeloest werden koennen.
- Contract-Tests validieren die zonenspezifische Filterung und die automatische Zone-ID-Aufloesung fuer Chat- und Voice-Surfaces.
- Versionsartefakte (`copilot_core/manifest.json`, `copilot_core/config.yaml`) auf `15.3.32` harmonisiert.

## [v15.3.31] - 2026-04-01

### 🧩 Slice 20 — Closure-Aware Voice Follow-Up Hints

- `copilot_core.voice.proactive` liest fuer proaktive Voice-Hinweise jetzt direkt die kanonische `ActionClosureContextBlockV1`-Surface und erzeugt daraus outcome-aware Follow-up-Hints statt separater Sonderlogik.
- Neuer Hint-Typ `action_follow_up` hebt problematische Closures mit hoher Prioritaet hervor und meldet offene Closures als proaktive Status-Nachfrage mit derselben Closure-/Summary-Wahrheit.
- `GET /api/v1/voice/hints` exponiert den Closure-Summary- und Recent-Closure-Kontext jetzt stabil im Hint-Payload, damit Voice-Consumer den Follow-up-Grund nachvollziehen koennen.
- Contract-Coverage sichert sowohl die direkte Hint-Generierung als auch die Voice-API-Surface gegen dieselbe Closure-Historie ab.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`) auf `15.3.31` harmonisiert.
- Validiert mit: `pytest -q tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_voice_action_closure_hints_contract.py tests/test_voice_policy_contract.py` → `13 passed`.

## [v15.3.30] - 2026-04-01

### 🧩 Slice 19 — Closure-Driven Learning Feedback Loop

- `copilot_core.action_closure` liefert jetzt eine filterbare Lernzusammenfassung (`accepted`, positive/negative Feedback-Signale, Execution-Outcomes, normalisierter `score`, `priority_bias`) aus derselben kanonischen Closure-Historie statt separater Feature-Heuristiken.
- `copilot_core.predictive.automation_engine` koppelt Closure-Signale in Confidence, Reasoning, Source-Signals und Evidence zurück: erfolgreiche Closures verstärken Pattern-Matches, problematische Outcomes dämpfen sie nachvollziehbar.
- `copilot_core.habitus_miner.zone_mining` verknüpft Proposal-Regeln mit Closure-Metadaten (`rule_a`, `rule_b`) und priorisiert Regelvorschläge dadurch nach realen Accept/Execution-Ergebnissen statt nur nach Confidence/Score.
- `copilot_core.multizone.coordination_engine` berechnet für Pending-Actions jetzt `learning_signals`, `priority_bias` und `effective_priority`, sodass Konfliktauflösung dieselbe Closure-Lernspur nutzt wie Predictive und Habitus.
- `copilot_core.api.v1.habitus` persistiert beim Accept die kanonischen Regel-Keys jetzt belastbar auch ohne separaten Trigger-Fallback; damit bleibt Closure-basiertes Re-Ranking für Habit-Policies konsistent.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`) auf `15.3.30` harmonisiert.
- Validiert mit: `pytest -q tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_action_closure_learning_contract.py tests/test_predictive_automation.py tests/test_predictive_api_contract.py tests/test_multizone_coordination.py tests/test_multizone_blueprint_contract.py tests/test_multizone_runtime_contract.py tests/test_habitus_accept_contract.py` → `58 passed`.

## [v15.3.29] - 2026-04-01

### 🧩 Slice 18 — Action Closure Summary / Context Surface

- `copilot_core.core.action_closure_read_model` liefert jetzt eine kanonische `ActionClosureSummaryV1`- und `ActionClosureContextBlockV1`-Surface: Action-Closures werden nicht mehr nur gespeichert, sondern als aggregierte Outcome-/Feedback-/Source-/Zone-/Module-Summaries konsumierbar.
- `copilot_core.api.v1.action_closure` ergänzt `GET /api/v1/action-closures/summary` und `GET /api/v1/action-closures/context`, inklusive derselben Filter (`source`, `zone_id`, `module_id`, `state`, `action_id`, `proposal_id`) wie die Listen-Surface.
- Dashboard-Global-Context (`zone_dashboard`) exponiert Closure-/Outcome-Zustand jetzt als kompakten `action_closures`-Block mit offenen/erfolgreichen/problematischen Counts, Highlights und Recent-Items.
- `copilot_core.styx.chat_handler` zieht dieselbe Closure-Kontext-Surface jetzt in den Live-Hauskontext ein, damit Chat-Antworten den aktuellen Feedback-/Execution-Stand kanonisch erklären koennen.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, Runtime-VERSION, `copilot_core/config.yaml`, `copilot_core/manifest.json`) auf `15.3.29` harmonisiert.
- Validiert mit: `pytest -q tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_voice_policy_contract.py tests/test_predictive_api_contract.py tests/test_multizone_runtime_contract.py tests/test_habitus_accept_contract.py` → `17 passed`.

## [v15.3.28] - 2026-04-01

### 🧩 Slice 17 — Canonical Action Closure Surface

- `copilot_core.action_closure` ergänzt eine einzige kanonische `ActionClosureV1`-Spur für Proposal→Action→Runtime: akzeptierte Aktionen können jetzt auf derselben Surface Feedback-Events und Execution-Outcomes sammeln, statt pro Feature eigene Rückmeldepfade zu erfinden.
- Neue REST-Surface `/api/v1/action-closures/*` erlaubt listing, detail lookup sowie das nachträgliche Anhängen von User-Feedback und Runtime-Ausführungsresultaten an dieselbe Closure-ID.
- `copilot_core.api.v1.voice`, `copilot_core.api.v1.predictive` und `copilot_core.api.v1.habitus` materialisieren beim Confirm/Accept jetzt sofort eine kanonische `action_closure` neben `ProposalIntentV1`, `ActionIntentV1` und dem HA-Handoff.
- `copilot_core.multizone.coordination_engine` hängt Multi-Zone-Pending-Actions jetzt an dieselbe Closure-Surface: Pending-Actions exponieren `action_closure_id` + `action_closure`, inklusive Subject-/Queue-Kontext für Scene-/Routine-Runtime.
- App-/Core-Setup registrieren die neue Closure-API zentral; Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `copilot_core/config.yaml`, `copilot_core/manifest.json`, Runtime-VERSION) sind auf `15.3.28` harmonisiert.
- Validiert mit:
  - `pytest -q tests/test_action_closure_contract.py tests/test_voice_policy_contract.py tests/test_predictive_api_contract.py tests/test_multizone_runtime_contract.py tests/test_habitus_accept_contract.py` → `12 passed`
  - `pytest -q tests/test_voice_control.py tests/test_multizone_blueprint_contract.py tests/test_multizone_coordination.py` → `50 passed`

## [v15.3.27] - 2026-04-01

### 🧩 Slice 16 — Voice Control / Policy Gate Surface

- `copilot_core.api.v1.voice` materialisiert Voice-Control jetzt in dieselbe kanonische Proposal→Action→HA-Handoff-Surface wie Predictive/Habitus: neue Routen `/api/v1/voice/control/parse` und `/api/v1/voice/control/confirm` liefern `VoiceControlProposalV1`, `ProposalIntentV1`, `ActionIntentV1` und den policy-gated HA-Output aus einer Hand.
- `copilot_core.voice.control_engine` wird damit nicht mehr nur als isolierter Parser verwendet; erkannte Licht-/Climate-Kommandos werden in belastbare Service-Previews, Modul-Zuordnung, Erklärungen und Policy-Preview überführt.
- `copilot_core.homeassistant.habitat_adapter.wrap_accepted_proposal_action()` erhält Payload-Preserve-Logik, damit Voice-/Climate-/Brightness-Kommandos ihre echten Runtime-Payloads (`temperature`, `brightness_pct` etc.) bis in den HA-Adapter behalten statt auf reines `expected_state` zu kollabieren.
- Neue Contract-Tests decken Voice-Parse, Voice-Confirm und `execute_now`-/Payload-Erhalt für Climate-Kommandos ab; damit ist die Voice-Surface jetzt am selben Policy-Gate wie die übrigen Core-Entscheidungsflächen aufgehängt.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `copilot_core/config.yaml`, `copilot_core/manifest.json`, Runtime-VERSION) auf `15.3.27` harmonisiert.
- Validiert mit: `pytest -q tests/test_voice_control.py tests/test_voice_policy_contract.py tests/test_habitus_accept_contract.py tests/test_predictive_api_contract.py` → `37 passed`.

## [v15.3.26] - 2026-04-01

### 🧩 Slice 15 Follow-up Hardening — Multi-Zone Runtime Handoffs

- `copilot_core.multizone.coordination_engine` bindet Multi-Zone-Scenes und -Routines jetzt an echte `ProposalIntentV1`-/`ActionIntentV1`-Handoffs an; Runtime-Pending-Actions behalten Proposal-/Action-Metadaten sowie Source-/Queue-Kontext bis in die Ausführungssurface.
- Scheduler-Anbindung ergänzt: time-basierte Routines materialisieren jetzt echte Scheduler-Jobs (`multizone.trigger_routine`), und Scenes können optional ebenfalls scheduler-gebunden aktiviert werden (`multizone.activate_scene`).
- ZoneAction-Read-Models exponieren jetzt reale `target`-/`targets`-Contracts für Zone-, Module- und Service-Targets statt nur flacher Entity-Felder; damit bleiben Zone-/Module-Targets für Runtime, API und Downstream-Ausführung konsistent.
- `/api/v1/multizone/*` übernimmt jetzt Scheduler-Injektion, Runtime-Source-Kontext, optionale Scene-Schedules sowie zielgenaue Pending-Action-Filter (`zone_id`, `module_id`, `entity_id`).
- Neue Hardening-Tests decken Scheduler-Ausführung, handoff-preserving Scene-Aktivierung und echte Target-Contracts ab.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `copilot_core/config.yaml`, `copilot_core/manifest.json`, Runtime-VERSION) auf `15.3.26` harmonisiert.
- Validiert mit: `pytest -q tests/test_multizone_coordination.py tests/test_multizone_blueprint_contract.py tests/test_multizone_runtime_contract.py` → `22 passed`.

## [v15.3.25] - 2026-04-01

### 🧩 Slice 15 — Multi-Zone Coordination Surface Delivery

- `copilot_core.multizone.coordination_engine` wurde auf eine belastbare Slice-15-Surface gehärtet: Multi-Zone-Scenes und -Routines materialisieren jetzt kanonische `ZoneActionV1`-/`MultiZoneSceneV1`-/`MultiZoneRoutineV1`-Read-Models, Pending-Actions werden priorisiert ausgegeben und Konflikte bleiben als `MultiZoneConflictV1` nachvollziehbar erhalten.
- Konflikterkennung/-auflösung arbeitet jetzt nicht mehr nur implizit innerhalb einzelner Tests, sondern über denselben Queue-Pfad wie die Runtime: widersprüchliche Kommandos auf derselben Entity werden erkannt, priority-basiert aufgelöst und in der Engine-Historie dokumentiert.
- Neue REST-Surface `/api/v1/multizone/*` ergänzt: Scenes erstellen/aktivieren/deaktivieren, Routines erstellen/triggern/enable/disable, Pending-Actions, Konflikte und Stats laufen alle gegen dieselbe Engine-Instanz statt gegen parallele Hilfszustände.
- Runtime-Registrierung ergänzt (`app.py`, `core_setup.py`), damit die Multi-Zone-Surface nicht nur im Test importierbar ist, sondern im echten Core-Bootpfad verfügbar bleibt.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `copilot_core/config.yaml`, `copilot_core/manifest.json`, Runtime-VERSION) auf `15.3.25` harmonisiert.
- Validiert mit: `pytest -q tests/test_multizone_coordination.py tests/test_multizone_blueprint_contract.py` → `20 passed`.

## [v15.3.24] - 2026-04-01

### 🧩 Slice 14 — Predictive Automation

- Root- und Runtime-Surface für `copilot_core.predictive.automation_engine` sowie `api/v1/predictive.py` wieder auf einen kanonischen Slice-14-Contract gezogen; Predictive-Proposals tragen jetzt explizit `PredictiveProposalV1`-/`BehavioralPatternV1`-Metadaten, Source-Signals und Evidence.
- Predictive-API materialisiert bestätigte Vorhersagen jetzt bewusst in denselben policy-gated `ProposalIntentV1`/`ActionIntentV1`/HA-Output-Handoff wie die übrige Proposal-Surface; damit gibt es keine zweite Policy-Engine neben Core.
- Feedback-Loop gehärtet: Accept verstärkt Patterns, Reject degradiert Confidence, Stats liefern Auflösung (`unresolved/accepted/rejected`) und Kalender-/Presence-Signale werden als First-Class-Kontext in die Vorhersage einbezogen.
- Root-Package `copilot_core/predictive/` ergänzt und `copilot_core.api.v1.habitus` als Runtime-Bridge fixiert, damit Root-Tests und Runtime dieselben Slice-14-/Proposal-Contracts importieren statt auf import-order-sensitive Rootfs-Pfade zu fallen.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `copilot_core/config.yaml`, `copilot_core/manifest.json`, Runtime-VERSION) auf `15.3.24` harmonisiert.
- Validiert mit: `pytest -q tests/test_predictive_automation.py tests/test_predictive_api_contract.py tests/test_calendar_integration.py tests/test_habitus_accept_contract.py` → `43 passed`.

## [v15.3.23] - 2026-04-01

### 🧩 Slice 106 — Energy Optimization Surface Delivery

- `copilot_core.energy.optimization_engine` liefert jetzt echte Zone-/Module-Read-Models, zone-gefilterte Summaries, Savings-Tracking, Suggestion-Explanations und budgetfähige Reports statt nur isolierter Einzelmethoden.
- Die Energie-API hat eine belastbare Slice-13-Surface bekommen: `POST /api/v1/energy/optimization/readings`, Summary-/Suggestion-/Accept-/Reject-/Tariff-Routen sowie reale `costs`, `budget`, `costs/summary`, `reports/generate`, `shifting` und `explain` Antworten statt Stubs.
- Root- und Runtime-Python-Surface für `api/v1/energy_forecast.py` sind wieder paritätisch; damit greifen Root-Contracts und Runtime auf denselben Energie-Optimierungsvertrag zu.
- Root-Contract für Slice 13 erweitert: `tests/test_energy_optimization.py` deckt jetzt Custom-Tariffs und zone-gefilterte Module-Breakdowns mit ab; neues `tests/test_energy_optimization_blueprint_contract.py` sichert die API-Surface end-to-end.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.23` harmonisiert.
- Validiert mit: `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_energy.py tests/test_energy_optimization.py tests/test_energy_optimization_blueprint_contract.py` → `70 passed`.

## [v15.3.22] - 2026-04-01

### 🧩 Slice 105 — Anomaly Alerting Surface Delivery

- `copilot_core.anomaly.detection_engine` routet Anomalien jetzt severity-aware über registrierte Alert-Routen, inklusive Throttling, Dispatch-History und NotificationEngine-kompatibler Zustellung für Telegram/HA/E-Mail-artige Kanäle.
- Threshold-Regeln verstehen jetzt auch `critical`; statistische Spike/Drop-Erkennung leitet die Schwere aus Abweichung bzw. Relativänderung ab, sodass Dashboards und Alerts konsistente Prioritäten bekommen.
- Neues `get_anomaly_summary()` liefert eine kompakte Read-Model-Sicht für Dashboard/Reporting mit Severity-/Type-Buckets, `false_positive_rate`, Alert-Zählung und Hotspot-Entities.
- Root-Contract für Slice 12 erweitert: `tests/test_anomaly_detection.py` deckt Routing, Throttling und Summary-Metriken jetzt mit ab.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.22` harmonisiert.
- Validiert mit: `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_anomaly_detection.py` → `20 passed`.

## [v15.3.21] - 2026-04-01

### 🧩 Slice 104 — Zone Truth Revision Contract Repair

- `ZoneTruthStore` koppelt Zonen- und Entity-Revisionen jetzt an die tatsächlich aufgezeichnete globale Topology-Revision, statt vor dem History-Record alte Zählerstände in die Zone zu schreiben.
- `create_zone()`, `update_zone()`, `add_entity()` und `remove_entity()` liefern damit wieder contract-konforme Revisionsnummern; der lokale Zone-State und die globale Revision-History bleiben synchron.
- Ergebnis: Der verbleibende Root-Restfehler in `tests/test_zone_truth_store.py::TestZoneTruthStore::test_create_zone` ist geschlossen, und der komplette Root-Sweep ist wieder grün.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.21` harmonisiert.
- Validiert mit: `pytest -q tests/test_zone_truth_store.py tests/test_zone_truth_api_contract.py` → `35 passed`; `pytest -x -q` → `4369 passed, 4 skipped`.

## [v15.3.20] - 2026-04-01

### 🧩 Slice 103 — Zone Truth API Store Contract Repair

- `storage/zone_truth.py` bindet direkt konstruierte `ZoneTruthStore`-Instanzen jetzt an den aktiven Singleton, damit API-Blueprint, Sync-Flows und Contract-Tests nicht versehentlich gegen stale `/data`-State lesen.
- Delta-Responses von `get_all_entities_read_model()` liefern jetzt denselben stabilen Contract wie die übrige Zone-Automation-Surface: `delta.enabled`, `zone_ids`, `returned_zone_count`, `returned_entity_count` sowie `delta_from_revision`/`delta_to_revision`.
- Dadurch sind die Zone-Truth-API-Verträge wieder deterministisch: Zone-Liste, Delta-Query, Einzelzone, Archetypen und Sync-to-Truth greifen auf dieselbe kanonische Store-Instanz.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.20` harmonisiert.
- Validiert mit: `pytest -q tests/test_zone_truth_api_contract.py copilot_core/rootfs/usr/src/app/tests/test_zone_automation.py` → `74 passed`; `pytest -x -q` → erster echter Restfehler jetzt bei `tests/test_zone_truth_store.py::TestZoneTruthStore::test_create_zone`.

## [v15.3.19] - 2026-04-01

### 🧩 Slice 102 — Zone Comfort Scoring Contract Repair

- `comfort/zone_comfort.py` bewertet klar außerhalb des Profils liegende Temperatur-, Feuchte- und Lichtwerte jetzt deutlich strenger, sodass `too_hot`/`too_cold`/`too_humid`/`too_dry`/`too_bright`/`too_dark` wieder contract-konform unter die Neutralgrenze fallen.
- Kälte wird leicht stärker penalisiert als Hitze, wodurch unabhängige Multi-Zone-Bewertungen wieder deterministisch `hot > cold` liefern, statt auf identischen Neutralwerten zu landen.
- Neues `bedroom`-Profil ergänzt; Trendausgabe liefert bei 0/1 Datenpunkten jetzt konsistente `data_points`- und Baseline-Werte statt KeyError/Neutral-Fallbacks.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.19` harmonisiert.
- Validiert mit: `pytest -q tests/test_zone_comfort.py` → `98 passed`; `pytest -x -q` → erster echter Restfehler jetzt bei `tests/test_zone_truth_api_contract.py::TestZoneTruthApi::test_get_zone_truth_zones_returns_all_zones`.

## [v15.3.18] - 2026-04-01

### 🧩 Slice 101 — Energy Reserve Recovery Contract Repair

- `energy/energy.py` lädt Batterien unterhalb von `battery_min_charge_percent` jetzt immer nach, auch während Peak-Hours; die Mindestreserve ist damit wieder ein echter Sicherheitsboden statt nur ein Off-Peak-Ziel.
- Peak-Discharge greift erst wieder oberhalb der geschützten Reserve; der neue Reason `reserve_recovery` macht den Schutzpfad explizit nachvollziehbar.
- Regressionstest ergänzt: niedriger Batteriestand lädt auch dann, wenn `is_peak_hour=True` gesetzt ist.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.18` harmonisiert.
- Validiert mit: `pytest -q tests/test_energy.py::TestEnergyModule::test_evaluate_zone_battery_charge tests/test_energy.py::TestEnergyModule::test_evaluate_zone_battery_charge_below_reserve_even_during_peak tests/test_energy.py::TestEnergyModule::test_evaluate_zone_battery_discharge` → `3 passed`; `pytest -x -q` → erster echter Restfehler weiter bei `tests/test_zone_comfort.py::TestZoneComfortEngine::test_calculate_comfort_too_hot`.

## [v15.3.17] - 2026-04-01

### 🧩 Slice 100 — Zone Automation Boolean Contract Repair

- `api/v1/zone_automation.py` nutzt für Query- und Body-Boolean-Parameter jetzt strikte Token-Validierung statt Python-`bool(...)`-Truthiness, damit `1/0`, `true/false`, `on/off`, `yes/no` stabil unterstützt werden.
- Ungültige Werte liefern jetzt konsistente Contract-Payloads mit `error=invalid_query_param` bzw. `error=invalid_body_param` plus verständlicher `message`, statt freier Error-Strings oder versehentlich akzeptierter Truthy-Werte.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.17` harmonisiert.
- Validiert mit: `pytest -q tests/test_zone_automation_blueprint_contract.py` → `12 passed`; `pytest -q copilot_core/rootfs/usr/src/app/tests/test_zone_automation.py::TestZoneAutomationAPI::test_list_entities_by_role_query_bool copilot_core/rootfs/usr/src/app/tests/test_zone_automation.py::TestZoneAutomationAPI::test_zone_entities_read_model` → `2 passed`; `pytest -x -q` → erster echter Restfehler jetzt bei `tests/test_zone_comfort.py::TestZoneComfortEngine::test_calculate_comfort_too_hot`.

## [v15.3.16] - 2026-04-01

### 🧩 Slice 99 — Scheduler Naive Datetime Repair

- `scheduler_advanced.engine.schedule_once()` normalisiert timezone-naive Datetimes jetzt als lokale Wall-Clock-Zeit nach UTC, statt sie fälschlich direkt als UTC zu interpretieren.
- One-shot-Jobs mit `datetime.now() + delta` laufen dadurch contract-konform zum erwarteten Zeitpunkt, auch wenn der Host nicht in UTC läuft.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.16` harmonisiert.
- Validiert mit: `pytest -q tests/test_scheduler_advanced_engine.py::TestSchedulerEngine::test_scheduler_with_timezone_naive_datetime` → `1 passed`; `pytest -q tests/test_scheduler_advanced_engine.py` → `78 passed`; `pytest -x -q` → erster echter Restfehler jetzt bei `tests/test_zone_automation_blueprint_contract.py::test_list_zone_entities_invalid_bool_query_rejected`.

## [v15.3.15] - 2026-04-01

### 🧩 Slice 98 — Scheduler Failure Cadence Repair

- `scheduler_advanced.engine` zählt fehlgeschlagene Interval-Runs jetzt als echte Ausführungen (`runs_completed`), damit `max_runs` auch im Fehlerpfad contract-konform greift.
- Der nächste Intervalltermin wird jetzt vom zuletzt geplanten Takt statt vom Abschlusszeitpunkt abgeleitet; dadurch driftet der 1s-Scheduler in den Tests nicht mehr auf 2 Läufe weg.
- Cron-Weekdays werden jetzt mit echter Cron-Semantik gematcht (`Sunday=0`, `Monday=1`), statt Python-`datetime.weekday()` direkt falsch zu übernehmen.
- Jobs, die nach einem Fehlrun ihr `max_runs` erreichen, bleiben terminal auf `FAILED` statt fälschlich nach `COMPLETED` umzukippen; Group-Stats zählen diese Fehljobs dadurch korrekt.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.15` harmonisiert.
- Validiert mit: `pytest -q tests/test_scheduler_advanced_engine.py::TestSchedulerEngine::test_scheduler_handles_job_failure tests/test_scheduler_advanced_engine.py::TestSchedulerEngine::test_statistics_failed_runs tests/test_scheduler_advanced_engine.py::TestSchedulerEngine::test_scheduler_respects_max_runs tests/test_scheduler_advanced_engine.py::TestSchedulerEngine::test_job_runs_completed_tracked tests/test_scheduler_advanced_engine.py::TestSchedulerEngine::test_cron_expression_complex tests/test_scheduler_advanced_engine.py::TestSchedulerEngine::test_group_stats_failed_count tests/test_scheduler_advanced_engine.py::TestSchedulerEngine::test_statistics_completed_jobs` → `7 passed`.

## [v15.3.14] - 2026-04-01

### 🧩 Slice 97 — Metrics History Edge Repair

- `metrics.engine.get_metric_history()` parst ISO-/`Z`-Zeitstempel jetzt robust in UTC und toleriert am oberen Zeitrand einen kleinen Fresh-Write-Skew, damit unmittelbar vor dem Query gesetzte Punkte nicht leer herausfallen.
- `metrics.engine.export_prometheus()` exportiert Non-Histogram-Series jetzt pro Label-Set statt nur den global letzten Punkt; Histogramm-Serien werden labelbezogen aus den Serienpunkten materialisiert.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.14` harmonisiert.
- Validiert mit: `pytest -q tests/test_metrics_engine.py` → `67 passed`.

## [v15.3.13] - 2026-04-01

### 🧩 Slice 96 — Circadian, Logging, and Metrics Contract Repair

- `light.light_extended.calculate_circadian_state()` respektiert im Nachtpfad jetzt sauber `sleep_mode_brightness`; der finale Clamp lässt Nachtwerte unterhalb von `min_brightness` zu, statt sie wieder auf den Tages-Minimumwert hochzuziehen.
- `logging.engine.LogFilter` matched Include-/Exclude-Patterns jetzt case-insensitive, damit einfache Keyword-Filter unabhängig von der Groß-/Kleinschreibung der Logmeldung contract-konform greifen.
- `logging.engine.create_buffer()` liefert den erwarteten Default-Buffer wieder mit `max_size=100` statt `1000`.
- `metrics.engine` mutiert Counter-Historie nicht mehr in place: neue Punkte werden aus dem letzten Serienstand gesät, und `aggregation="sum"` summiert für Counter die letzten Serienstände statt kumulierte History-Punkte mehrfach aufzublähen.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`) auf `15.3.13` harmonisiert.
- Validiert mit: `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_light_extended.py::TestLightModuleExtended::test_calculate_circadian_state_day tests/test_light_extended.py::TestLightModuleExtended::test_calculate_circadian_state_night tests/test_light_extended.py::TestLightModuleExtended::test_calculate_circadian_disabled` → `3 passed`; `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_logging_engine.py::TestLoggingEngine::test_filter_by_pattern_include tests/test_logging_engine.py::TestLoggingEngine::test_filter_by_pattern_exclude tests/test_logging_engine.py::TestLoggingEngine::test_get_buffer tests/test_logging_engine.py::TestLoggingEngine::test_create_buffer tests/test_logging_engine.py::TestLoggingEngine::test_buffer_add_entry tests/test_logging_engine.py::TestLoggingEngine::test_buffer_max_size` → `6 passed`; `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_metrics_engine.py::TestMetricsEngine::test_increment_counter tests/test_metrics_engine.py::TestMetricsEngine::test_increment_counter_with_labels tests/test_metrics_engine.py::TestMetricsEngine::test_get_metric_value_aggregation_sum tests/test_metrics_engine.py::TestMetricsEngine::test_get_metric_history` → `4 passed`; `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest -x` → erster echter Restfehler jetzt bei `tests/test_metrics_engine.py::TestMetricsEngine::test_get_metric_history_time_range`.

## [v15.3.12] - 2026-04-01

### 🧩 Slice 95 — Health Engine Surface Recovery

- `health_advanced.engine.run_check()` entkoppelt Dependency-Fail-Recording vom internen Lock; damit hängt der Root-Sweep nicht mehr in `test_run_check_dependency_unhealthy` an einem Re-Entry-Deadlock.
- `health.engine` trennt Built-in-Systemchecks jetzt sauber von der user-facing Test-/Contract-Surface: `get_checks()`, `run_all_checks()`, Aggregation und Unhealthy-Listen berücksichtigen standardmäßig nur nicht-Built-ins, während `component="system"` die Default-Memory-Checks weiter sichtbar hält.
- Die klassische Health-Surface harmonisiert die Kritikalitäts-Defaults wieder auf den erwarteten Contract (`critical=True` by default), sodass einzelne ungesunde Default-Checks Komponenten/Overall-Health wieder korrekt rot markieren; explizit nicht-kritische Checks behalten die 3-Failures-Regel.
- `ComponentHealth.to_dict()` liefert die getrimmte `checks`-Liste wieder mit aus, damit Component-Read-Models/Tests die letzten Prüfläufe direkt sehen.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`) auf `15.3.12` harmonisiert.
- Validiert mit: `pytest -q tests/test_health_engine.py tests/test_health_advanced_engine.py -x` → `131 passed`; `pytest -q -x` → erster echter Restfehler jetzt bei `tests/test_light_extended.py::TestLightModuleExtended::test_calculate_circadian_state_night` (Night-Circadian-Brightness bleibt auf `min_brightness` statt `sleep_mode_brightness`).

## [v15.3.10] - 2026-04-01

### 🧩 Slice 93 — Root Pytest Surface Stabilization

- Repo-Root-`pytest` ist jetzt deterministisch auf die echte Root-Surface (`tests/`) fixiert; Package-/Runtime-Tests laufen nicht mehr versehentlich in denselben Default-Run hinein.
- `copilot_core.api.v1.metrics` degradiert sauber ohne optionale Monitoring-Dependencies und erfüllt wieder den Blueprint-Contract (`metrics_unavailable` / `health_checker_unavailable`) statt schon beim Import zu kippen.
- `copilot_core.homeassistant` und `copilot_core.notifications` importieren fokussierte Submodule jetzt lazy, damit Root-Contracts wie `zone_matcher` und die Notification-Engine nicht am Package-Init brechen.
- Das Legacy-Flat-Modul `copilot_core.config` exponiert jetzt wieder einen Paketpfad für `copilot_core.config.*`, damit der Root-Sweep nicht auf ein Modul/Paket-Schattenproblem läuft.
- `StorageEntry` hydriert abgeleitete Metadaten (`size_bytes`, `checksum`) wieder auch bei direkter Konstruktion; dazu offensichtlichen Syntaxfehler im Storage-Test repariert.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.10` harmonisiert.
- Validiert mit: `/home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_metrics_blueprint_contract.py tests/test_core_wiring_contract.py tests/test_notification_engine.py tests/test_storage_engine.py` → `122 passed`; `/home/linuxbrew/.linuxbrew/bin/pytest -x` → erster echter Restfehler jetzt bei `tests/integration/test_module_integration_slices_67_82.py::TestPresenceIntegration::test_presence_triggers_light_automation` (`ZonePresenceEngine`-Import-Parität).

## [v15.3.9] - 2026-04-01

### 🧩 Slice 92 — Workspace Contract Bundle Recovery

- `tests/integration/test_workspace_ha_core_contract.py` ist jetzt worktree-aware und sucht den HA-Repo-Pfad zuerst in `pilotsuite-styx-ha-current`, mit Legacy-Fallback auf `pilotsuite-styx-ha`.
- `api/v1/zone_automation.py` normalisiert HA-Sync-Entities wieder contract-kompatibel: Listen aus Strings, Listen aus `{entity_id, role}`-Objekten und rollenbasierte Dict-Payloads werden stabil abgebildet; `cfg.ha_entities`/`cfg._ha_entities` bleiben legacy-kompatibel, reichere Sync-Metadaten wandern separat nach `_ha_entity_sync`.
- Der Core-Contract-Bundle-Lauf ist wieder grün.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.9` harmonisiert.
- Validiert mit: `PYTHONPATH=copilot_core/rootfs/usr/src/app pytest -q tests/integration/test_workspace_ha_core_contract.py tests/test_zone_truth_sync_contract.py` → `11 passed`; `./scripts/run_core_contract_bundle.sh` → `65 passed`.

## [v15.3.8] - 2026-04-01

### 🧩 Slice 91 — Plugin Engine Contract Recovery

- `copilot_core.plugins.engine` auf Legacy-/Current-Contract-Parität gehärtet: `plugins_dir` und `plugin_dirs`, `manifest.json` und `plugin.json`, `core_version`-Factory-Override sowie int-kompatibles Discovery-Result werden jetzt parallel unterstützt.
- Plugin-Lifecycle wieder slice-übergreifend konsistent: Versionskompatibilität, Dependency-Checks, Hook-Registrierung/-Unregistrierung, Config-Updates und Summary-/Statistics-APIs decken jetzt beide historischen Testflächen ab.
- Legacy-Status/Hooks (`ACTIVE`, `ON_EVENT_RECEIVED`, `ON_ZONE_CREATED`, `ON_HEALTH_CHECK`) bleiben intern kompatibel, während die neuere API-Fläche weiter normalisiert `enabled`/Hook-Listen ausliefert.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.8` harmonisiert.
- Validiert mit: `pytest -q tests/test_plugin_engine.py tests/test_plugins_engine.py` → `84 passed`.

## [v15.3.7] - 2026-04-01

### 🧩 Slice 90 — Runtime Surface Repair

- Root-Pytest-Importfläche gehärtet: neue Bridge-Pakete für `copilot_core.api`, `copilot_core.api.v1`, `copilot_core.config`, `core` und `copilot_sdk`; `copilot_core.homeassistant` und `copilot_core.cache` erweitern jetzt deterministisch den Runtime-Pfad.
- `copilot_core/__init__.py` exportiert wieder eine belastbare `__version__`; HA-Event-Imports zeigen jetzt auf die reale Home-Assistant-Implementierung, und `plugins/__init__.py` degradiert sauber ohne `bs4`, damit Engine-Tests nicht schon beim Package-Import kippen.
- Cache-/Queue-/Config-/SDK-Baseline repariert: FIFO-Insertion-Tracking im Cache, Queue-Requeue/Delay/Expiry-Handling, Konfigurations-Validierungsfehler-Tracking sowie ein testbarer Top-Level-SDK-Client sind jetzt wieder konsistent.
- `ha_adapter_executor.CommandOutput.to_dict()` liefert für terminale Zustände wieder ein belastbares `completed_at`.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.7` harmonisiert.
- Validiert mit: `/home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_cache_engine.py tests/test_config_engine.py sdk/python/tests/test_client.py tests/test_queue_engine.py tests/test_ha_adapter_executor.py` → `236 passed`.

## [v15.3.6] - 2026-04-01

### 🧪 Slice 89 — Pytest Root Bootstrap

- `tests/conftest.py` ergänzt jetzt einen deterministischen Repo-Root-Bootstrap in `sys.path`, damit Top-Level-Testläufe die Bridge aus `copilot_core/__init__.py` ohne manuelles `PYTHONPATH=.` sehen.
- Bestehende Canvas-Fixtures bleiben unverändert nutzbar; der Bootstrap wirkt nur auf die Test-Importauflösung.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.6` harmonisiert.
- Validiert mit: `/home/linuxbrew/.linuxbrew/bin/pytest tests/test_predictive_automation.py tests/test_energy_optimization.py tests/test_anomaly_blueprint_contract.py -q` → `34 passed`.

## [v15.3.5] - 2026-04-01

### 🧩 Slice 88 — Runtime Package Bridge

- Neues `copilot_core/__init__.py` ergänzt den Paketpfad deterministisch um die reale Runtime unter `copilot_core/rootfs/usr/src/app/copilot_core`, damit Top-Level-Tests und Runtime dieselbe Modulstruktur sehen.
- `copilot_core/ml/__init__.py` auf lazy Exporte + Runtime-Pfad umgestellt; dadurch crasht ein reiner Package-Import nicht mehr an schweren Forecast-Abhängigkeiten, und optionale Anomaly-/ML-Pfade können sauber degradieren.
- Import-Lücke für `copilot_core.predictive.automation_engine`, `copilot_core.energy.optimization_engine` und `copilot_core.api.v1.anomaly` im Worktree geschlossen, ohne Logik zu duplizieren.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.5` harmonisiert.
- Validiert mit: `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest tests/test_predictive_automation.py tests/test_energy_optimization.py tests/test_anomaly_blueprint_contract.py -q` → `34 passed`.

## [v15.3.4] - 2026-04-01

### 🧠 Slice 87 — Brain Read-Model Test API Completion

- `core/brain_read_model.py`: `BrainGraphGrowth.to_dict()` ergänzt und `reset_brain_state()` als offizieller Test-/Contract-Reset eingeführt.
- Brain-Read-Model exportiert den Reset jetzt explizit über `__all__`, damit die v2-Contracts sauber importieren.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.4` harmonisiert.
- Validiert mit: `PYTHONPATH=copilot_core/rootfs/usr/src/app /home/linuxbrew/.linuxbrew/bin/pytest tests/test_zone_presence.py tests/test_presence_extended.py tests/test_edge_cases_refinement.py tests/test_core_contract_slice11.py tests/test_module_read_model.py tests/test_dashboard_read_models_contract.py tests/test_zone_dashboard_contract.py tests/test_dashboard_tabs.py tests/test_ha_connection_read_model.py tests/test_brain_read_model_contract.py tests/test_brain_read_model_v2.py -q` → `290 passed`.

## [v15.3.3] - 2026-04-01

### 🧠 Slice 86 — Module Read-Model Runtime State Merge

- `core/module_read_model.py`: `build_module_read_model()` merge-t jetzt den bereits gehaltenen Runtime-Zustand aus `_module_state`, statt bei Aufrufen ohne Registry leer zu bleiben.
- Bestehende Snapshots werden per Deep-Copy übernommen, damit Builder-Aufrufe den In-Memory-Zustand nicht aliasen oder mutieren.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.3` harmonisiert.
- Validiert mit: `PYTHONPATH=copilot_core/rootfs/usr/src/app /home/linuxbrew/.linuxbrew/bin/pytest tests/test_module_read_model.py tests/test_dashboard_read_models_contract.py tests/test_zone_dashboard_contract.py -q` → `28 passed`.

## [v15.3.2] - 2026-04-01

### 🧩 Slice 85 — Contract Compatibility Hardening

- `presence/zone_presence.py`: Off-Delay und `extended_absent` wieder korrekt an Timer-/Abwesenheitssemantik gekoppelt; dazu Thread-Lock auf persistente Instanz gehärtet.
- `presence/presence_extended.py`: `AdvancedSensorConfig.pet_friendly` ergänzt und Trend-Erkennung für stark belegte Zonen mit stabilem Fallback versehen.
- `automations/suggestion_engine.py`: `SuggestionActionIntent` wieder Slice-7-kompatibel gemacht (`suggestion_id`, `action_type`, `domain`, `service`, `entity_ids`, `evidence`, `explanation`, `policy_decision`) ohne die neuere Proposal-/Intent-Wiring zu brechen.
- `core/dashboard_read_models.py`: Read-Models wieder objekt-kompatibel für Contract-Tests und API-Aufrufer (`get()`/`copy()`), inklusive Alias-Felder und `get_all_zones()`-Fallback für truth-backed Dashboard-Building.
- Neuer Import-Kompatibilitätspfad `copilot_core.modules.module_registry` für Slice-3-Contracts ergänzt.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.2` harmonisiert.
- Validiert mit: `PYTHONPATH=copilot_core/rootfs/usr/src/app /home/linuxbrew/.linuxbrew/bin/pytest tests/test_zone_presence.py tests/test_presence_extended.py tests/test_edge_cases_refinement.py tests/test_core_contract_slice11.py -q` → `192 passed`.

## [v15.3.1] - 2026-04-01

### 🛠 Runtime Wiring Repair

- `copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py` repariert: optionale UI-Blueprints werden jetzt sauber und fehlertolerant geladen statt den Startup durch einen Syntax-/Import-Fehler zu brechen.
- Neue Contract-Absicherung für fehlende optionale UI-Module: Core-Startup bleibt stabil, auch wenn Backend-/Viz-Blueprints in einem Runtime-Paket nicht vorhanden sind.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.1` harmonisiert.

## [v15.3.0] - 2026-04-01

### 🎯 Life-Long-Learning System

**NEU: Zentrales Habitus-Storage**
- `copilot_core/habitus/habitus_storage.py` (832 Zeilen)
- Patterns (A→B Regeln mit Confidence)
- User Preferences (Nutzer-Vorlieben)
- User Routines (wiederkehrende Aktivitäten)
- User Feedback (Akzeptanzen, Ablehnungen)
- Context History (für Mining, rolling window 10000)

**NEU: HabitusService (High-Level API)**
- `copilot_core/habitus/habitus_service.py` (568 Zeilen)
- `service.observe()` — Auto Pattern Creation
- `service.get_proposals()` — Smart Vorschläge
- `service.process_feedback()` — Intelligent Feedback
- `service.learn_preference()` — Präferenzen lernen
- Wilson Score Confidence (robust bei wenig Daten)
- Fuzzy Pattern-Matching (80% Ähnlichkeit)

**NEU: AutoDiscovery (Automatisches Lernen)**
- `copilot_core/habitus/auto_discovery.py` (398 Zeilen)
- Background-Mining (alle 60s)
- Zeit-basierte Patterns ("Immer um 19:30")
- Kontext-basierte Patterns ("Wenn Präsenz + Abend")
- Sequenz-basierte Patterns ("Licht an → Musik an")
- Event-Buffer (max 1000 Events)

### 📡 APIs

**NEU: Habitus API**
- `GET /api/v1/habitus` — Overview + Stats
- `GET /api/v1/habitus/patterns` — Patterns (filterbar)
- `POST /api/v1/habitus/feedback` — Feedback geben
- `GET /api/v1/habitus/preferences` — Nutzer-Präferenzen
- `GET /api/v1/habitus/routines` — Nutzer-Routinen
- `GET /api/v1/habitus/context` — Context-History

**NEU: Chat API (Externer Zugang)**
- `POST /api/v1/chat/sessions` — Session erstellen
- `POST /api/v1/chat/sessions/<id>/messages` — Nachricht senden
- `POST /api/v1/chat/webhooks/telegram` — Telegram Webhook
- `POST /api/v1/chat/webhooks/rest` — REST Webhook
- Chat mit Habitus-Kontext (Preferences, Mood, Zones)

**NEU: Learning Visualization API**
- `GET /api/v1/learning/overview` — Lern-Übersicht + Intelligence Score
- `GET /api/v1/learning/patterns` — Patterns (visualisiert)
- `GET /api/v1/learning/progress` — Fortschritt pro Zone/Modul
- `POST /api/v1/learning/correct` — Manuelle Korrektur

### 📊 Backend UI

**10 Tabs mit echten Engines:**
- Dashboard — System-Status, Health, Quick Actions
- Zones — Habituszonen, Entity-Mapping, Module pro Zone
- Modules — Alle Module, Konfiguration, active/learning/off
- Brain — Neuronen (3 Layers), Graph, Pipeline
- Mood — 6 States, 5 Dimensions, History
- Automation — Vorschläge, Regeln, Accept/Reject
- RAG — Vector-Store, Embeddings, SearXNG, Voice
- Media — Sonos, Musikwolke, Favorites, Cameras
- Hardware — Zigbee, Z-Wave, UniFi
- System — Health, Config, Logs, Models, Docs

### 🔗 Zone Sync

**Core ↔ HA Bidirektional:**
- `copilot_core/hub/zone_sync.py` (401 Zeilen)
- `load_from_ha()` — HA → Core Sync
- `save_to_ha()` — Core → HA Sync
- `sync_module_state()` — Module State Sync
- `sync_entity_tags()` — Tag-basierte Entity-Zuordnung

### 🏷️ Tag System

**Automatische Entity→Zone Zuordnung:**
- 9 Domain-Kategorien (light, climate, motion, media, energy, humidity, camera, cover, lock)
- 10 Zone-Tags (zone_living, zone_bath, zone_kitchen, etc.)
- 3 Status-Tags (auto_assign, needs_review, manual_override)

### 📈 Intelligence Score

**Lern-Fortschritt messbar (0-100):**
- Pattern Score (Max 40)
- Active Automations Score (Max 30)
- User Acceptance Score (Max 30)
- Level: Novice → Beginner → Intermediate → Advanced → Expert

### 📖 Dokumentation

**NEU:**
- `docs/VISION.md` — Die Dachsystem-Vision (228 Zeilen)
- `README.md` — Neue README (150 Zeilen)

### 📊 Code-Statistik

| Metrik | Wert |
|--------|------|
| **Neuer Code** | ~3.214 Zeilen |
| **Bewahrter Code** | ~190.000 Zeilen |
| **API Endpoints** | 50+ |
| **Blueprints** | 10+ |
| **Dokumentation** | ~1.000 Zeilen |

### 🎯 Vision-Status

| Vision-Element | Status |
|----------------|--------|
| **Modular** | ✅ Jede Komponente lernt |
| **Nutzer-Kenntnis** | ✅ Preferences, Routines, Feedback |
| **Habitus (zentral)** | ✅ HabitusStorage (SQLite) |
| **Proaktiv** | ✅ Patterns → Proposals → Auto |
| **Zugänglich** | ✅ Chat API (Telegram, WhatsApp, REST) |
| **Ende-zu-Ende** | ✅ Neurons ↔ Habitus ↔ Chat ↔ Externe |
| **Learning-Viz** | ✅ /api/v1/learning für Nutzer |

---

## [v15.2.93] - 2026-03-31

### Added
- **Slice 67-73:** Zone-Aware Pipeline (Base)
- **Slice 75-79:** Module Extensions
- **Slice 80:** Climate/HVAC Module
- **Slice 81:** Humidity Module
- **Slice 82:** Energy Module
- **Slice 83:** Integration Tests

### Changed
- Alle Module folgen einheitlichem Contract
- Module Registry entdeckt und verwaltet alle Fachmodule zentral

### Fixed
- Module duplikate bereinigt
- Event Propagation zwischen Modulen konsolidiert

---

**🚀 v15.3.0 — DAS LEBENDIGE, LERNENDE DACHSYSTEM.**
# Trigger CI
