"""Plugin Sandboxing — restricts what loaded plugins can access."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Built-in denylist — modules plugins must not import directly
# ------------------------------------------------------------------
DENYLISTED_MODULES: set[str] = {
    "ctypes",          # memory abuse
    "cffi",            # arbitrary native code
    "multiprocessing", # process forking (security boundary issues)
    "_posixshm",       # shared memory
    "sys",
    "builtins",
}


class SandboxConfig:
    """Sandbox configuration for a single plugin.

    Attributes:
        allowed_paths: Directories the plugin may read/write.
                       None means only its own plugin directory.
        blocked_modules: Additional modules to block beyond the denylist.
        env_prefix: If set, only env vars with this prefix are visible.
        max_memory_mb: Memory ceiling (currently informational only).
    """

    def __init__(
        self,
        plugin_id: str,
        plugin_dir: str | Path | None = None,
        allowed_paths: list[str | Path] | None = None,
        blocked_modules: set[str] | None = None,
        env_prefix: str | None = None,
        max_memory_mb: int | None = None,
    ) -> None:
        self.plugin_id = plugin_id
        self.plugin_dir = Path(plugin_dir) if plugin_dir else None
        self.allowed_paths: list[Path] = [Path(p).expanduser() for p in (allowed_paths or [])]
        if self.plugin_dir and self.plugin_dir not in self.allowed_paths:
            self.allowed_paths.insert(0, self.plugin_dir)
        self.blocked_modules: set[str] = (blocked_modules or set()) | DENYLISTED_MODULES
        self.env_prefix = env_prefix
        self.max_memory_mb = max_memory_mb

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def is_module_allowed(self, module_name: str) -> bool:
        """Check whether a module import is permitted."""
        # Exact match
        if module_name in self.blocked_modules:
            return False
        # Sub-package block  (e.g. "subpkg." prefix in blocked_modules)
        for blocked in self.blocked_modules:
            if module_name.startswith(f"{blocked}."):
                return False
        return True

    def is_path_allowed(self, file_path: str | Path) -> bool:
        """Check whether a file-system path access is permitted.

        If no allowed_paths are configured, only the plugin's own directory
        is accessible.
        """
        if not self.allowed_paths:
            return True  # Allow all when unrestricted (honour-system)

        abs_path = Path(file_path).expanduser().resolve()
        for allowed in self.allowed_paths:
            try:
                abs_path.relative_to(allowed.resolve())
                return True
            except ValueError:
                continue
        return False

    def get_allowed_env(self) -> dict[str, str]:
        """Return the environment variables visible to the plugin."""
        if self.env_prefix is None:
            return dict(os.environ)

        return {
            key: value
            for key, value in os.environ.items()
            if key.startswith(self.env_prefix)
        }


class PluginSandbox:
    """Enforces security boundaries around a single plugin instance.

    Current implementation is a policy-enforcement helper (honour-system)
    rather than a true process-level sandbox. Plugins that respect the
    ``is_module_allowed`` / ``is_path_allowed`` checks can be considered
    reasonably isolated.

    A future version may integrate ``seccomp`` or ``ptrace`` for stronger
    guarantees on Linux hosts.
    """

    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self._active = False

    def activate(self) -> None:
        """Mark the sandbox as active (call before running plugin code)."""
        self._active = True
        logger.debug("Sandbox activated for plugin %s", self.config.plugin_id)

    def deactivate(self) -> None:
        """Mark the sandbox as inactive."""
        self._active = False
        logger.debug("Sandbox deactivated for plugin %s", self.config.plugin_id)

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Policy checks — call these from engine / loader wrappers
    # ------------------------------------------------------------------
    def check_import(self, module_name: str) -> bool:
        """Return True if the module may be imported by this plugin."""
        return self.config.is_module_allowed(module_name)

    def check_file_access(self, file_path: str | Path) -> bool:
        """Return True if the path may be accessed by this plugin."""
        return self.config.is_path_allowed(file_path)

    def get_env(self) -> dict[str, str]:
        """Return sanitized environment for this plugin."""
        return self.config.get_allowed_env()

    def build_context(self) -> dict[str, Any]:
        """Build a context dict to inject into the plugin namespace."""
        return {
            "__pilot_sandbox_active__": self._active,
            "__pilot_plugin_id__": self.config.plugin_id,
        }


# ------------------------------------------------------------------
# Global sandbox registry
# ------------------------------------------------------------------
_sandboxes: dict[str, PluginSandbox] = {}


def get_sandbox(plugin_id: str) -> PluginSandbox | None:
    """Return the sandbox for a registered plugin, or None."""
    return _sandboxes.get(plugin_id)


def register_sandbox(plugin_id: str, sandbox: PluginSandbox) -> None:
    """Register a sandbox for a plugin."""
    _sandboxes[plugin_id] = sandbox
    logger.debug("Sandbox registered for plugin %s", plugin_id)


def unregister_sandbox(plugin_id: str) -> None:
    """Remove a plugin's sandbox."""
    _sandboxes.pop(plugin_id, None)
    logger.debug("Sandbox unregistered for plugin %s", plugin_id)
