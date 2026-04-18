# PS Core — CORE-STRUCT-101A Repo-Root Runtime Version Contract

**Date:** 2026-04-18 14:27 Europe/Berlin  
**Task:** CORE-STRUCT-101 / Runtime-API hardening  
**Slice:** repo-root runtime surface contract

## Problem

The repo-root `copilot_core/__init__.py` tried to forward `__version__` with:

```python
from copilot_core import __version__ as _addon_version
```

Inside the package's own initialization, that import resolves back into the same partially initialized repo-root package instead of the addon runtime package path. The practical result was that standalone repo-root imports collapsed to the fallback version:

```python
import copilot_core
print(copilot_core.__version__)
# 0.0.0
```

That breaks the intended runtime/API compatibility surface for tooling, contract tests, and any caller that inspects the repo-root package version without Home Assistant.

## Fix

- keep the existing addon package path extension on `__path__`
- resolve the runtime version through `from .versioning import get_runtime_version`
- compute `__version__ = get_runtime_version()` instead of recursively importing `copilot_core.__version__`
- add focused contract coverage for:
  - repo-root `__version__` forwarding
  - repo-root `__all__` symbol integrity
  - clear standalone failure path for `_require_homeassistant_runtime()`

## Artifact Radius

- `copilot_core/__init__.py`
- `tests/test_repo_root_runtime_surface_contract.py`

## Verification

```bash
python3 -m py_compile copilot_core/__init__.py tests/test_repo_root_runtime_surface_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_repo_root_runtime_surface_contract.py
```

## Result

The repo-root runtime surface now reports the packaged runtime version instead of `0.0.0`, while keeping the standalone import contract explicit and bounded.

## Next

Stay on `CORE-STRUCT-101` and harden the next runtime/API edge without reopening the cleaned `P3-011` voice-context seam, likely around runtime health/readiness surface truth or startup-state exposure.
