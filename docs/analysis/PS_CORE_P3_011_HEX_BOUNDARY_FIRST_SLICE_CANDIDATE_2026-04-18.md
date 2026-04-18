# PS_CORE_P3_011_HEX_BOUNDARY_FIRST_SLICE_CANDIDATE_2026-04-18

## Task
Prepare the first honest bounded slice behind `P3-011 / Hexagonal Architecture Refactor` while Andreas approval is pending.

## Why this prep matters
`P3-011` was still approval-gated, but the next implementation move should not stay vague. The lane needs one concrete first defect ready so approval can turn directly into a bounded code pull.

## First concrete boundary defect
`addons/pilotsuite/app/copilot_core/api/v1/voice.py` still acts as both HTTP adapter **and** service factory / runtime container.

Evidence in repo truth:
- `_get_intent_handler()` lazily constructs `VoiceIntentHandler` on `current_app` (`voice.py:57-98`)
- `_get_context_builder()` caches a concrete builder on `current_app` (`voice.py:103-105`)
- `_get_stt_engine()` and `_get_tts_engine()` instantiate `WhisperSTT` / `PiperTTS` directly in the route layer (`voice.py:110-119`)
- `_get_nlu_engine()` instantiates `NLUEngine` in the route layer (`voice.py:124-126`)
- `_get_proactive_hints()` also caches concrete runtime state on `current_app` (`voice.py:251-270`)

That means the route surface owns object lifecycle, concrete dependency selection, and app-local singleton state instead of consuming a clearly injected boundary.

## Recommended first bounded P3-011 slice
**Slice name:** `P3-011-A / Voice route boundary extraction`

Bounded implementation goal:
1. keep `api/v1/voice.py` as the HTTP adapter only,
2. resolve voice dependencies from a single injected runtime/service access seam,
3. keep current behavior stable with fallback compatibility,
4. add focused contract coverage proving the route prefers the injected seam over ad-hoc `current_app` construction.

## Likely touched files after approval
- `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- `addons/pilotsuite/app/copilot_core/core_setup.py`
- one new small runtime/accessor module under `addons/pilotsuite/app/copilot_core/voice/`
- focused test file(s) near `tests/test_voice_api_transcribe_synthesize_contract.py` / `tests/test_voice_discovery_surface_contract.py`

## Blocker removed by this prep
`P3-011` is no longer blocked by "approval exists but first slice is still fuzzy". The first boundary-enforcement target is now file-backed and narrow enough to start immediately after approval.

## Next exact step
Route the prepared Andreas matrix into the question backlog (`topic 12679`) with explicit recommendation **A**, then start `P3-011-A` immediately if approved.