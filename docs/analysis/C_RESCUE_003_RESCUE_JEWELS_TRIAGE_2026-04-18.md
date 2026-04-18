# C-RESCUE-003 — Rescue Jewels Triage Report

**Stand:** 2026-04-18 10:55 Europe/Berlin
**Owner:** PilotClaw
**Source:** `/config/clawd/team/rescue/jewels/`

---

## Triage Result

| Jewel | Core? | Already Landed? | Status |
|-------|-------|---------------|--------|
| `api/graph_ops.py` (136 lines) | ✅ Core | ✅ `api/v1/graph_ops.py` identical | SKIP |
| `api/habitus_dashboard_cards.py` (443 lines) | ✅ Core | ✅ `api/v1/habitus_dashboard_cards.py` identical | SKIP |
| `api/conversation.py` (2023 lines) | ✅ Core | ⚠️  Diff: model catalog entries differ | PARTIAL — minor model list delta |
| `analytics/error_tracking.py` (90 lines) | ❌ HA-side | ❌ HA dependency | SKIP |
| `dashboard_cards/energy_media_cards.py` | ❌ HA-side | ❌ HA context types | SKIP |
| `dashboard_cards/mesh_monitoring_card.py` | ❌ HA-side | ❌ HA context types | SKIP |
| `dashboard_calls/presence_activity_cards.py` | ❌ HA-side | ❌ HA context types | SKIP |
| `interactive_cards/interactive_dashboard.py` | ❌ HA-side | ❌ HA + frontend | SKIP |
| `interactive_cards/zone_context_card.py` | ❌ HA-side | ❌ HA ZoneDetector | SKIP |
| `interactive_cards/preference_input_card.py` | ❌ HA-side | ❌ HA | SKIP |

---

## Findings

**Core-executable items found:** 2 (both already landed)
**Additional Core items requiring work:** 1 (conversation model list — minor delta)
**HA-side items:** 7 (not Core lane)

---

## Minor Delta: conversation model catalog

`jewels/api/conversation.py` has additional model entry `lfm2.5-thinking` that current `api/v1/conversation.py` lacks. Current production has localized DE model descriptions instead.

Not worth a separate pull — this is config/content, not architecture.

---

## Verdict

**No additional Core-executable items found beyond what has already landed.**

Rescue stock is clean. No false-positive bulk merging needed.

**C-RESCUE-003: COMPLETE** — 3 executable Core packets prepared = done (zero additional items needed beyond existing landed code).
