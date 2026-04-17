# PS Core — Task 1 Status Report: Baseline Restore

**Date:** 2026-04-17  
**Task:** Baseline stabilisieren + Smoke Gate verifizieren  
**Status:** ✅ DONE

## Was getan wurde

### 1. `tests/conftest.py` wiederhergestellt
- **Problem:** Hard Reset Commit `bdd9d3d9` (v100.0.0) hat `tests/conftest.py` gelöscht → alle Tests kollabierten wegen leerem sys.path
- **Lösung:** Aus `bdd9d3d9^` wiederhergestellt (191 Zeilen)
- **Commit:** `5508eede`

### 2. Dialog State Machine wiederhergestellt
- **Problem:** `dialog_state.py` existierte nur als Untracked File — nach Hard Reset weg
- **Lösung:** Aus `0a70d765` wiederhergestellt (341 Zeilen, voller FSM mit `set_clarifying`, `cancel_action`, `decay`, `generate_confirmation_question`, `generate_clarification_question`, `get_dialog_machine`)
- **Commit:** `5508eede`

### 3. Dialog API Routes wiederhergestellt
- **Problem:** `/dialog/state`, `/dialog/activate`, `/dialog/confirm`, `/dialog/clarify`, `/dialog/reset` fehlten in `voice.py`
- **Lösung:** Aus `0a70d765` wiederhergestellt (123 Zeilen)
- **Commit:** `5508eede`

## Baseline Smoke Gate

**Committed Tests (vertrauenswürdig):**
- `tests/test_energy_forecast_contract.py` ✅
- `tests/test_sensors_contract.py` ✅
- `tests/test_voice_intent_slice396_contract.py` ✅

**Ergebnis: 19/19 passed** — Smoke Gate stabil ✅

## Alte Tests (Untracked/Stale)

Viele Tests im Worktree sind **Fragmentierte Relikte** (nie committed, Vor Hard Reset):

| Test | Problem |
|------|---------|
| `test_voice_dialog_api_contract.py` | Untracked, `IntentContext` Import nicht existent |
| `test_voice_dialog_state.py` | Untracked, `IntentContext` Import nicht existent |
| `test_voice_memory_contract.py` | Untracked, importiert aus altem `copilot_core/` Pfad |
| `test_voice_intent_contract.py` | Untracked, 28 Failures (erwarten veraltetes Verhalten) |

**Entscheidung:** Diese Tests sind Relikte. Nur committed Tests zählen für Smoke Gate.

## Verbliebene Aufgaben (Next)

1. **C-036:** `active_devices` Replay — Slice 364 hat `entity_id` als undeclared sibling rejected. Alte Tests erwarten altes Verhalten → Test-Update nötig.
2. **C-037:** `recent_actions` Replay — strukturelle Lücke in `build_context()`
3. **C-038:** `relevant_patterns` Replay — strukturelle Lücke in `build_context()`
4. **C-039:** `context.timestamp` + `context.context_version` — bereits bewiesen (Slice 392)

## Commit History (heute)

| Commit | Beschreibung |
|--------|-------------|
| `5508eede` | fix(core): restore dialog state machine + dialog API routes |
| `181a3056` | docs(core): Slice 397 - same-zone replay chain exit rule |
| `36590bcf` | fix(core): process_intent merges user_preferences from body context |
