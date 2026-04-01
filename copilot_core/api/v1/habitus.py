"""Bridge root imports to the runtime habitus API surface.

The authoritative proposal/action-intent contract for Habitus lives in the
runtime tree under `copilot_core/rootfs/usr/src/app/...`. Root-level tests can
import this module without depending on import-order-sensitive path hacks.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


_RUNTIME_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "rootfs"
    / "usr"
    / "src"
    / "app"
    / "copilot_core"
    / "api"
    / "v1"
    / "habitus.py"
)


def _load_runtime_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "copilot_core._runtime_api_v1_habitus",
        _RUNTIME_MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load runtime habitus module from {_RUNTIME_MODULE_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_runtime = _load_runtime_module()

bp = _runtime.bp
accept_zone_proposal = _runtime.accept_zone_proposal
_build_service_call_preview = _runtime._build_service_call_preview
_normalize_zone_type = _runtime._normalize_zone_type

__all__ = [
    "bp",
    "accept_zone_proposal",
    "_build_service_call_preview",
    "_normalize_zone_type",
]
