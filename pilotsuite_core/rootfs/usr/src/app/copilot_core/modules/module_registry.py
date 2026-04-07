"""Compatibility module registry for Slice-3 contract tests.

This adapter keeps the older ``copilot_core.modules.module_registry`` import path
working while the richer registries live elsewhere in the codebase.
"""

from __future__ import annotations

from typing import Any, Dict, List


class ModuleRegistry:
    """Minimal in-memory registry used by contract tests and lightweight callers."""

    def __init__(self) -> None:
        self._modules: Dict[str, Dict[str, Any]] = {}

    def register_module(self, module_data: Dict[str, Any]) -> bool:
        module_id = str(module_data.get("module_id", "") or "")
        if not module_id:
            return False
        self._modules[module_id] = dict(module_data)
        return True

    def get_all_modules(self) -> List[Dict[str, Any]]:
        return [dict(module) for module in self._modules.values()]
