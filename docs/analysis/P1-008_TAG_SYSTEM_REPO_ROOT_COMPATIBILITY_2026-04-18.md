# P1-008 Tag System Tests — Repo-root compatibility restore

**Date:** 2026-04-18 03:58 Europe/Berlin  
**Owner:** PilotClaw  
**Status:** ✅ implemented and verified

## Failure cause
- `copilot_core/tags/tests/test_tag_system.py` failed at import time.
- The active core worktree had `copilot_core/tags/tag_api.py`, but the companion `tag_system.py` module and package `__init__.py` were missing.
- Result: repo-root compatibility tests could not import `copilot_core.tags.tag_system.TagSystem` or stabilize the tiny `TagAPI` facade.

## Bounded fix
- Restored the missing repo-root compatibility package files:
  - `copilot_core/tags/__init__.py`
  - `copilot_core/tags/tag_system.py`
- Replaced the broken `copilot_core/tags/tag_api.py` variant with the minimal compatibility facade already used in the main workspace tree.

## Verification
- `python3 -m py_compile copilot_core/tags/__init__.py copilot_core/tags/tag_system.py copilot_core/tags/tag_api.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q copilot_core/tags/tests/test_tag_system.py` → `14 passed`

## Expected outcome
- The six named Tag System rescue failures collapse into the same bounded compatibility surface.
- Repo-root tag tests can run again without widening into add-on tag-service architecture.

## Next exact pull
- Move the rescue queue forward to `P1-006 Voice: Whisper/Piper Integration` unless another nearer file-backed blocker appears.
