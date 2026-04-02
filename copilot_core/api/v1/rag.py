"""Compatibility bridge to the runtime RAG blueprint implementation.

The active runtime truth for `copilot_core.api.v1.rag` lives in the rootfs tree.
This repo-level module re-exports that implementation so registry imports,
contract tests, and app wiring all resolve to the same blueprint surface.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_RUNTIME_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "rootfs"
    / "usr"
    / "src"
    / "app"
    / "copilot_core"
    / "api"
    / "v1"
    / "rag.py"
)
_RUNTIME_MODULE_NAME = "copilot_core._runtime_api_v1_rag"

_spec = importlib.util.spec_from_file_location(_RUNTIME_MODULE_NAME, _RUNTIME_MODULE_PATH)
if _spec is None or _spec.loader is None:  # pragma: no cover - deterministic import guard
    raise ImportError(f"Unable to load runtime RAG module from {_RUNTIME_MODULE_PATH}")

_runtime_module = importlib.util.module_from_spec(_spec)
sys.modules.setdefault(_RUNTIME_MODULE_NAME, _runtime_module)
_spec.loader.exec_module(_runtime_module)

globals().update(
    {
        name: value
        for name, value in vars(_runtime_module).items()
        if name not in {"__name__", "__loader__", "__package__", "__spec__"}
    }
)

rag_bp = bp

__all__ = sorted({*(getattr(_runtime_module, "__all__", []) or []), "bp", "rag_bp"})
